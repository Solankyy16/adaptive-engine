"""
routes/sessions.py — All API endpoints for managing test sessions.

Endpoints:
  POST /sessions/start        → Create session, return first question
  POST /sessions/submit       → Submit answer, return next question or study plan
  GET  /sessions/{session_id} → Get full session results
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from app.db.mongodb import get_database
from app.models.session import (
    StartSessionRequest, SubmitAnswerRequest,
    UserSession, AnswerRecord, StudyPlanStep
)
from app.models.question import Question, QuestionPublic
from app.services.irt_engine import probability_correct, update_ability, select_next_question
from app.services.llm_insights import generate_study_plan

router = APIRouter(prefix="/sessions", tags=["Sessions"])
logger = logging.getLogger(__name__)

QUESTIONS_PER_SESSION = int(os.getenv("QUESTIONS_PER_SESSION", 10))
LEARNING_RATE = float(os.getenv("LEARNING_RATE", 0.3))


async def _fetch_all_questions() -> list[dict]:
    """Load all questions from MongoDB once per request. Simple and correct for this scale."""
    db = get_database()
    cursor = db.questions.find({}, {"_id": 0})  # Exclude MongoDB's ObjectId from results
    return await cursor.to_list(length=None)


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_session(body: StartSessionRequest):
    """
    Start a new adaptive test session.

    Returns the session_id and the first question (selected at ability=0.5,
    which means the first question will be closest to medium difficulty).
    """
    db = get_database()

    # 1. Load all questions
    all_questions = await _fetch_all_questions()
    if not all_questions:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No questions found in database. Please run the seed script first."
        )

    # 2. Create a new session document
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    session = UserSession(
        session_id=session_id,
        student_id=body.student_id,
        ability_score=0.5,   # IRT baseline: start at mid-level
    )

    # 3. Select the first question (difficulty closest to 0.5)
    first_q_dict = select_next_question(
        ability=session.ability_score,
        asked_ids=[],
        questions=all_questions
    )
    if not first_q_dict:
        raise HTTPException(status_code=500, detail="Could not select a first question.")

    first_q = Question(**first_q_dict)
    session.questions_asked.append(first_q.question_id)

    # 4. Save session to MongoDB
    await db.sessions.insert_one(session.model_dump())

    return {
        "session_id": session_id,
        "student_id": body.student_id,
        "message": f"Test started. Answer {QUESTIONS_PER_SESSION} questions to complete.",
        "questions_total": QUESTIONS_PER_SESSION,
        "question_number": 1,
        "current_question": QuestionPublic.from_question(first_q).model_dump()
    }


@router.post("/submit")
async def submit_answer(body: SubmitAnswerRequest):
    """
    Submit an answer for the current question.

    Flow:
      1. Load session from MongoDB
      2. Validate: session exists, is in progress, question was actually asked
      3. Check correctness, update ability score using IRT
      4. If session complete (10 questions): trigger LLM study plan generation
      5. Save updated session to MongoDB
      6. Return: whether answer was correct + next question OR study plan
    """
    db = get_database()

    # ── 1. Load session ───────────────────────────────────────────────────────
    session_doc = await db.sessions.find_one(
        {"session_id": body.session_id}, {"_id": 0}
    )
    if not session_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{body.session_id}' not found."
        )

    session = UserSession(**session_doc)

    # ── 2. Validate state ─────────────────────────────────────────────────────
    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This session is already completed. Check your results at GET /sessions/{id}."
        )

    if body.question_id not in session.questions_asked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question '{body.question_id}' was not part of this session."
        )

    # ── 3. Grade the answer ───────────────────────────────────────────────────
    question_doc = await db.questions.find_one(
        {"question_id": body.question_id}, {"_id": 0}
    )
    if not question_doc:
        raise HTTPException(status_code=404, detail=f"Question '{body.question_id}' not found.")

    question = Question(**question_doc)
    is_correct = body.answer.strip().upper() == question.correct_answer.strip().upper()

    # ── 4. Update ability score using IRT ─────────────────────────────────────
    ability_before = session.ability_score
    ability_after = update_ability(
        ability=ability_before,
        difficulty=question.difficulty,
        is_correct=is_correct,
        learning_rate=LEARNING_RATE
    )

    # ── 5. Record the answer ──────────────────────────────────────────────────
    answer_record = AnswerRecord(
        question_id=body.question_id,
        submitted_answer=body.answer.strip().upper(),
        correct_answer=question.correct_answer,
        is_correct=is_correct,
        difficulty=question.difficulty,
        topic=question.topic,
        ability_before=ability_before,
        ability_after=ability_after
    )
    session.answers.append(answer_record)
    session.ability_score = ability_after

    # ── 6. Check if test is complete ─────────────────────────────────────────
    questions_answered = len(session.answers)
    is_test_complete = questions_answered >= QUESTIONS_PER_SESSION

    study_plan = None
    if is_test_complete:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

        # Generate AI study plan — non-fatal if it fails
        try:
            plan_steps = await generate_study_plan(session.model_dump())
            session.study_plan = [StudyPlanStep(**s) for s in plan_steps]
            study_plan = [s.model_dump() for s in session.study_plan]
        except Exception as e:
            logger.error(f"Study plan generation failed: {e}")
            session.llm_error = str(e)

    else:
        # Select next question
        all_questions = await _fetch_all_questions()
        next_q_dict = select_next_question(
            ability=session.ability_score,
            asked_ids=session.questions_asked,
            questions=all_questions
        )
        if next_q_dict:
            session.questions_asked.append(next_q_dict["question_id"])

    # ── 7. Persist updated session ────────────────────────────────────────────
    await db.sessions.replace_one(
        {"session_id": session.session_id},
        session.model_dump()
    )

    # ── 8. Build response ─────────────────────────────────────────────────────
    response = {
        "question_number": questions_answered,
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "ability_score": session.ability_score,
        "session_status": session.status,
    }

    if is_test_complete:
        accuracy = round(
            sum(1 for a in session.answers if a.is_correct) / len(session.answers) * 100
        )
        response["test_complete"] = True
        response["final_ability_score"] = session.ability_score
        response["accuracy_percentage"] = accuracy
        response["study_plan"] = study_plan
        response["message"] = (
            f"Test complete! You answered {questions_answered} questions with "
            f"{accuracy}% accuracy. Your study plan is ready."
        )
    else:
        # Next question
        next_q_dict = await db.questions.find_one(
            {"question_id": session.questions_asked[-1]}, {"_id": 0}
        )
        if next_q_dict:
            next_q = Question(**next_q_dict)
            response["test_complete"] = False
            response["question_number_next"] = questions_answered + 1
            response["next_question"] = QuestionPublic.from_question(next_q).model_dump()
            response["message"] = (
                f"{'Correct! ✓' if is_correct else 'Incorrect. ✗'} "
                f"Question {questions_answered + 1} of {QUESTIONS_PER_SESSION} next."
            )

    return response


@router.get("/{session_id}")
async def get_session(session_id: str):
    """
    Retrieve the full results of a session.
    Call this after completion to see the full study plan and answer history.
    """
    db = get_database()
    session_doc = await db.sessions.find_one({"session_id": session_id}, {"_id": 0})

    if not session_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    session = UserSession(**session_doc)
    total = len(session.answers)
    correct = sum(1 for a in session.answers if a.is_correct)

    return {
        "session_id": session.session_id,
        "student_id": session.student_id,
        "status": session.status,
        "ability_score": session.ability_score,
        "questions_answered": total,
        "accuracy_percentage": round(correct / total * 100) if total else 0,
        "answers": [a.model_dump() for a in session.answers],
        "study_plan": [s.model_dump() for s in session.study_plan] if session.study_plan else None,
        "llm_error": session.llm_error,
        "started_at": session.started_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }

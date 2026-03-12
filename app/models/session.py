"""
models/session.py — The data shape of a UserSession document.

A session is like a save file for one student's test run.
It stores everything: current ability estimate, every answer, and the final study plan.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone


class AnswerRecord(BaseModel):
    """One answer the student submitted, stored inside the session document."""
    question_id: str
    submitted_answer: str
    correct_answer: str
    is_correct: bool
    difficulty: float          # Difficulty of this question (b-parameter)
    topic: str
    ability_before: float      # θ before this answer — useful for debugging
    ability_after: float       # θ after this answer


class StudyPlanStep(BaseModel):
    """One step in the 3-step personalized study plan from the LLM."""
    step: int
    focus: str                 # The topic/area to focus on
    action: str                # What the student should DO
    resources: List[str]       # Recommended resources


class UserSession(BaseModel):
    """
    The full session document stored in MongoDB.
    
    Design decision: We embed answers as an array inside the session document
    rather than a separate Answers collection. This makes reading a session
    a single MongoDB query instead of a JOIN — much faster for our use case.
    """
    session_id: str
    student_id: str
    ability_score: float = 0.5              # θ — starts at 0.5 (mid-level)
    questions_asked: List[str] = []         # question_ids already shown
    answers: List[AnswerRecord] = []
    status: Literal["in_progress", "completed"] = "in_progress"
    study_plan: Optional[List[StudyPlanStep]] = None
    llm_error: Optional[str] = None         # If LLM fails, we log it here
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


# ── Request/Response models for the API ──────────────────────────────────────

class StartSessionRequest(BaseModel):
    student_id: str = Field(..., min_length=1, description="Unique student identifier")


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str = Field(..., description="The answer letter, e.g. 'A', 'B', 'C', 'D'")

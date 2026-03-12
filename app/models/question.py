"""
models/question.py — The data shape of a Question document.

Pydantic validates types at runtime. If a document from MongoDB is missing a
required field, Pydantic raises an error immediately — no silent bugs.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class Question(BaseModel):
    """
    Matches the MongoDB document structure exactly.
    'question_id' is our app-level ID (q001, q002…).
    MongoDB also adds '_id' (ObjectId) but we don't expose that via the API.
    """
    question_id: str
    text: str
    options: List[str]                    # e.g. ["A) Permanent", "B) Fleeting", …]
    correct_answer: str                   # e.g. "B"
    difficulty: float                     # IRT b-parameter — range [0.1, 1.0]
    topic: str                            # e.g. "Vocabulary", "Algebra"
    tags: List[str]                       # e.g. ["GRE", "antonyms"]
    explanation: Optional[str] = None     # Shown after the test ends


class QuestionPublic(BaseModel):
    """
    What we send to the student. We NEVER send correct_answer during the test.
    Security: even if someone intercepts the HTTP response, the answer isn't there.
    """
    question_id: str
    text: str
    options: List[str]
    topic: str
    difficulty_hint: str = Field(
        description="Human-readable difficulty label, not the numeric score"
    )

    @classmethod
    def from_question(cls, q: Question) -> "QuestionPublic":
        """Convert internal Question to safe public version."""
        if q.difficulty < 0.35:
            label = "Easy"
        elif q.difficulty < 0.65:
            label = "Medium"
        else:
            label = "Hard"
        return cls(
            question_id=q.question_id,
            text=q.text,
            options=q.options,
            topic=q.topic,
            difficulty_hint=label
        )

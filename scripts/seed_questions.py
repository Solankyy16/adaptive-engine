"""
scripts/seed_questions.py — Load 10 GRE-style questions into MongoDB.

Run this once before starting the app:
  python scripts/seed_questions.py

It is IDEMPOTENT: running it twice won't create duplicates.
It clears existing questions and re-inserts fresh ones.
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

# ── 10 GRE Questions: Mix of topics & difficulty levels ──────────────────────
# Difficulty scale: 0.1 (very easy) → 1.0 (very hard)
# Topics: Vocabulary, Reading Comprehension, Algebra, Geometry, Data Interpretation

QUESTIONS = [
    {
        "question_id": "q001",
        "text": "Which word is closest in meaning to 'Ephemeral'?",
        "options": ["A) Permanent", "B) Fleeting", "C) Ancient", "D) Vibrant"],
        "correct_answer": "B",
        "difficulty": 0.25,
        "topic": "Vocabulary",
        "tags": ["GRE", "synonyms", "beginner"],
        "explanation": "'Ephemeral' means lasting for a very short time. 'Fleeting' is the closest synonym."
    },
    {
        "question_id": "q002",
        "text": "If 3x + 7 = 22, what is the value of x?",
        "options": ["A) 3", "B) 5", "C) 7", "D) 9"],
        "correct_answer": "B",
        "difficulty": 0.20,
        "topic": "Algebra",
        "tags": ["GRE", "linear-equations", "beginner"],
        "explanation": "3x = 22 - 7 = 15, so x = 15 / 3 = 5."
    },
    {
        "question_id": "q003",
        "text": "A rectangle has a length of 12 cm and a width of 5 cm. What is the length of its diagonal?",
        "options": ["A) 11 cm", "B) 13 cm", "C) 15 cm", "D) 17 cm"],
        "correct_answer": "B",
        "difficulty": 0.40,
        "topic": "Geometry",
        "tags": ["GRE", "Pythagorean-theorem", "intermediate"],
        "explanation": "Diagonal = √(12² + 5²) = √(144 + 25) = √169 = 13 cm."
    },
    {
        "question_id": "q004",
        "text": "Which word is the ANTONYM (opposite) of 'Loquacious'?",
        "options": ["A) Talkative", "B) Reticent", "C) Verbose", "D) Gregarious"],
        "correct_answer": "B",
        "difficulty": 0.45,
        "topic": "Vocabulary",
        "tags": ["GRE", "antonyms", "intermediate"],
        "explanation": "'Loquacious' means very talkative. Its antonym is 'Reticent', which means not revealing one's thoughts readily."
    },
    {
        "question_id": "q005",
        "text": (
            "Read the passage: 'The city council's decision to rezone the waterfront district was met with "
            "both enthusiasm and alarm. Developers praised the move as long overdue, while environmental "
            "groups warned of irreversible ecological damage.'\n\n"
            "Which of the following best describes the reaction to the rezoning decision?"
        ),
        "options": [
            "A) Universally positive",
            "B) Universally negative",
            "C) Mixed, with differing stakeholder views",
            "D) Largely indifferent"
        ],
        "correct_answer": "C",
        "difficulty": 0.35,
        "topic": "Reading Comprehension",
        "tags": ["GRE", "main-idea", "beginner"],
        "explanation": "The passage explicitly states both positive (developers) and negative (environmentalists) reactions."
    },
    {
        "question_id": "q006",
        "text": "If a store offers a 30% discount on an item originally priced at $240, what is the sale price?",
        "options": ["A) $148", "B) $162", "C) $168", "D) $180"],
        "correct_answer": "C",
        "difficulty": 0.38,
        "topic": "Algebra",
        "tags": ["GRE", "percentages", "intermediate"],
        "explanation": "Discount = 30% × $240 = $72. Sale price = $240 − $72 = $168."
    },
    {
        "question_id": "q007",
        "text": "Which word best fits the blank: 'Her _______ approach to managing the team allowed each member to work independently.'",
        "options": ["A) Autocratic", "B) Laissez-faire", "C) Dogmatic", "D) Imperious"],
        "correct_answer": "B",
        "difficulty": 0.60,
        "topic": "Vocabulary",
        "tags": ["GRE", "sentence-completion", "advanced"],
        "explanation": "'Laissez-faire' describes a policy of leaving things to take their own course, with minimal intervention — matching the context perfectly."
    },
    {
        "question_id": "q008",
        "text": (
            "A study tracked 500 students: 200 attended tutoring (Group A) and 300 did not (Group B). "
            "In Group A, 160 passed the exam. In Group B, 150 passed.\n\n"
            "What is the pass rate difference between Group A and Group B (A minus B)?"
        ),
        "options": ["A) 10%", "B) 20%", "C) 30%", "D) 40%"],
        "correct_answer": "C",
        "difficulty": 0.65,
        "topic": "Data Interpretation",
        "tags": ["GRE", "percentages", "data-analysis", "advanced"],
        "explanation": "Group A pass rate = 160/200 = 80%. Group B pass rate = 150/300 = 50%. Difference = 80% − 50% = 30%."
    },
    {
        "question_id": "q009",
        "text": (
            "Read the argument: 'Company X increased its marketing budget by 50% last year, "
            "and its revenue grew by 20%. Therefore, marketing spending directly causes revenue growth.'\n\n"
            "Which of the following most weakens this argument?"
        ),
        "options": [
            "A) Company X's main competitor also grew revenue by 20% last year with no change in marketing spend",
            "B) Company X hired 10 new salespeople last year",
            "C) The marketing campaign won several industry awards",
            "D) Revenue growth is always associated with increased spending"
        ],
        "correct_answer": "A",
        "difficulty": 0.75,
        "topic": "Reading Comprehension",
        "tags": ["GRE", "critical-reasoning", "advanced"],
        "explanation": (
            "If a competitor grew revenue equally without increasing marketing spend, "
            "it suggests another factor (e.g., market conditions) caused the growth, "
            "undermining the causal claim."
        )
    },
    {
        "question_id": "q010",
        "text": (
            "For the equation x² − 5x + 6 = 0, which of the following gives both roots?"
        ),
        "options": ["A) x = 1 and x = 6", "B) x = 2 and x = 3", "C) x = −2 and x = −3", "D) x = 3 and x = 5"],
        "correct_answer": "B",
        "difficulty": 0.55,
        "topic": "Algebra",
        "tags": ["GRE", "quadratic-equations", "intermediate"],
        "explanation": "Factoring: (x−2)(x−3) = 0, so x = 2 or x = 3. Verify: 2+3=5 ✓ and 2×3=6 ✓."
    },
]


async def seed():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "adaptive_engine")

    if not uri:
        print("❌  ERROR: MONGODB_URI not found in .env file.")
        print("    → Copy .env.example to .env and fill in your MongoDB Atlas URI.")
        return

    print(f"📡  Connecting to MongoDB...")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    # Verify connection
    try:
        await client.admin.command("ping")
        print("✅  Connected to MongoDB Atlas!")
    except Exception as e:
        print(f"❌  Could not connect: {e}")
        print("    → Check your MONGODB_URI in .env")
        client.close()
        return

    # Clear existing questions (idempotent seed)
    existing = await db.questions.count_documents({})
    if existing > 0:
        print(f"🗑️   Removing {existing} existing questions...")
        await db.questions.delete_many({})

    # Insert fresh questions
    result = await db.questions.insert_many(QUESTIONS)
    print(f"✅  Inserted {len(result.inserted_ids)} questions into '{db_name}.questions'")

    # Show summary
    print("\n📊  Question Summary:")
    print(f"   {'ID':<8} {'Topic':<25} {'Difficulty':<12} {'Tags'}")
    print(f"   {'-'*8} {'-'*25} {'-'*12} {'-'*30}")
    for q in QUESTIONS:
        print(f"   {q['question_id']:<8} {q['topic']:<25} {q['difficulty']:<12} {', '.join(q['tags'][:2])}")

    print(f"\n🎉  Seed complete! Your database is ready.")
    print(f"    Start the server with: uvicorn app.main:app --reload")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())

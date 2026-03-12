#  AI-Driven Adaptive Diagnostic Engine

> A production-grade **Computerized Adaptive Testing (CAT)** backend for GRE preparation — built with FastAPI, MongoDB Atlas, and Groq LLM. Uses **Item Response Theory (1PL Rasch Model)** to dynamically select questions based on each student's live ability estimate, then generates a personalized AI study plan on completion.



## Quick Start (5 Commands)

### Prerequisites
- Python 3.11+
- MongoDB Atlas account (free) — [cloud.mongodb.com](https://cloud.mongodb.com)
- Groq API key (free, no credit card) — [console.groq.com](https://console.groq.com)

```bash
# 1. Clone the repo
git clone https://github.com/Solankyy16/adaptive-engine.git
cd adaptive-engine

# 2. Create virtual environment and install dependencies
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

# 3. Configure environment (copy template, fill in your keys)
copy .env.example .env         # Windows
# cp .env.example .env         # Mac/Linux

# 4. Seed the database with 10 GRE questions
python scripts/seed_questions.py

# 5. Start the server
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** — interactive Swagger UI to test all endpoints instantly.

---

##  API Documentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check — verifies DB connection and question count |
| `POST` | `/sessions/start` | Create a new test session, returns first adaptive question |
| `POST` | `/sessions/submit` | Submit an answer, updates IRT ability score, returns next question |
| `GET` | `/sessions/{session_id}` | Full session results including AI-generated study plan |

### Complete Flow Example

**Step 1 — Start a session:**
```json
POST /sessions/start
Body: {"student_id": "student_001"}

Response:
{
  "session_id": "sess_6cfe8356c23e",
  "question_number": 1,
  "current_question": {
    "question_id": "q004",
    "text": "Which word is the ANTONYM of 'Loquacious'?",
    "options": ["A) Talkative", "B) Reticent", "C) Verbose", "D) Gregarious"],
    "topic": "Vocabulary",
    "difficulty_hint": "Medium"
  }
}
```

**Step 2 — Submit answers (repeat for all 10 questions):**
```json
POST /sessions/submit
Body: {"session_id": "sess_6cfe8356c23e", "question_id": "q004", "answer": "B"}

Response:
{
  "is_correct": true,
  "ability_score": 0.6463,
  "next_question": { "...harder question..." }
}
```

**Step 3 — After 10 answers, AI study plan auto-generated:**
```json
GET /sessions/sess_6cfe8356c23e

{
  "status": "completed",
  "ability_score": 0.99,
  "accuracy_percentage": 80,
  "study_plan": [
    {
      "step": 1,
      "focus": "Data Interpretation Fundamentals",
      "action": "Complete the Data Interpretation chapter in Magoosh GRE prep",
      "resources": ["Magoosh GRE", "ETS PowerPrep"]
    },
    {
      "step": 2,
      "focus": "Practice Data Interpretation Questions",
      "action": "Complete 20 Data Interpretation questions from the official ETS PowerPrep practice test (approx. 1.5 hours)",
      "resources": [
        "ETS PowerPrep practice test"
      ]
    },
    {
      "step": 3,
      "focus": "Data Interpretation Strategy Development",
      "action": "Watch the Data Interpretation strategy video on Khan Academy (approx. 45 minutes) and take notes on key concepts",
      "resources": [
        "Khan Academy GRE Data Interpretation strategy video"
      ]
    }
  ],
  "message": "Test complete! You answered 10 questions with 80% accuracy. Your study plan is ready."
}
```

---

##  Adaptive Algorithm — How It Works

### The Model: 1-Parameter Logistic IRT (Rasch Model)

This system uses the same mathematical foundation as the actual GRE CAT.

**Core probability equation:**
```
P(correct | θ, b) = 1 / (1 + e^-(θ - b))
```

| Variable | Meaning | Range |
|----------|---------|-------|
| **θ (theta)** | Student's estimated ability | 0.01 – 0.99 |
| **b** | Question's difficulty parameter | 0.1 – 1.0 |

**Intuition:**
- `θ = b` → P = 0.50 → Maximum information (perfect challenge)
- `θ >> b` → P → 1.0 → Question too easy, minimal information gained
- `θ << b` → P → 0.0 → Question too hard, minimal information gained

### Ability Update — Newton-Raphson Gradient Step

```
θ_new = θ + learning_rate × (observed − P(θ, b))
```

The **"surprise factor"** `(observed − P)` drives the magnitude:
- Correct on a hard question → large upward surprise → large ability increase
- Wrong on an easy question → large downward surprise → large ability decrease

Theta is **clamped to [0.01, 0.99]** to prevent numerical edge cases.

### Question Selection — Maximum Fisher Information

Each question is selected by finding the **unanswered question whose difficulty is closest to the student's current theta**. This maximizes Fisher Information — the student is always challenged at exactly their level.


---

## 🏗️Architecture Decisions & Trade-offs

|## 🏗️ Architecture Decisions & Trade-offs

| # | Decision |  Choice Made | Alternative |  Reasoning |
|---|----------|---------------|----------------|--------------|
| 1 | **Database** | MongoDB Atlas | PostgreSQL | Questions have variable metadata fields — document model handles this naturally without ALTER TABLE migrations. Atlas gives cloud-ready deployment from day one. |
| 2 | **LLM Provider** | Groq (free tier) | OpenAI GPT-4 | Groq is 100% OpenAI API-compatible (same Python package, same code). Switching to GPT-4o = change 2 config lines. Cost: **$0 vs ~$0.03/session**. |
| 3 | **IRT Model** | 1PL Rasch Model | 3PL Full IRT | 3PL needs hundreds of calibration responses per question to estimate discrimination + guessing params. With 10 uncalibrated questions, 1PL is the statistically honest choice. |
| 4 | **DB Driver** | Motor (async) | PyMongo (sync) | FastAPI is async-first. Motor allows non-blocking DB queries — concurrent sessions never block each other waiting for MongoDB. |
| 5 | **Answer Storage** | Embedded in Session doc | Separate Answers collection | Sessions are always read with all their answers together. Embedding = single MongoDB query, no JOINs, simpler code. |
| 6 | **LLM Timing** | Post-test batch call | Per-question real-time | Keeps LLM latency out of the critical test-taking loop. Batching all 10 answers also gives the model richer context for a more specific study plan. |
| 7 | **Question Bank Size** | 10 questions | 500+ questions | Per assignment guidance — quality over quantity. With 500+ questions the θ=0.99 ceiling edge case would not occur. Noted as a known, intentional limitation. |


---

## 🤖 AI Log — How AI Tools Were Used

**Tools: Claude (claude.ai) for architecture and code. Groq/Llama 3.1 for runtime study plan generation.**

### What AI accelerated:
1. **Full project scaffolding** — Claude generated the folder structure, Pydantic models, FastAPI routes, and IRT engine from a detailed architectural brief. Estimated 3–4 hours saved.
2. **IRT formula verification** — Used Claude to verify the Newton-Raphson update formula and confirm theta clamping logic.
3. **Seed question generation** — Claude generated all 10 GRE questions with the exact MongoDB schema across 5 topics and the full 0.1–1.0 difficulty range.

### What I debugged and fixed myself:
1. **Python 3.13 + Pydantic conflict** — `pydantic==2.7.0` tried to compile from Rust source on Python 3.13 (no pre-built wheel). Diagnosed the root cause, upgraded to `pydantic==2.9.2`.
2. **Wrong venv location** — Accidentally created venv inside `scripts/` subfolder. Read the import error path, identified the issue, deleted and recreated from the project root.
3. **Motor/PyMongo incompatibility** — `motor==3.4.0` required `pymongo==4.6.x` but pip resolved a newer version. Fixed by explicitly pinning `pymongo==4.6.3`.
4. **MongoDB Atlas auth failures** — Debugged `bad auth` errors by isolating the issue with a raw `pymongo.MongoClient` ping, then verified `0.0.0.0/0` Network Access.
5. **IRT test threshold calibration** — Two test assertions used thresholds too strict for our 0–1 difficulty scale. Identified the mathematical mismatch, recalibrated thresholds to match actual model output. All 13 tests now pass.

### The honest truth:
AI accelerated boilerplate. Every real error — dependency conflicts, environment issues, auth debugging, test calibration — required independent diagnosis and manual fixing. All architectural decisions were made by reasoning through trade-offs, not by blindly accepting AI output.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
# 13 passed in 0.21s
```

---

## Project Structure

```
adaptive-engine/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, MongoDB index creation
│   ├── db/mongodb.py            # Async Motor connection (singleton pattern)
│   ├── models/
│   │   ├── question.py          # Question + QuestionPublic (hides answer during test)
│   │   └── session.py           # UserSession, AnswerRecord, StudyPlanStep
│   ├── routes/sessions.py       # All endpoints with full error handling
│   └── services/
│       ├── irt_engine.py        # IRT math: probability, update, selection
│       └── llm_insights.py      # Groq integration, prompt engineering, fallback
├── scripts/seed_questions.py    # Idempotent seed: 10 GRE questions, 5 topics
├── tests/test_irt.py            # 13 unit tests covering all IRT properties
├── .env.example                 # Safe template (commit this, never .env)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚙️ Environment Variables

```bash
MONGODB_URI=mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=adaptive_engine
GROQ_API_KEY=gsk_your_groq_key_here
QUESTIONS_PER_SESSION=10
LEARNING_RATE=0.3
```
# adaptive-engine
AI-Driven Adaptive Diagnostic Engine using IRT + FastAPI + MongoDB

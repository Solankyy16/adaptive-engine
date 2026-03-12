"""
main.py — FastAPI application entry point.

This is the file you run to start the server:
  uvicorn app.main:app --reload

FastAPI auto-generates interactive API docs at:
  http://localhost:8000/docs  ← Try your endpoints here without Postman!
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes.sessions import router as sessions_router
from app.db.mongodb import get_database, close_connection

# Configure logging — you'll see meaningful messages in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic.
    This runs BEFORE the app starts accepting requests and AFTER it stops.
    """
    # ── STARTUP ──────────────────────────────────────────────────────────────
    logger.info("🚀 Starting Adaptive Engine API...")
    try:
        db = get_database()

        # Create indexes for performance
        # Compound index: fast difficulty-based question selection by topic
        await db.questions.create_index([("difficulty", 1), ("topic", 1)])
        # Index for fast session lookup
        await db.sessions.create_index([("student_id", 1), ("status", 1)])
        await db.sessions.create_index("session_id", unique=True)

        # Verify DB connection
        q_count = await db.questions.count_documents({})
        logger.info(f"✅ MongoDB connected. Questions in DB: {q_count}")
        if q_count == 0:
            logger.warning(
                "⚠️  No questions found! Run: python scripts/seed_questions.py"
            )
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    yield  # App runs here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    logger.info("Shutting down — closing MongoDB connection...")
    await close_connection()
    logger.info("✅ Shutdown complete.")


# Create the FastAPI app
app = FastAPI(
    title="AI-Driven Adaptive Diagnostic Engine",
    description="""
    A 1-Dimension Computerized Adaptive Testing (CAT) system for GRE preparation.
    
    Uses Item Response Theory (1PL Rasch Model) to dynamically select questions
    based on each student's estimated ability level. After 10 questions, generates
    a personalized study plan using an LLM.
    
    ## How to use
    1. **POST /sessions/start** — Start a test, get your first question
    2. **POST /sessions/submit** — Submit answers, get next question
    3. **GET /sessions/{id}** — After completion, view full results + study plan
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Register route modules
app.include_router(sessions_router)


@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint. Verifies the API and DB are reachable.
    Used by deployment systems (Docker, CI/CD) to check if the app is alive.
    """
    try:
        db = get_database()
        q_count = await db.questions.count_documents({})
        s_count = await db.sessions.count_documents({})
        return {
            "status": "healthy",
            "database": "connected",
            "questions_in_db": q_count,
            "sessions_in_db": s_count,
            "message": "Adaptive Engine is running. Visit /docs to explore the API."
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

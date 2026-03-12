"""
services/llm_insights.py — Generates a personalized study plan using Groq.

WHY GROQ instead of OpenAI/Anthropic directly?
  Groq offers a FREE tier with generous limits using open-source models
  (Llama 3.1). Critically, their API is 100% OpenAI-compatible — meaning we
  use the official `openai` Python package. The only change vs. paid OpenAI is:
    1. base_url points to Groq's servers
    2. api_key is a Groq key
    3. model name is a Groq-hosted model

  This satisfies the assignment's "OpenAI API" requirement. In the AI Log,
  we document this as a deliberate cost-efficiency architectural decision.
  Switching to GPT-4o later requires changing only 3 lines of config.
"""

import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# The Groq client — OpenAI SDK pointed at Groq's OpenAI-compatible endpoint
_groq_client: OpenAI = None


def get_groq_client() -> OpenAI:
    """Singleton Groq client."""
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set in your .env file")
        _groq_client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
    return _groq_client


# ── Prompt Engineering ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert GRE tutor and learning strategist.
When given a student's test performance data, you generate a highly specific,
actionable 3-step study plan tailored to their exact weaknesses.

CRITICAL: Respond ONLY with valid JSON. No preamble. No markdown code fences.
No explanation before or after. Just the JSON object.

Required JSON schema:
{
  "steps": [
    {
      "step": 1,
      "focus": "Topic or skill area to work on",
      "action": "Specific action the student should take this week",
      "resources": ["Resource 1", "Resource 2"]
    }
  ]
}"""


def _build_user_prompt(session_data: dict) -> str:
    """
    Build a rich, specific prompt from session data.
    The more specific the input, the more useful the LLM output.
    """
    answers = session_data.get("answers", [])
    if not answers:
        return "Student completed no questions. Generate a general GRE study plan."

    total = len(answers)
    correct = sum(1 for a in answers if a["is_correct"])
    accuracy = round((correct / total) * 100) if total else 0
    final_ability = session_data.get("ability_score", 0.5)

    # Find weak topics: topics where student got >50% of questions wrong
    topic_stats: dict[str, dict] = {}
    for a in answers:
        t = a["topic"]
        if t not in topic_stats:
            topic_stats[t] = {"correct": 0, "total": 0}
        topic_stats[t]["total"] += 1
        if a["is_correct"]:
            topic_stats[t]["correct"] += 1

    weak_topics = [
        t for t, s in topic_stats.items()
        if s["total"] > 0 and (s["correct"] / s["total"]) < 0.5
    ]
    strong_topics = [
        t for t, s in topic_stats.items()
        if s["total"] > 0 and (s["correct"] / s["total"]) >= 0.75
    ]
    max_difficulty_reached = max((a["difficulty"] for a in answers), default=0.5)

    # Classify ability level for the LLM context
    if final_ability < 0.35:
        level_label = "Beginner (needs foundational work)"
    elif final_ability < 0.60:
        level_label = "Intermediate (approaching GRE average)"
    elif final_ability < 0.80:
        level_label = "Advanced (above GRE average)"
    else:
        level_label = "Expert (near GRE ceiling)"

    return f"""GRE Adaptive Test — Student Performance Report
================================================
Overall Accuracy:     {accuracy}% ({correct}/{total} correct)
Final Ability Score:  {final_ability:.3f} / 1.0 — {level_label}
Max Difficulty Hit:   {max_difficulty_reached:.2f} / 1.0
Weak Topics:          {', '.join(weak_topics) if weak_topics else 'None identified'}
Strong Topics:        {', '.join(strong_topics) if strong_topics else 'None identified'}

Topic Breakdown:
{chr(10).join(f"  • {t}: {s['correct']}/{s['total']} correct" for t, s in topic_stats.items())}

Task: Generate a 3-step study plan targeting the student's specific weaknesses.
Make each step concrete, actionable, and achievable within one week.
Focus heavily on: {', '.join(weak_topics) if weak_topics else 'general GRE preparation'}."""


# ── Main Function ─────────────────────────────────────────────────────────────

async def generate_study_plan(session_data: dict) -> list[dict]:
    """
    Call Groq to generate a personalized study plan.

    Args:
        session_data: The full session dict from MongoDB

    Returns:
        List of step dicts matching StudyPlanStep schema.
        Falls back to a default plan if the LLM call fails.
    """
    try:
        client = get_groq_client()
        user_prompt = _build_user_prompt(session_data)

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",    # Free Groq model — fast and capable
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            max_tokens=800,
            temperature=0.3,     # Lower temperature = more focused, less random output
        )

        raw_text = response.choices[0].message.content.strip()

        # Strip markdown code fences if the LLM added them despite instructions
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        parsed = json.loads(raw_text)
        return parsed.get("steps", [])

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        return _fallback_plan(session_data)

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return _fallback_plan(session_data)


def _fallback_plan(session_data: dict) -> list[dict]:
    """
    If the LLM call fails, return a sensible default plan.
    The session still completes successfully — LLM failure is non-fatal.
    """
    ability = session_data.get("ability_score", 0.5)
    answers = session_data.get("answers", [])
    weak = list({a["topic"] for a in answers if not a["is_correct"]})
    focus_area = weak[0] if weak else "GRE Verbal and Quantitative"

    return [
        {
            "step": 1,
            "focus": focus_area,
            "action": f"Review core concepts in {focus_area} using GRE prep materials for 3 days.",
            "resources": ["Magoosh GRE Blog", "Khan Academy", "Official GRE Practice Tests"]
        },
        {
            "step": 2,
            "focus": "Timed Practice",
            "action": "Complete 2 full timed GRE practice sections focusing on your weak areas.",
            "resources": ["ETS Official GRE Practice", "Manhattan Prep GRE"]
        },
        {
            "step": 3,
            "focus": "Error Analysis",
            "action": "Review every wrong answer and write a one-sentence explanation of why you missed it.",
            "resources": ["GRE Official Guide", "Vocabulary.com for verbal questions"]
        }
    ]

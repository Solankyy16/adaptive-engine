"""
services/irt_engine.py — The mathematical heart of the adaptive system.

This implements the 1-Parameter Logistic (1PL) IRT model, also known as the
Rasch model. It answers two questions:
  1. Given a student's ability and a question's difficulty, what is the
     probability the student gets it right?
  2. Given whether they got it right or wrong, how should we update our
     estimate of their ability?

WHY 1PL over 3PL (full IRT)?
  The 3-Parameter model adds discrimination (a) and guessing (c) parameters.
  For a 10-question demo with unknown question calibration data, we don't have
  enough statistical power to estimate those parameters. 1PL gives us a
  mathematically sound, implementable solution with our data constraints.
"""

import math


def probability_correct(ability: float, difficulty: float) -> float:
    """
    1PL Rasch Model: P(correct | θ, b) = 1 / (1 + e^-(θ - b))

    Args:
        ability:    θ — student's current ability estimate [0.01, 0.99]
        difficulty: b — question's difficulty parameter    [0.1, 1.0]

    Returns:
        Probability between 0 and 1 of the student answering correctly.

    Examples:
        ability=0.5, difficulty=0.5 → P=0.5  (50/50 — perfect information)
        ability=0.8, difficulty=0.3 → P≈0.88 (strong student, easy question)
        ability=0.2, difficulty=0.9 → P≈0.12 (weak student, hard question)
    """
    return 1.0 / (1.0 + math.exp(-(ability - difficulty)))


def update_ability(
    ability: float,
    difficulty: float,
    is_correct: bool,
    learning_rate: float = 0.3
) -> float:
    """
    Newton-Raphson gradient step to update the ability estimate.

    Formula: θ_new = θ + lr * (observed - P(correct | θ, b))

    The intuition:
      - If student got it correct (observed=1) and P was 0.5, the surprise is
        high (1 - 0.5 = 0.5), so we update ability UP by a large amount.
      - If student got it correct and P was already 0.95, the surprise is small
        (1 - 0.95 = 0.05), so we update ability UP by a tiny amount.
      - Same logic in reverse for incorrect answers.

    Args:
        ability:       Current θ estimate
        difficulty:    b-parameter of the question just answered
        is_correct:    Did the student answer correctly?
        learning_rate: Step size. 0.3 is a good default for short tests.
                       Lower = slower adaptation. Higher = noisier estimates.

    Returns:
        Updated ability estimate, clamped to [0.01, 0.99].
        We clamp to avoid θ reaching 0 or 1 (which breaks probability_correct).
    """
    p = probability_correct(ability, difficulty)
    observed = 1.0 if is_correct else 0.0
    delta = learning_rate * (observed - p)
    new_ability = ability + delta

    # Clamp: ability must stay in (0, 1) open interval
    # 0.01 and 0.99 give us safe numerical margins
    return round(max(0.01, min(0.99, new_ability)), 4)


def select_next_question(
    ability: float,
    asked_ids: list[str],
    questions: list[dict]
) -> dict | None:
    """
    Select the most informative question for the student's current ability.

    Strategy: Maximum Information — pick the question whose difficulty is
    closest to the student's current ability estimate.

    WHY this works: In IRT, a question gives maximum information when
    P(correct) ≈ 0.5, which happens when difficulty ≈ ability. A question
    that's too easy (P=0.95) tells us almost nothing new about the student.
    A question that's too hard (P=0.05) also tells us very little.

    Args:
        ability:   Current θ estimate
        asked_ids: List of question_ids already shown (to avoid repeats)
        questions: All available question dicts from MongoDB

    Returns:
        The best next question dict, or None if no questions remain.
    """
    eligible = [q for q in questions if q["question_id"] not in asked_ids]

    if not eligible:
        return None

    # Select the question that minimizes |difficulty - ability|
    return min(eligible, key=lambda q: abs(q["difficulty"] - ability))

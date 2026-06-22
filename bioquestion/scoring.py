"""Quiz scoring constants and deterministic multiple-choice grading."""

from __future__ import annotations

from bioquestion.schemas import ChoiceGradingDetail, MultipleChoiceQuestion

MC_COUNT = 5
SA_COUNT = 2
MC_OPTION_KEYS = ("A", "B", "C", "D", "E")
MC_OPTION_SCORE = 3.0
MC_MAX_SCORE = 15.0
SA_MAX_SCORES = (10.0, 15.0)
REPORT_MAX_SCORE = 100.0
QUIZ_MAX_SCORE = MC_COUNT * MC_MAX_SCORE + sum(SA_MAX_SCORES)

MC_REPORT_MAX_SCORE = MC_MAX_SCORE
MC_MISS_PENALTY = 3.0
MC_WRONG_PENALTY = 3.0
MC_TWO_MISS_SCORE = 3.0
MC_ONE_MISS_ONE_WRONG_SCORE = 6.0

EZ_MC_COUNT = 4
EZ_SA_COUNT = 1
EZ_MC_OPTION_KEYS = ("A", "B", "C", "D")


def short_answer_max_score(index: int) -> float:
    """Return max score for the nth short-answer question (0-based)."""
    if index < 0 or index >= len(SA_MAX_SCORES):
        raise IndexError(f"Short-answer index {index} out of range.")
    return SA_MAX_SCORES[index]


def score_multiple_choice(
    question: MultipleChoiceQuestion,
    user_selected: list[str],
) -> tuple[float, ChoiceGradingDetail, bool]:
    """Score one multi-select question (15 pts max, 3 pts per option).

    Miss (correct option not selected):
      1 miss → −3; 2 misses → 3 pts total; >2 misses → 0.

    Wrong (incorrect option selected):
      1 wrong → −3; ≥2 wrong → 0.

    Combined:
      1 miss + 1 wrong → 6 pts; 2 misses + 1 wrong → 0.
    """
    user_set = set(user_selected)
    correct_set = set(question.correct_answers)
    wrong = sorted(user_set - correct_set)
    missed = sorted(correct_set - user_set)
    n_miss = len(missed)
    n_wrong = len(wrong)

    if n_wrong >= 2:
        score = 0.0
    elif n_miss > 2:
        score = 0.0
    elif n_miss == 2 and n_wrong >= 1:
        score = 0.0
    elif n_miss == 2 and n_wrong == 0:
        score = MC_TWO_MISS_SCORE
    elif n_miss == 1 and n_wrong == 1:
        score = MC_ONE_MISS_ONE_WRONG_SCORE
    elif n_miss == 1 and n_wrong == 0:
        score = MC_MAX_SCORE - MC_MISS_PENALTY
    elif n_miss == 0 and n_wrong == 1:
        score = MC_MAX_SCORE - MC_WRONG_PENALTY
    else:
        score = MC_MAX_SCORE

    is_correct = score == MC_MAX_SCORE
    detail = ChoiceGradingDetail(
        user_answers=sorted(user_selected),
        correct_answers=sorted(question.correct_answers),
        missed=missed,
        extra=wrong,
        wrong=wrong,
        is_correct=is_correct,
    )
    return score, detail, is_correct


def explain_multiple_choice(
    question: MultipleChoiceQuestion,
    detail: ChoiceGradingDetail,
    score: float,
) -> str:
    parts: list[str] = []
    if question.explanation:
        parts.append(question.explanation)

    n_miss = len(detail.missed)
    n_wrong = len(detail.wrong)

    if score == MC_MAX_SCORE:
        parts.append(f"Full credit: {MC_MAX_SCORE:.0f}/{MC_MAX_SCORE:.0f}.")
    elif n_wrong >= 2:
        parts.append(
            f"Score 0: {n_wrong} incorrect option(s) selected "
            f"({', '.join(detail.wrong)}). Two or more wrong selections zero the question."
        )
    elif n_miss > 2:
        parts.append(
            f"Score 0: {n_miss} correct option(s) missed "
            f"({', '.join(detail.missed)}). More than two misses zero the question."
        )
    elif n_miss == 2 and n_wrong >= 1:
        parts.append(
            f"Score 0: two missed ({', '.join(detail.missed)}) "
            f"and one wrong selection ({', '.join(detail.wrong)})."
        )
    elif n_miss == 2:
        parts.append(
            f"Two missed correct options ({', '.join(detail.missed)}): "
            f"question capped at {MC_TWO_MISS_SCORE:.0f} pts."
        )
    elif n_miss == 1 and n_wrong == 1:
        parts.append(
            f"One missed ({', '.join(detail.missed)}) and one wrong "
            f"({', '.join(detail.wrong)}): {MC_ONE_MISS_ONE_WRONG_SCORE:.0f}/{MC_MAX_SCORE:.0f}."
        )
    else:
        if detail.missed:
            parts.append(f"Missed correct option(s): {', '.join(detail.missed)} (−3 each).")
        if detail.wrong:
            parts.append(f"Incorrectly selected: {', '.join(detail.wrong)} (−3 each).")
        parts.append(f"Score: {score:.0f}/{MC_MAX_SCORE:.0f}.")

    return " ".join(parts)

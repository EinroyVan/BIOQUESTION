"""Quiz scoring constants and deterministic choice grading."""

from __future__ import annotations

from questioner.schemas import (
    CustomQuizCounts,
    LogicQuestion,
    MultipleChoiceQuestion,
    Question,
    QuestionType,
    QuizMode,
    SingleChoiceQuestion,
    ChoiceGradingDetail,
)

# Normal mode defaults (total 100)
NORMAL_MS_COUNT = 5
NORMAL_LOGIC_COUNT = 3
NORMAL_SA_COUNT = 2

# Easy mode
EASY_SC_COUNT = 4
EASY_SA_COUNT = 1

MS_OPTION_KEYS = ("A", "B", "C", "D", "E")
SC_OPTION_KEYS = ("A", "B", "C", "D")

MS_MAX_SCORE = 10.0
MS_OPTION_SCORE = 2.0
MS_MISS_PENALTY = 2.0
MS_WRONG_PENALTY = 2.0
MS_TWO_MISS_SCORE = 2.0
MS_ONE_MISS_ONE_WRONG_SCORE = 4.0

LOGIC_MAX_SCORE = 6.0
SA_MAX_SCORE = 16.0
SINGLE_MAX_SCORE = 5.0

REPORT_MAX_SCORE = 100.0


def normal_quiz_max_score() -> float:
    return (
        NORMAL_MS_COUNT * MS_MAX_SCORE
        + NORMAL_LOGIC_COUNT * LOGIC_MAX_SCORE
        + NORMAL_SA_COUNT * SA_MAX_SCORE
    )


def custom_quiz_max_score(counts: CustomQuizCounts) -> float:
    return (
        counts.single_choice * SINGLE_MAX_SCORE
        + counts.multiple_choice * MS_MAX_SCORE
        + counts.logic * LOGIC_MAX_SCORE
        + counts.short_answer * SA_MAX_SCORE
    )


def short_answer_max_score(_index: int = 0) -> float:
    return SA_MAX_SCORE


def question_max_score(question: Question, mode: QuizMode) -> float:
    if mode == QuizMode.EASY:
        return 0.0
    if question.type == QuestionType.SINGLE_CHOICE:
        return SINGLE_MAX_SCORE
    if question.type == QuestionType.MULTIPLE_CHOICE:
        return MS_MAX_SCORE
    if question.type == QuestionType.LOGIC:
        return LOGIC_MAX_SCORE
    return SA_MAX_SCORE


def _choice_score_summary(
    detail: ChoiceGradingDetail,
    score: float,
    max_score: float,
) -> str:
    """Brief score reason for UI (no per-option fluff)."""
    if detail.is_correct:
        return f"Full credit: {score:.0f}/{max_score:.0f}."
    n_miss = len(detail.missed)
    n_wrong = len(detail.wrong)
    single_correct = len(detail.correct_answers) == 1

    if single_correct and n_miss >= 1 and n_wrong >= 1:
        return f"One miss + one wrong: {score:.0f}/{max_score:.0f}."
    if n_wrong >= 2:
        return f"Two or more wrong selections ({', '.join(detail.wrong)}): {score:.0f}/{max_score:.0f}."
    if n_miss > 2:
        return f"More than two missed ({', '.join(detail.missed)}): {score:.0f}/{max_score:.0f}."
    if n_miss == 2 and n_wrong >= 1:
        return (
            f"Two missed ({', '.join(detail.missed)}) and wrong ({', '.join(detail.wrong)}): "
            f"{score:.0f}/{max_score:.0f}."
        )
    if n_miss == 2 and n_wrong == 0:
        return f"Two missed ({', '.join(detail.missed)}): {score:.0f}/{max_score:.0f}."
    if n_miss == 1 and n_wrong == 1:
        return f"One miss + one wrong: {score:.0f}/{max_score:.0f}."
    if n_miss == 1 and n_wrong == 0:
        return f"One missed ({', '.join(detail.missed)}): {score:.0f}/{max_score:.0f}."
    if n_miss == 0 and n_wrong == 1:
        return f"One wrong ({', '.join(detail.wrong)}): {score:.0f}/{max_score:.0f}."
    return f"Score: {score:.0f}/{max_score:.0f}."


def score_multiple_choice(
    question: MultipleChoiceQuestion,
    user_selected: list[str],
) -> tuple[float, ChoiceGradingDetail, bool]:
    """Score multi-select (10 pts max, 2 pts per option)."""
    user_set = set(user_selected)
    correct_set = set(question.correct_answers)
    wrong = sorted(user_set - correct_set)
    missed = sorted(correct_set - user_set)
    n_miss = len(missed)
    n_wrong = len(wrong)
    single_correct = len(correct_set) == 1

    if single_correct and n_miss >= 1 and n_wrong >= 1:
        score = 0.0
    elif n_wrong >= 2:
        score = 0.0
    elif n_miss > 2:
        score = 0.0
    elif n_miss == 2 and n_wrong >= 1:
        score = 0.0
    elif n_miss == 2 and n_wrong == 0:
        score = MS_TWO_MISS_SCORE
    elif n_miss == 1 and n_wrong == 1:
        score = MS_ONE_MISS_ONE_WRONG_SCORE
    elif n_miss == 1 and n_wrong == 0:
        score = MS_MAX_SCORE - MS_MISS_PENALTY
    elif n_miss == 0 and n_wrong == 1:
        score = MS_MAX_SCORE - MS_WRONG_PENALTY
    else:
        score = MS_MAX_SCORE

    is_correct = score == MS_MAX_SCORE
    detail = ChoiceGradingDetail(
        user_answers=sorted(user_selected),
        correct_answers=sorted(question.correct_answers),
        missed=missed,
        extra=wrong,
        wrong=wrong,
        is_correct=is_correct,
    )
    return score, detail, is_correct


def score_single_choice(
    question: SingleChoiceQuestion,
    user_selected: list[str],
) -> tuple[float, ChoiceGradingDetail, bool]:
    user_set = set(user_selected)
    correct = question.correct_answer
    is_correct = user_set == {correct}
    wrong = sorted(user_set - {correct}) if user_set else []
    missed = [] if is_correct else ([correct] if correct not in user_set else [])
    score = SINGLE_MAX_SCORE if is_correct else 0.0
    detail = ChoiceGradingDetail(
        user_answers=sorted(user_selected),
        correct_answers=[correct],
        missed=missed,
        extra=wrong,
        wrong=wrong,
        is_correct=is_correct,
    )
    return score, detail, is_correct


def score_logic_question(
    question: LogicQuestion,
    user_selected: list[str],
) -> tuple[float, ChoiceGradingDetail, bool]:
    """Score logic items independently: full 6 pts if correct, else 0 (no partial credit)."""
    user_set = set(user_selected)
    correct = question.correct_answer
    is_correct = user_set == {correct} and len(user_set) == 1
    wrong = sorted(user_set - {correct})
    missed = [] if is_correct else ([correct] if correct not in user_set else [])
    score = LOGIC_MAX_SCORE if is_correct else 0.0
    detail = ChoiceGradingDetail(
        user_answers=sorted(user_selected),
        correct_answers=[correct],
        missed=missed,
        extra=wrong,
        wrong=wrong,
        is_correct=is_correct,
    )
    return score, detail, is_correct


def explain_single_choice(
    question: SingleChoiceQuestion,
    detail: ChoiceGradingDetail,
    score: float,
) -> str:
    return _choice_score_summary(detail, score, SINGLE_MAX_SCORE)


def explain_multiple_choice(
    question: MultipleChoiceQuestion,
    detail: ChoiceGradingDetail,
    score: float,
) -> str:
    return _choice_score_summary(detail, score, MS_MAX_SCORE)


def explain_logic(detail: ChoiceGradingDetail, score: float) -> str:
    if detail.is_correct:
        return f"Full credit: {LOGIC_MAX_SCORE:.0f}/{LOGIC_MAX_SCORE:.0f}."
    selected = ", ".join(detail.user_answers) or "(empty)"
    correct = ", ".join(detail.correct_answers)
    return (
        f"Incorrect (selected {selected}; correct {correct}). "
        f"Score: 0/{LOGIC_MAX_SCORE:.0f}."
    )

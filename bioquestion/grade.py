"""Step 3: Grade user answers against quiz standard answers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from bioquestion.llm import LLMClient
from bioquestion.prompts import GRADE_EZ_SHORT_ANSWER_SYSTEM, GRADE_SHORT_ANSWER_SYSTEM
from bioquestion.schemas import (
    ChoiceGradingDetail,
    GradingReport,
    MultipleChoiceQuestion,
    QuestionGradingResult,
    QuestionType,
    QuizMode,
    QuizResult,
    ShortAnswerQuestion,
    UserAnswer,
    UserAnswerSheet,
)
from bioquestion.scoring import (
    MC_MAX_SCORE,
    MC_REPORT_MAX_SCORE,
    REPORT_MAX_SCORE,
    SA_MAX_SCORES,
    explain_multiple_choice,
    score_multiple_choice,
    short_answer_max_score,
)


class _ShortAnswerGradeResponse(BaseModel):
    question_results: list[QuestionGradingResult] = Field(default_factory=list)
    summary: str = ""


def _answer_map(sheet: UserAnswerSheet) -> dict[str, UserAnswer]:
    return {item.question_id: item for item in sheet.answers}


def _grade_multiple_choice(
    question: MultipleChoiceQuestion,
    user_answer: UserAnswer | None,
) -> QuestionGradingResult:
    selected = user_answer.answer if user_answer and isinstance(user_answer.answer, list) else []
    score, detail, is_correct = score_multiple_choice(question, selected)
    return QuestionGradingResult(
        question_id=question.id,
        question_type=QuestionType.MULTIPLE_CHOICE,
        score=round(score, 1),
        max_score=MC_REPORT_MAX_SCORE,
        is_correct=is_correct,
        choice_detail=detail,
        explanation=explain_multiple_choice(question, detail, score),
        references=question.references,
    )


def _grade_ez_multiple_choice(
    question: MultipleChoiceQuestion,
    user_answer: UserAnswer | None,
) -> QuestionGradingResult:
    selected = user_answer.answer if user_answer and isinstance(user_answer.answer, list) else []
    user_set = set(selected)
    correct_set = set(question.correct_answers)
    is_correct = user_set == correct_set and len(correct_set) == 1
    detail = ChoiceGradingDetail(
        user_answers=sorted(selected),
        correct_answers=sorted(question.correct_answers),
        missed=sorted(correct_set - user_set),
        extra=sorted(user_set - correct_set),
        wrong=sorted(user_set - correct_set),
        is_correct=is_correct,
    )
    if is_correct:
        explanation = question.explanation or "Correct."
    elif not selected:
        explanation = "No option selected."
    elif len(selected) > 1:
        explanation = (
            f"EZ mode expects a single choice. You selected {', '.join(sorted(selected))}; "
            f"the correct answer is {', '.join(sorted(correct_set))}."
        )
    else:
        explanation = (
            f"Incorrect. You selected {selected[0]}; "
            f"the correct answer is {', '.join(sorted(correct_set))}."
        )
        if question.explanation:
            explanation = f"{question.explanation} {explanation}"

    return QuestionGradingResult(
        question_id=question.id,
        question_type=QuestionType.MULTIPLE_CHOICE,
        score=0.0,
        max_score=0.0,
        is_correct=is_correct,
        choice_detail=detail,
        explanation=explanation,
        references=question.references,
    )


def _grade_ez_answers(
    quiz: QuizResult,
    answers: UserAnswerSheet,
    llm: LLMClient | None = None,
) -> GradingReport:
    by_id = _answer_map(answers)
    mc_results: list[QuestionGradingResult] = []
    sa_questions: list[ShortAnswerQuestion] = []

    for question in quiz.questions:
        if isinstance(question, MultipleChoiceQuestion):
            mc_results.append(_grade_ez_multiple_choice(question, by_id.get(question.id)))
        elif isinstance(question, ShortAnswerQuestion):
            sa_questions.append(question)

    sa_results: list[QuestionGradingResult] = []
    sa_summary = ""
    if sa_questions:
        client = llm or LLMClient()
        payload = {
            "short_answer_questions": [q.model_dump(mode="json") for q in sa_questions],
            "user_answers": [
                {
                    "question_id": q.id,
                    "answer": (by_id[q.id].answer if by_id.get(q.id) else ""),
                }
                for q in sa_questions
            ],
        }
        response = client.complete_json(
            GRADE_EZ_SHORT_ANSWER_SYSTEM,
            f"Review these short-answer responses (feedback only, no scoring):\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
            _ShortAnswerGradeResponse,
        )
        sa_by_id = {item.question_id: item for item in response.question_results}
        for question in sa_questions:
            item = sa_by_id.get(question.id)
            if item is None:
                sa_results.append(
                    QuestionGradingResult(
                        question_id=question.id,
                        question_type=QuestionType.SHORT_ANSWER,
                        score=0.0,
                        max_score=0.0,
                        is_correct=False,
                        short_answer_detail=None,
                        explanation="No feedback returned for this question.",
                        references=question.references,
                    )
                )
                continue
            item.score = 0.0
            item.max_score = 0.0
            if item.references is None or not item.references:
                item.references = question.references
            sa_results.append(item)
        sa_summary = response.summary

    question_results: list[QuestionGradingResult] = []
    sa_iter = iter(sa_results)
    for question in quiz.questions:
        if isinstance(question, MultipleChoiceQuestion):
            question_results.append(
                next(r for r in mc_results if r.question_id == question.id)
            )
        else:
            question_results.append(next(sa_iter))

    mc_correct = sum(
        1
        for r in question_results
        if r.question_type == QuestionType.MULTIPLE_CHOICE and r.is_correct
    )
    sa_complete = sum(
        1
        for r in question_results
        if r.question_type == QuestionType.SHORT_ANSWER
        and r.short_answer_detail
        and r.short_answer_detail.logic_complete
    )
    summary = (
        f"EZ mode (no scoring): {mc_correct}/{len(mc_results)} single-choice correct. "
        f"Short-answer feedback provided for {len(sa_results)} question(s). "
        f"{sa_summary}".strip()
    )

    return GradingReport(
        total_score=0.0,
        max_score=0.0,
        percentage=0.0,
        summary=summary,
        scoring_enabled=False,
        quiz_mode=QuizMode.EZ,
        question_results=question_results,
    )


def grade_answers(
    quiz: QuizResult,
    answers: UserAnswerSheet,
    llm: LLMClient | None = None,
) -> GradingReport:
    if quiz.mode == QuizMode.EZ:
        return _grade_ez_answers(quiz, answers, llm)

    by_id = _answer_map(answers)
    mc_results: list[QuestionGradingResult] = []
    sa_questions: list[ShortAnswerQuestion] = []

    for question in quiz.questions:
        if isinstance(question, MultipleChoiceQuestion):
            mc_results.append(_grade_multiple_choice(question, by_id.get(question.id)))
        elif isinstance(question, ShortAnswerQuestion):
            sa_questions.append(question)

    sa_results: list[QuestionGradingResult] = []
    sa_summary = ""
    if sa_questions:
        client = llm or LLMClient()
        payload = {
            "short_answer_questions": [
                {
                    **q.model_dump(mode="json"),
                    "max_score": short_answer_max_score(i),
                }
                for i, q in enumerate(sa_questions)
            ],
            "user_answers": [
                {
                    "question_id": q.id,
                    "answer": (by_id[q.id].answer if by_id.get(q.id) else ""),
                }
                for q in sa_questions
            ],
        }
        response = client.complete_json(
            GRADE_SHORT_ANSWER_SYSTEM,
            f"Grade these short-answer responses:\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
            _ShortAnswerGradeResponse,
        )
        sa_by_id = {item.question_id: item for item in response.question_results}
        for index, question in enumerate(sa_questions):
            sa_max = short_answer_max_score(index)
            item = sa_by_id.get(question.id)
            if item is None:
                sa_results.append(
                    QuestionGradingResult(
                        question_id=question.id,
                        question_type=QuestionType.SHORT_ANSWER,
                        score=0.0,
                        max_score=sa_max,
                        is_correct=False,
                        short_answer_detail=None,
                        explanation="No grading result returned for this question.",
                        references=question.references,
                    )
                )
                continue
            item.max_score = sa_max
            item.score = round(max(0.0, min(sa_max, item.score)), 1)
            if item.references is None or not item.references:
                item.references = question.references
            sa_results.append(item)
        sa_summary = response.summary

    question_results: list[QuestionGradingResult] = []
    sa_iter = iter(sa_results)
    for question in quiz.questions:
        if isinstance(question, MultipleChoiceQuestion):
            question_results.append(
                next(r for r in mc_results if r.question_id == question.id)
            )
        else:
            question_results.append(next(sa_iter))

    mc_total = sum(
        r.score
        for r in question_results
        if r.question_type == QuestionType.MULTIPLE_CHOICE
    )
    sa_total = sum(
        r.score
        for r in question_results
        if r.question_type == QuestionType.SHORT_ANSWER
    )
    total_score = round(sum(r.score for r in question_results), 1)
    percentage = round(total_score, 1)

    mc_full = sum(
        1
        for r in question_results
        if r.question_type == QuestionType.MULTIPLE_CHOICE and r.is_correct
    )
    mc_report_max = MC_MAX_SCORE * len(mc_results)
    sa_report_max = sum(SA_MAX_SCORES[: len(sa_results)])
    summary = (
        f"Multiple-choice: {mc_total:.1f}/{mc_report_max:.1f} "
        f"({mc_full}/{len(mc_results)} full credit). "
        f"Short-answer: {sa_total:.1f}/{sa_report_max:.1f}. "
        f"{sa_summary}".strip()
    )

    return GradingReport(
        total_score=total_score,
        max_score=REPORT_MAX_SCORE,
        percentage=percentage,
        summary=summary,
        scoring_enabled=True,
        quiz_mode=QuizMode.NORMAL,
        question_results=question_results,
    )


def save_report(report: GradingReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_answers(path: Path) -> UserAnswerSheet:
    data = json.loads(path.read_text(encoding="utf-8"))
    return UserAnswerSheet.model_validate(data)

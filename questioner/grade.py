"""Step 3: Grade user answers against quiz standard answers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from questioner.i18n import (
    augment_system_prompt_for_language,
    get_output_language_name,
    translate_content,
)
from questioner.literature_format import literature_analysis_is_substantive
from questioner.llm import LLMClient
from questioner.prompts import (
    GRADE_CHOICE_EXPLANATIONS_SYSTEM,
    GRADE_EASY_SHORT_ANSWER_SYSTEM,
    GRADE_SHORT_ANSWER_SYSTEM,
    LOGIC_OPTION_LABELS,
)
from questioner.schemas import (
    ChoiceGradingDetail,
    GradingReport,
    KnowledgeExtractionResult,
    LogicQuestion,
    MultipleChoiceQuestion,
    QuestionGradingResult,
    QuestionType,
    QuizMode,
    QuizResult,
    ShortAnswerGradingDetail,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
    UserAnswer,
    UserAnswerSheet,
)
from questioner.scoring import (
    LOGIC_MAX_SCORE,
    MS_MAX_SCORE,
    SA_MAX_SCORE,
    SINGLE_MAX_SCORE,
    custom_quiz_max_score,
    explain_logic,
    explain_multiple_choice,
    explain_single_choice,
    normal_quiz_max_score,
    question_max_score,
    score_logic_question,
    score_multiple_choice,
    score_single_choice,
    short_answer_max_score,
)


class _ShortAnswerGradeResponse(BaseModel):
    question_results: list[QuestionGradingResult] = Field(default_factory=list)
    summary: str = ""


class _ChoiceRationaleItem(BaseModel):
    question_id: str
    issue_rationales: dict[str, str] = Field(default_factory=dict)
    pdf_rationales: dict[str, str] = Field(default_factory=dict)


class _ChoiceRationaleResponse(BaseModel):
    questions: list[_ChoiceRationaleItem] = Field(default_factory=list)


def _answer_map(sheet: UserAnswerSheet) -> dict[str, UserAnswer]:
    return {item.question_id: item for item in sheet.answers}


def _maybe_translate(text: str, language: str) -> str:
    if language == "en" or not text.strip():
        return text
    return translate_content(text, language)


def _selected_list(user_answer: UserAnswer | None) -> list[str]:
    if not user_answer or not isinstance(user_answer.answer, list):
        return []
    return user_answer.answer


def _compute_short_answer_score(
    question: ShortAnswerQuestion,
    detail: ShortAnswerGradingDetail,
    max_score: float,
) -> float:
    keywords = question.grading_keywords
    if keywords:
        matched = len(detail.matched_keywords)
        keyword_base = (matched / len(keywords)) * max_score
    else:
        keyword_base = max_score if detail.logic_complete else 0.0

    penalties = 0.0
    if detail.logic_error:
        penalties += 10.0
    if detail.concept_confusion:
        penalties += 10.0
    return round(max(0.0, min(max_score, keyword_base - penalties)), 1)


def _grade_scored_choice(
    question: SingleChoiceQuestion | MultipleChoiceQuestion | LogicQuestion,
    user_answer: UserAnswer | None,
    language: str,
) -> QuestionGradingResult:
    """Grade choice questions deterministically — no LLM tokens."""
    selected = _selected_list(user_answer)
    if isinstance(question, SingleChoiceQuestion):
        score, detail, is_correct = score_single_choice(question, selected)
        max_score = SINGLE_MAX_SCORE
        qtype = QuestionType.SINGLE_CHOICE
        explanation = explain_single_choice(question, detail, score)
    elif isinstance(question, LogicQuestion):
        score, detail, is_correct = score_logic_question(question, selected)
        max_score = LOGIC_MAX_SCORE
        qtype = QuestionType.LOGIC
        explanation = explain_logic(detail, score)
    else:
        score, detail, is_correct = score_multiple_choice(question, selected)
        max_score = MS_MAX_SCORE
        qtype = QuestionType.MULTIPLE_CHOICE
        explanation = explain_multiple_choice(question, detail, score)

    return QuestionGradingResult(
        question_id=question.id,
        question_type=qtype,
        score=round(score, 1),
        max_score=max_score,
        is_correct=is_correct,
        choice_detail=detail,
        explanation=explanation,
        references=question.references,
    )


def _grade_easy_choice(
    question: SingleChoiceQuestion,
    user_answer: UserAnswer | None,
    language: str,
) -> QuestionGradingResult:
    selected = _selected_list(user_answer)
    correct = question.correct_answer
    is_correct = set(selected) == {correct}
    wrong = sorted(set(selected) - {correct})
    missed = [] if is_correct else [correct]
    detail = ChoiceGradingDetail(
        user_answers=sorted(selected),
        correct_answers=[correct],
        missed=missed,
        wrong=wrong,
        is_correct=is_correct,
    )
    explanation = explain_single_choice(
        question, detail, SINGLE_MAX_SCORE if is_correct else 0.0
    )

    return QuestionGradingResult(
        question_id=question.id,
        question_type=QuestionType.SINGLE_CHOICE,
        score=0.0,
        max_score=0.0,
        is_correct=is_correct,
        choice_detail=detail,
        explanation=explanation,
        references=question.references,
    )


def _grade_short_answers_llm(
    sa_questions: list[ShortAnswerQuestion],
    by_id: dict[str, UserAnswer],
    llm: LLMClient,
    language: str,
    *,
    easy: bool = False,
) -> tuple[list[QuestionGradingResult], str]:
    if not sa_questions:
        return [], ""

    payload = {
        "output_language": get_output_language_name(language),
        "short_answer_questions": [
            {
                **q.model_dump(mode="json"),
                "max_score": 0 if easy else short_answer_max_score(i),
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
    system = GRADE_EASY_SHORT_ANSWER_SYSTEM if easy else GRADE_SHORT_ANSWER_SYSTEM
    response = llm.complete_json(
        augment_system_prompt_for_language(system, language),
        f"{'Review' if easy else 'Grade'} in {payload['output_language']}:\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
        _ShortAnswerGradeResponse,
    )

    sa_by_id = {item.question_id: item for item in response.question_results}
    results: list[QuestionGradingResult] = []
    for index, question in enumerate(sa_questions):
        sa_max = 0.0 if easy else short_answer_max_score(index)
        item = sa_by_id.get(question.id)
        if item is None:
            results.append(
                QuestionGradingResult(
                    question_id=question.id,
                    question_type=QuestionType.SHORT_ANSWER,
                    score=0.0,
                    max_score=sa_max,
                    is_correct=False,
                    explanation=_maybe_translate("No grading result returned.", language),
                    references=question.references,
                )
            )
            continue
        item.max_score = sa_max
        if not easy and item.short_answer_detail:
            item.score = _compute_short_answer_score(
                question, item.short_answer_detail, sa_max
            )
            item.is_correct = item.score >= sa_max
        elif not easy:
            item.score = round(max(0.0, min(sa_max, item.score)), 1)
        else:
            item.score = 0.0
        if not item.references:
            item.references = question.references
        results.append(item)
    return results, response.summary


def _choice_question_payload(
    question: SingleChoiceQuestion | MultipleChoiceQuestion | LogicQuestion,
    result: QuestionGradingResult,
) -> dict | None:
    detail = result.choice_detail
    if detail is None or (not detail.missed and not detail.wrong):
        return None

    payload: dict = {
        "question_id": question.id,
        "type": question.type.value,
        "correct_answers": detail.correct_answers,
        "user_answers": detail.user_answers,
        "missed_keys": detail.missed,
        "wrong_keys": detail.wrong,
        "references": [r.model_dump(mode="json") for r in question.references],
        "author_explanation": question.explanation,
    }
    if isinstance(question, LogicQuestion):
        payload["description_alpha"] = question.description_alpha
        payload["description_beta"] = question.description_beta
        payload["logic_options"] = LOGIC_OPTION_LABELS
    else:
        payload["stem"] = question.stem
        payload["options"] = question.options
    return payload


def _enrich_choice_rationales(
    quiz: QuizResult,
    results: list[QuestionGradingResult],
    llm: LLMClient,
    language: str,
    knowledge: KnowledgeExtractionResult | None = None,
) -> None:
    quiz_map = {q.id: q for q in quiz.questions}
    payloads: list[dict] = []
    for result in results:
        question = quiz_map.get(result.question_id)
        if question is None or not isinstance(
            question, (SingleChoiceQuestion, MultipleChoiceQuestion, LogicQuestion)
        ):
            continue
        item = _choice_question_payload(question, result)
        if item:
            payloads.append(item)

    if not payloads:
        return

    context: dict = {
        "output_language": get_output_language_name(language),
        "questions": payloads,
    }
    if knowledge and literature_analysis_is_substantive(knowledge.literature_analysis):
        context["literature_analysis"] = knowledge.literature_analysis.model_dump(mode="json")
    elif knowledge and knowledge.knowledge_points:
        context["knowledge_points"] = [
            {
                "id": kp.id,
                "title": kp.title,
                "content": kp.content,
                "source_quote": kp.source_quote,
            }
            for kp in knowledge.knowledge_points
        ]

    response = llm.complete_json(
        augment_system_prompt_for_language(GRADE_CHOICE_EXPLANATIONS_SYSTEM, language),
        f"Write option rationales in {context['output_language']}:\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}",
        _ChoiceRationaleResponse,
    )
    by_id = {item.question_id: item for item in response.questions}
    for result in results:
        item = by_id.get(result.question_id)
        if item is None or result.choice_detail is None:
            continue
        result.choice_detail.option_issue_rationales = {
            key: _maybe_translate(text, language)
            for key, text in item.issue_rationales.items()
        }
        result.choice_detail.option_pdf_rationales = {
            key: _maybe_translate(text, language)
            for key, text in item.pdf_rationales.items()
        }


def _compute_max_score(quiz: QuizResult) -> float:
    if quiz.mode == QuizMode.EASY:
        return 0.0
    if quiz.mode == QuizMode.CUSTOM and quiz.custom_counts:
        return custom_quiz_max_score(quiz.custom_counts)
    if quiz.mode == QuizMode.NORMAL:
        return normal_quiz_max_score()
    return sum(question_max_score(q, quiz.mode) for q in quiz.questions)


def _grade_easy(
    quiz: QuizResult,
    answers: UserAnswerSheet,
    llm: LLMClient | None,
    language: str,
    knowledge: KnowledgeExtractionResult | None = None,
) -> GradingReport:
    by_id = _answer_map(answers)
    results: list[QuestionGradingResult] = []
    sa_questions: list[ShortAnswerQuestion] = []

    for question in quiz.questions:
        if isinstance(question, SingleChoiceQuestion):
            results.append(_grade_easy_choice(question, by_id.get(question.id), language))
        elif isinstance(question, ShortAnswerQuestion):
            sa_questions.append(question)

    if sa_questions:
        client = llm or LLMClient()
        sa_results, sa_summary = _grade_short_answers_llm(
            sa_questions, by_id, client, language, easy=True
        )
    else:
        sa_results, sa_summary = [], ""

    ordered: list[QuestionGradingResult] = []
    sa_iter = iter(sa_results)
    for question in quiz.questions:
        if isinstance(question, SingleChoiceQuestion):
            ordered.append(next(r for r in results if r.question_id == question.id))
        else:
            ordered.append(next(sa_iter))

    mc_ok = sum(1 for r in ordered if r.is_correct and r.question_type != QuestionType.SHORT_ANSWER)
    summary = _maybe_translate(
        f"Easy mode (no scoring): {mc_ok} single-choice correct. {sa_summary}".strip(),
        language,
    )
    client = llm or LLMClient()
    _enrich_choice_rationales(quiz, ordered, client, language, knowledge)
    for result in ordered:
        if result.explanation:
            result.explanation = _maybe_translate(result.explanation, language)
    return GradingReport(
        total_score=0.0,
        max_score=0.0,
        percentage=0.0,
        summary=summary,
        scoring_enabled=False,
        quiz_mode=QuizMode.EASY,
        question_results=ordered,
    )


def grade_answers(
    quiz: QuizResult,
    answers: UserAnswerSheet,
    llm: LLMClient | None = None,
    language: str = "en",
    knowledge: KnowledgeExtractionResult | None = None,
) -> GradingReport:
    if quiz.mode == QuizMode.EASY:
        return _grade_easy(quiz, answers, llm, language, knowledge)

    by_id = _answer_map(answers)
    choice_results: list[QuestionGradingResult] = []
    sa_questions: list[ShortAnswerQuestion] = []

    for question in quiz.questions:
        if isinstance(question, (SingleChoiceQuestion, MultipleChoiceQuestion, LogicQuestion)):
            choice_results.append(
                _grade_scored_choice(question, by_id.get(question.id), language)
            )
        elif isinstance(question, ShortAnswerQuestion):
            sa_questions.append(question)

    if sa_questions:
        client = llm or LLMClient()
        sa_results, sa_summary = _grade_short_answers_llm(
            sa_questions, by_id, client, language, easy=False
        )
    else:
        sa_results, sa_summary = [], ""

    client = llm or LLMClient()
    _enrich_choice_rationales(quiz, choice_results, client, language, knowledge)

    for result in choice_results:
        if result.explanation:
            result.explanation = _maybe_translate(result.explanation, language)

    ordered: list[QuestionGradingResult] = []
    sa_iter = iter(sa_results)
    for question in quiz.questions:
        if isinstance(question, ShortAnswerQuestion):
            ordered.append(next(sa_iter))
        else:
            ordered.append(next(r for r in choice_results if r.question_id == question.id))

    total_score = round(sum(r.score for r in ordered), 1)
    max_score = _compute_max_score(quiz)
    percentage = round(total_score / max_score * 100, 1) if max_score else 0.0

    mc_total = sum(r.score for r in ordered if r.question_type == QuestionType.MULTIPLE_CHOICE)
    logic_total = sum(r.score for r in ordered if r.question_type == QuestionType.LOGIC)
    sc_total = sum(r.score for r in ordered if r.question_type == QuestionType.SINGLE_CHOICE)
    sa_total = sum(r.score for r in ordered if r.question_type == QuestionType.SHORT_ANSWER)

    summary = _maybe_translate(
        (
            f"Single-choice: {sc_total:.1f}; Multi-select: {mc_total:.1f}; "
            f"Logic: {logic_total:.1f}; Short-answer: {sa_total:.1f}. {sa_summary}"
        ).strip(),
        language,
    )

    return GradingReport(
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        summary=summary,
        scoring_enabled=True,
        quiz_mode=quiz.mode,
        question_results=ordered,
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

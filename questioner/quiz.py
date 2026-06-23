"""Step 2: Generate quiz questions from knowledge points."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from questioner.i18n import augment_system_prompt_for_language, get_output_language_name
from questioner.llm import LLMClient
from questioner.prompts import QUIZ_EASY_SYSTEM, QUIZ_NORMAL_SYSTEM, build_custom_quiz_system
from questioner.schemas import (
    CustomQuizCounts,
    KnowledgeExtractionResult,
    LOGIC_OPTION_KEYS,
    LogicQuestion,
    MultipleChoiceQuestion,
    QuestionType,
    QuizMode,
    QuizResult,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
)
from questioner.scoring import (
    EASY_SA_COUNT,
    EASY_SC_COUNT,
    MS_OPTION_KEYS,
    NORMAL_LOGIC_COUNT,
    NORMAL_MS_COUNT,
    NORMAL_SA_COUNT,
    SC_OPTION_KEYS,
)


class _QuizLLMResponse(BaseModel):
    questions: list[
        SingleChoiceQuestion
        | MultipleChoiceQuestion
        | LogicQuestion
        | ShortAnswerQuestion
    ] = Field(default_factory=list)


def _validate_quiz_questions(
    questions: list[
        SingleChoiceQuestion
        | MultipleChoiceQuestion
        | LogicQuestion
        | ShortAnswerQuestion
    ],
    mode: QuizMode,
    custom_counts: CustomQuizCounts | None = None,
) -> None:
    sc = [q for q in questions if q.type == QuestionType.SINGLE_CHOICE]
    ms = [q for q in questions if q.type == QuestionType.MULTIPLE_CHOICE]
    lg = [q for q in questions if q.type == QuestionType.LOGIC]
    sa = [q for q in questions if q.type == QuestionType.SHORT_ANSWER]

    if mode == QuizMode.EASY:
        exp_sc, exp_sa = EASY_SC_COUNT, EASY_SA_COUNT
        if len(sc) != exp_sc or len(sa) != exp_sa or ms or lg:
            raise ValueError(
                f"Easy mode requires {exp_sc} single-choice + {exp_sa} short-answer; "
                f"got SC={len(sc)}, MS={len(ms)}, Logic={len(lg)}, SA={len(sa)}."
            )
    elif mode == QuizMode.NORMAL:
        if (
            len(ms) != NORMAL_MS_COUNT
            or len(lg) != NORMAL_LOGIC_COUNT
            or len(sa) != NORMAL_SA_COUNT
            or sc
        ):
            raise ValueError(
                f"Normal mode requires {NORMAL_MS_COUNT} multi-select + "
                f"{NORMAL_LOGIC_COUNT} logic + {NORMAL_SA_COUNT} short-answer."
            )
    elif mode == QuizMode.CUSTOM and custom_counts:
        if (
            len(sc) != custom_counts.single_choice
            or len(ms) != custom_counts.multiple_choice
            or len(lg) != custom_counts.logic
            or len(sa) != custom_counts.short_answer
        ):
            raise ValueError(
                f"Custom counts mismatch: expected "
                f"SC={custom_counts.single_choice}, MS={custom_counts.multiple_choice}, "
                f"Logic={custom_counts.logic}, SA={custom_counts.short_answer}; "
                f"got SC={len(sc)}, MS={len(ms)}, Logic={len(lg)}, SA={len(sa)}."
            )

    for q in sc:
        if set(q.options.keys()) != set(SC_OPTION_KEYS):
            raise ValueError(f"{q.id} must have options A–D.")
        if q.correct_answer not in SC_OPTION_KEYS:
            raise ValueError(f"{q.id} invalid correct_answer {q.correct_answer}.")

    for q in ms:
        if set(q.options.keys()) != set(MS_OPTION_KEYS):
            raise ValueError(f"{q.id} must have options A–E.")
        invalid = [k for k in q.correct_answers if k not in MS_OPTION_KEYS]
        if invalid:
            raise ValueError(f"{q.id} invalid correct_answers: {invalid}.")

    for q in lg:
        if q.correct_answer not in LOGIC_OPTION_KEYS:
            raise ValueError(f"{q.id} invalid logic correct_answer {q.correct_answer}.")


def generate_quiz(
    knowledge: KnowledgeExtractionResult,
    llm: LLMClient | None = None,
    mode: QuizMode = QuizMode.NORMAL,
    language: str = "en",
    custom_counts: CustomQuizCounts | None = None,
) -> QuizResult:
    if not knowledge.has_substantive_content or not knowledge.knowledge_points:
        raise ValueError(
            "Knowledge points are empty or lack substantive content; cannot generate quiz."
        )

    client = llm or LLMClient()
    payload = {
        "output_language": get_output_language_name(language),
        "entities": knowledge.entities,
        "knowledge_points": [kp.model_dump(mode="json") for kp in knowledge.knowledge_points],
        "summary": knowledge.summary,
    }

    if mode == QuizMode.EASY:
        base_prompt = QUIZ_EASY_SYSTEM
    elif mode == QuizMode.CUSTOM:
        if custom_counts is None:
            raise ValueError("Custom mode requires custom_counts.")
        base_prompt = build_custom_quiz_system(custom_counts.model_dump())
        payload["custom_counts"] = custom_counts.model_dump()
    else:
        base_prompt = QUIZ_NORMAL_SYSTEM

    system_prompt = augment_system_prompt_for_language(base_prompt, language)
    response = client.complete_json(
        system_prompt,
        f"Generate questions in {payload['output_language']}:\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
        _QuizLLMResponse,
    )

    _validate_quiz_questions(response.questions, mode, custom_counts)

    return QuizResult(
        knowledge_source=knowledge.source_text_preview,
        mode=mode,
        custom_counts=custom_counts,
        questions=response.questions,
    )


def save_quiz(result: QuizResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_quiz(path: Path) -> QuizResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return QuizResult.model_validate(data)

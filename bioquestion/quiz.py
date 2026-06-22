"""Step 2: Generate quiz questions from knowledge points."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from bioquestion.llm import LLMClient
from bioquestion.prompts import QUIZ_EZ_SYSTEM, QUIZ_SYSTEM
from bioquestion.schemas import (
    KnowledgeExtractionResult,
    MultipleChoiceQuestion,
    QuestionType,
    QuizMode,
    QuizResult,
    ShortAnswerQuestion,
)
from bioquestion.scoring import (
    EZ_MC_COUNT,
    EZ_MC_OPTION_KEYS,
    EZ_SA_COUNT,
    MC_COUNT,
    MC_OPTION_KEYS,
    SA_COUNT,
)


class _QuizLLMResponse(BaseModel):
    questions: list[MultipleChoiceQuestion | ShortAnswerQuestion] = Field(
        default_factory=list
    )


def _validate_quiz_questions(
    questions: list[MultipleChoiceQuestion | ShortAnswerQuestion],
    mode: QuizMode = QuizMode.NORMAL,
) -> None:
    mc = [q for q in questions if q.type == QuestionType.MULTIPLE_CHOICE]
    sa = [q for q in questions if q.type == QuestionType.SHORT_ANSWER]

    if mode == QuizMode.EZ:
        expected_mc, expected_sa = EZ_MC_COUNT, EZ_SA_COUNT
        option_keys = EZ_MC_OPTION_KEYS
    else:
        expected_mc, expected_sa = MC_COUNT, SA_COUNT
        option_keys = MC_OPTION_KEYS

    if len(mc) != expected_mc or len(sa) != expected_sa:
        raise ValueError(
            f"Invalid question count: multi-select {len(mc)}/{expected_mc}, "
            f"short-answer {len(sa)}/{expected_sa}."
        )

    for q in mc:
        if not isinstance(q, MultipleChoiceQuestion):
            continue
        if set(q.options.keys()) != set(option_keys):
            raise ValueError(
                f"{q.id} must have exactly options {', '.join(option_keys)}; "
                f"got {sorted(q.options.keys())}."
            )
        invalid = [key for key in q.correct_answers if key not in option_keys]
        if invalid:
            raise ValueError(f"{q.id} has invalid correct_answers: {invalid}.")
        if mode == QuizMode.EZ and len(q.correct_answers) != 1:
            raise ValueError(
                f"{q.id} must have exactly one correct answer in EZ mode; "
                f"got {q.correct_answers}."
            )


def generate_quiz(
    knowledge: KnowledgeExtractionResult,
    llm: LLMClient | None = None,
    mode: QuizMode = QuizMode.NORMAL,
) -> QuizResult:
    if not knowledge.has_substantive_content or not knowledge.knowledge_points:
        raise ValueError(
            "Knowledge points are empty or lack substantive content; cannot generate quiz."
        )

    client = llm or LLMClient()
    payload = {
        "entities": knowledge.entities,
        "knowledge_points": [kp.model_dump(mode="json") for kp in knowledge.knowledge_points],
        "summary": knowledge.summary,
    }
    system_prompt = QUIZ_EZ_SYSTEM if mode == QuizMode.EZ else QUIZ_SYSTEM
    response = client.complete_json(
        system_prompt,
        f"Generate questions based on the following knowledge points:\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        _QuizLLMResponse,
    )

    _validate_quiz_questions(response.questions, mode)

    return QuizResult(
        knowledge_source=knowledge.source_text_preview,
        mode=mode,
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

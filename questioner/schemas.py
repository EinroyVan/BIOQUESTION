"""Pydantic models for the three-step natural-science literature workflow."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class KnowledgeCategory(str, Enum):
    ENTITY = "entity"
    MECHANISM = "mechanism"
    FINDING = "finding"


_CATEGORY_ALIASES: dict[str, str] = {
    "entity": "entity",
    "entities": "entity",
    "concept": "entity",
    "实体": "entity",
    "概念": "entity",
    "mechanism": "mechanism",
    "mechanisms": "mechanism",
    "process": "mechanism",
    "机制": "mechanism",
    "机理": "mechanism",
    "finding": "finding",
    "findings": "finding",
    "conclusion": "finding",
    "result": "finding",
    "发现": "finding",
    "结论": "finding",
    "结果": "finding",
}


def normalize_knowledge_category(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[stripped]
    lowered = stripped.lower()
    return _CATEGORY_ALIASES.get(lowered, stripped)


class KnowledgePoint(BaseModel):
    id: str
    category: KnowledgeCategory
    title: str
    content: str
    source_quote: str

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: object) -> object:
        return normalize_knowledge_category(value)

    @field_validator("source_quote", mode="before")
    @classmethod
    def _truncate_source_quote(cls, value: object) -> object:
        if isinstance(value, str) and len(value) > 200:
            return value[:200]
        return value

    @field_validator("title", "content", mode="before")
    @classmethod
    def _coerce_text_fields(cls, value: object) -> object:
        if value is None:
            return ""
        return value


class KnowledgeExtractionResult(BaseModel):
    source_text_preview: str = Field(
        description="First 200 characters of the input text for traceability."
    )
    has_substantive_content: bool = True
    entities: list[str] = Field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    summary: str = ""


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    LOGIC = "logic"
    SHORT_ANSWER = "short_answer"


class QuizMode(str, Enum):
    NORMAL = "normal"
    EASY = "easy"
    CUSTOM = "custom"

    @classmethod
    def _missing_(cls, value: object) -> QuizMode | None:
        if value == "ez":
            return cls.EASY
        return None


class Reference(BaseModel):
    knowledge_point_id: str
    source_quote: str


LOGIC_OPTION_KEYS = ("A", "B", "C", "D", "E")


class SingleChoiceQuestion(BaseModel):
    id: str
    type: Literal[QuestionType.SINGLE_CHOICE] = QuestionType.SINGLE_CHOICE
    stem: str
    options: dict[str, str]
    correct_answer: str
    explanation: str = ""
    references: list[Reference] = Field(default_factory=list)


class MultipleChoiceQuestion(BaseModel):
    id: str
    type: Literal[QuestionType.MULTIPLE_CHOICE] = QuestionType.MULTIPLE_CHOICE
    stem: str
    options: dict[str, str]
    correct_answers: list[str]
    explanation: str = ""
    references: list[Reference] = Field(default_factory=list)


class LogicQuestion(BaseModel):
    id: str
    type: Literal[QuestionType.LOGIC] = QuestionType.LOGIC
    stem: str = ""
    description_alpha: str
    description_beta: str
    correct_answer: str
    explanation: str = ""
    references: list[Reference] = Field(default_factory=list)


class ShortAnswerQuestion(BaseModel):
    id: str
    type: Literal[QuestionType.SHORT_ANSWER] = QuestionType.SHORT_ANSWER
    stem: str
    standard_answer: str
    grading_keywords: list[str] = Field(default_factory=list)
    logic_chain: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)


Question = SingleChoiceQuestion | MultipleChoiceQuestion | LogicQuestion | ShortAnswerQuestion


class CustomQuizCounts(BaseModel):
    single_choice: int = 0
    multiple_choice: int = 0
    logic: int = 0
    short_answer: int = 0


class QuizResult(BaseModel):
    knowledge_source: str = ""
    mode: QuizMode = QuizMode.NORMAL
    custom_counts: CustomQuizCounts | None = None
    questions: list[Question] = Field(default_factory=list)


class UserAnswer(BaseModel):
    question_id: str
    answer: str | list[str]


class UserAnswerSheet(BaseModel):
    answers: list[UserAnswer] = Field(default_factory=list)


class ChoiceGradingDetail(BaseModel):
    user_answers: list[str]
    correct_answers: list[str]
    missed: list[str] = Field(default_factory=list)
    extra: list[str] = Field(default_factory=list)
    wrong: list[str] = Field(default_factory=list)
    is_correct: bool = False


class ShortAnswerGradingDetail(BaseModel):
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    logic_complete: bool = False
    feedback: str = ""


class QuestionGradingResult(BaseModel):
    question_id: str
    question_type: QuestionType
    score: float
    max_score: float
    is_correct: bool | None = None
    choice_detail: ChoiceGradingDetail | None = None
    short_answer_detail: ShortAnswerGradingDetail | None = None
    explanation: str = ""
    references: list[Reference] = Field(default_factory=list)


class GradingReport(BaseModel):
    total_score: float
    max_score: float = 100.0
    percentage: float
    summary: str = ""
    scoring_enabled: bool = True
    quiz_mode: QuizMode = QuizMode.NORMAL
    question_results: list[QuestionGradingResult] = Field(default_factory=list)

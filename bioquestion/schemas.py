"""Pydantic models for the three-step biomedical literature workflow."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeCategory(str, Enum):
    ENTITY = "entity"
    MECHANISM = "mechanism"
    FINDING = "finding"


class KnowledgePoint(BaseModel):
    id: str
    category: KnowledgeCategory
    title: str
    content: str
    source_quote: str


class KnowledgeExtractionResult(BaseModel):
    source_text_preview: str = Field(
        description="First 200 characters of the input text for traceability."
    )
    has_substantive_content: bool = True
    entities: list[str] = Field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    summary: str = ""


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"


class QuizMode(str, Enum):
    NORMAL = "normal"
    EZ = "ez"


class Reference(BaseModel):
    knowledge_point_id: str
    source_quote: str


class MultipleChoiceQuestion(BaseModel):
    id: str
    type: Literal[QuestionType.MULTIPLE_CHOICE] = QuestionType.MULTIPLE_CHOICE
    stem: str
    options: dict[str, str]
    correct_answers: list[str]
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


class QuizResult(BaseModel):
    knowledge_source: str = ""
    mode: QuizMode = QuizMode.NORMAL
    questions: list[MultipleChoiceQuestion | ShortAnswerQuestion] = Field(
        default_factory=list
    )


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

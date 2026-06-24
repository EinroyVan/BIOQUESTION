"""Step 1: Extract structured literature analysis from natural-science text."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from questioner.i18n import augment_system_prompt_for_language
from questioner.literature_format import literature_analysis_is_substantive
from questioner.llm import LLMClient
from questioner.metadata_format import merge_pdf_document_metadata
from questioner.prompts import EXTRACT_SYSTEM
from questioner.schemas import KnowledgeExtractionResult, LiteratureAnalysis, LiteratureMetadata

MAX_INPUT_CHARS = 18000


class _ExtractLLMResponse(BaseModel):
    has_substantive_content: bool = True
    literature_analysis: LiteratureAnalysis = Field(default_factory=LiteratureAnalysis)
    literature_metadata: LiteratureMetadata = Field(default_factory=LiteratureMetadata)


def _trim_input(text: str) -> str:
    if len(text) <= MAX_INPUT_CHARS:
        return text
    return (
        text[:MAX_INPUT_CHARS]
        + "\n\n[Note: text truncated due to length; extract the most important content from the excerpt above.]"
    )


def extract_knowledge(
    text: str,
    llm: LLMClient | None = None,
    language: str = "en",
    *,
    pdf_title: str = "",
    pdf_author: str = "",
) -> KnowledgeExtractionResult:
    client = llm or LLMClient()
    trimmed = _trim_input(text.strip())
    preview = trimmed[:200] + ("..." if len(trimmed) > 200 else "")
    system = augment_system_prompt_for_language(EXTRACT_SYSTEM, language)
    response = client.complete_json(
        system,
        f"Analyze the following natural-science literature excerpt:\n\n{trimmed}",
        _ExtractLLMResponse,
    )
    substantive = response.has_substantive_content and literature_analysis_is_substantive(
        response.literature_analysis
    )
    metadata = merge_pdf_document_metadata(
        response.literature_metadata,
        pdf_title=pdf_title,
        pdf_author=pdf_author,
    )
    return KnowledgeExtractionResult(
        source_text_preview=preview,
        has_substantive_content=substantive,
        literature_analysis=response.literature_analysis,
        literature_metadata=metadata,
    )


def save_knowledge(result: KnowledgeExtractionResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_knowledge(path: Path) -> KnowledgeExtractionResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return KnowledgeExtractionResult.model_validate(data)

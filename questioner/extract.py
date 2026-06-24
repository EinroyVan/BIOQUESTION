"""Step 1: Extract knowledge points from natural-science literature."""

from __future__ import annotations

import json
from pathlib import Path

from typing import Any

from pydantic import BaseModel, Field, model_validator

from questioner.i18n import augment_system_prompt_for_language
from questioner.llm import LLMClient
from questioner.prompts import EXTRACT_SYSTEM
from questioner.schemas import KnowledgeExtractionResult, KnowledgePoint

MAX_INPUT_CHARS = 18000


class _ExtractLLMResponse(BaseModel):
    has_substantive_content: bool = True
    entities: list[str] = Field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        fixed_kps: list[object] = []
        for index, item in enumerate(data.get("knowledge_points") or [], start=1):
            if not isinstance(item, dict):
                fixed_kps.append(item)
                continue
            kp = dict(item)
            if not str(kp.get("id", "")).strip():
                kp["id"] = f"KP-{index}"
            fixed_kps.append(kp)
        data = dict(data)
        data["knowledge_points"] = fixed_kps
        return data


def _trim_input(text: str) -> str:
    if len(text) <= MAX_INPUT_CHARS:
        return text
    return (
        text[:MAX_INPUT_CHARS]
        + "\n\n[Note: text truncated due to length; extract the most important knowledge points from the excerpt above.]"
    )


def extract_knowledge(
    text: str,
    llm: LLMClient | None = None,
    language: str = "en",
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
    return KnowledgeExtractionResult(
        source_text_preview=preview,
        has_substantive_content=response.has_substantive_content,
        entities=response.entities,
        knowledge_points=response.knowledge_points,
        summary=response.summary,
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

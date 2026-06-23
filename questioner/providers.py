"""LLM provider registry and environment-variable mapping."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class LLMProvider(str, Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPAT = "openai_compatible"


@dataclass(frozen=True)
class ProviderSpec:
    provider: LLMProvider
    label: str
    api_key_env: str
    model_env: str
    base_url_env: str | None
    default_model: str
    docs_hint: str


PROVIDER_SPECS: dict[LLMProvider, ProviderSpec] = {
    LLMProvider.GOOGLE: ProviderSpec(
        provider=LLMProvider.GOOGLE,
        label="Google Gemini",
        api_key_env="GOOGLE_API_KEY",
        model_env="GOOGLE_MODEL",
        base_url_env=None,
        default_model="gemini-3.5-flash",
        docs_hint="https://aistudio.google.com/apikey",
    ),
    LLMProvider.OPENAI: ProviderSpec(
        provider=LLMProvider.OPENAI,
        label="OpenAI",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        base_url_env="OPENAI_BASE_URL",
        default_model="gpt-4o",
        docs_hint="https://platform.openai.com/api-keys",
    ),
    LLMProvider.ANTHROPIC: ProviderSpec(
        provider=LLMProvider.ANTHROPIC,
        label="Anthropic Claude",
        api_key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_MODEL",
        base_url_env=None,
        default_model="claude-sonnet-4-20250514",
        docs_hint="https://console.anthropic.com/",
    ),
    LLMProvider.OPENAI_COMPAT: ProviderSpec(
        provider=LLMProvider.OPENAI_COMPAT,
        label="OpenAI-compatible",
        api_key_env="OPENAI_COMPAT_API_KEY",
        model_env="OPENAI_COMPAT_MODEL",
        base_url_env="OPENAI_COMPAT_BASE_URL",
        default_model="deepseek-chat",
        docs_hint="DeepSeek, Ollama, local gateways, etc.",
    ),
}


def get_provider_spec(provider: LLMProvider | str) -> ProviderSpec:
    if isinstance(provider, str):
        provider = LLMProvider(provider)
    return PROVIDER_SPECS[provider]


def resolve_provider_config(
    provider: LLMProvider | str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> tuple[str, str, str | None]:
    spec = get_provider_spec(provider)
    resolved_key = (api_key or os.getenv(spec.api_key_env, "")).strip()
    resolved_model = (model or os.getenv(spec.model_env) or spec.default_model).strip()
    resolved_base: str | None = None
    if spec.base_url_env:
        resolved_base = (base_url or os.getenv(spec.base_url_env) or "").strip() or None
        if provider == LLMProvider.OPENAI and not resolved_base:
            resolved_base = "https://api.openai.com/v1"
    return resolved_key, resolved_model, resolved_base


def provider_is_configured(provider: LLMProvider | str) -> bool:
    spec = get_provider_spec(provider)
    return bool(os.getenv(spec.api_key_env, "").strip())

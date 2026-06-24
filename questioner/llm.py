"""Multi-provider LLM client with JSON structured output."""

from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from questioner import load_project_env
from questioner.providers import (
    LLMProvider,
    get_provider_spec,
    resolve_provider_config,
)

load_project_env()

T = TypeVar("T", bound=BaseModel)

_JSON_RETRY_HINT = (
    "\n\n[Important] Previous output was invalid JSON. Reply again with: "
    "1) strictly valid JSON; 2) escaped double quotes inside strings; "
    "3) no trailing commas; 4) source_quote max 200 characters."
)


def _extract_json_blob(text: str) -> str:
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        return fence_match.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _parse_json_text(text: str) -> dict | list:
    blob = _extract_json_blob(text)
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        try:
            import json_repair

            return json_repair.loads(blob)
        except Exception as exc:
            raise json.JSONDecodeError(
                f"Could not parse model JSON output: {exc}",
                blob,
                0,
            ) from exc


class LLMClient:
    def __init__(
        self,
        provider: LLMProvider | str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        provider_name = provider or os.getenv("LLM_PROVIDER", LLMProvider.GOOGLE.value)
        self.provider = LLMProvider(provider_name)
        self.spec = get_provider_spec(self.provider)
        self.api_key, self.model, self.base_url = resolve_provider_config(
            self.provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        self._google_client = None
        self._openai_client = None
        self._anthropic_client = None

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                f"{self.spec.api_key_env} is not configured for {self.spec.label}. "
                "Copy .env.example to .env and set the key, or choose another provider in the sidebar."
            )

    def _generate_google(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_schema: dict | None = None,
    ) -> str:
        from google import genai
        from google.genai import types

        if self._google_client is None:
            self._google_client = genai.Client(api_key=self.api_key)
        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "temperature": 0.2,
            "max_output_tokens": 8192,
        }
        if json_schema is not None:
            config_kwargs["response_json_schema"] = json_schema
        response = self._google_client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return response.text or "{}"

    def _generate_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_schema: dict | None = None,
    ) -> str:
        from openai import OpenAI

        if self._openai_client is None:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._openai_client = OpenAI(**kwargs)
        if json_schema is not None and self.provider == LLMProvider.OPENAI:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema.get("title", "response"),
                    "schema": json_schema,
                    "strict": True,
                },
            }
        else:
            response_format = {"type": "json_object"}
        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_format,
            temperature=0.2,
            max_tokens=8192,
        )
        return response.choices[0].message.content or "{}"

    def _generate_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.Anthropic(api_key=self.api_key)
        response = self._anthropic_client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system_prompt + "\n\nReply with JSON only.",
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
        )
        parts = [block.text for block in response.content if block.type == "text"]
        return "".join(parts) or "{}"

    def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_schema: dict | None = None,
    ) -> str:
        self._require_api_key()
        if self.provider == LLMProvider.GOOGLE:
            return self._generate_google(
                system_prompt, user_prompt, json_schema=json_schema
            )
        if self.provider in (LLMProvider.OPENAI, LLMProvider.OPENAI_COMPAT):
            return self._generate_openai(
                system_prompt, user_prompt, json_schema=json_schema
            )
        if self.provider == LLMProvider.ANTHROPIC:
            return self._generate_anthropic(system_prompt, user_prompt)
        raise RuntimeError(f"Unsupported provider: {self.provider}")

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        *,
        max_retries: int = 2,
    ) -> T:
        last_error: Exception | None = None
        prompt = user_prompt
        json_schema = schema.model_json_schema()

        for attempt in range(max_retries + 1):
            try:
                content = self._generate(
                    system_prompt, prompt, json_schema=json_schema
                )
                data = _parse_json_text(content)
                return schema.model_validate(data)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt < max_retries:
                    prompt = user_prompt + _JSON_RETRY_HINT
                continue

        detail = f": {last_error}" if last_error else ""
        raise RuntimeError(
            "Model JSON could not be parsed or validated "
            f"(retried {max_retries} times){detail}"
        ) from last_error

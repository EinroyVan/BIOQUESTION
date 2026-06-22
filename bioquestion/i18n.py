"""Google Translate powered UI localization (no LLM tokens)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from bioquestion import PROJECT_ROOT
from bioquestion.ui_strings import UI_STRINGS

CACHE_DIR = PROJECT_ROOT / ".cache" / "i18n"

LANGUAGES: dict[str, str] = {
    "en": "English",
    "zh-CN": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "ru": "Русский",
    "es": "Español",
    "de": "Deutsch",
    "pt": "Português",
    "vi": "Tiếng Việt",
}


def _cache_path(lang: str) -> Path:
    return CACHE_DIR / f"{lang}.json"


def _load_cache(lang: str) -> dict[str, str]:
    path = _cache_path(lang)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(lang: str, data: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(lang).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _translate_batch(texts: list[str], target_lang: str) -> list[str]:
    if not texts:
        return []
    try:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="en", target=target_lang)
        translated = translator.translate_batch(texts)
        return [item if item else texts[i] for i, item in enumerate(translated)]
    except Exception:
        # Fallback: translate one-by-one; keep English on failure.
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="en", target=target_lang)
        results: list[str] = []
        for text in texts:
            try:
                results.append(translator.translate(text) or text)
            except Exception:
                results.append(text)
        return results


def build_translation_map(lang: str) -> dict[str, str]:
    """Return all UI strings translated to `lang`. English skips remote calls."""
    if lang == "en":
        return dict(UI_STRINGS)

    cached = _load_cache(lang)
    missing_keys: list[str] = []
    missing_texts: list[str] = []

    for key, text in UI_STRINGS.items():
        if key not in cached:
            missing_keys.append(key)
            missing_texts.append(text)

    if missing_texts:
        translated = _translate_batch(missing_texts, lang)
        for key, value in zip(missing_keys, translated, strict=True):
            cached[key] = value
        _save_cache(lang, cached)

    result = dict(UI_STRINGS)
    result.update(cached)
    return result


def translate_value(text: str, lang: str) -> str:
    if lang == "en" or not text.strip():
        return text
    digest = hashlib.sha256(f"{lang}:{text}".encode("utf-8")).hexdigest()[:16]
    cache = _load_cache(lang)
    cache_key = f"__dyn__:{digest}"
    if cache_key in cache:
        return cache[cache_key]
    translated = _translate_batch([text], lang)[0]
    cache[cache_key] = translated
    _save_cache(lang, cache)
    return translated


def get_language_label(lang: str) -> str:
    return LANGUAGES.get(lang, lang)

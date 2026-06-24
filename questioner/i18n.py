"""Google Translate powered UI localization (no LLM tokens)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from questioner import PROJECT_ROOT
from questioner.ui_strings import UI_STRINGS

CACHE_DIR = PROJECT_ROOT / ".cache" / "i18n"
I18N_CACHE_VERSION = 9

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
    "fr": "Français",
    "hi": "हिन्दी",
    "ar": "العربية",
}

OUTPUT_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "zh-CN": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "es": "Spanish",
    "de": "German",
    "pt": "Portuguese",
    "vi": "Vietnamese",
    "fr": "French",
    "hi": "Hindi",
    "ar": "Arabic",
}

_ENGLISH_ONLY_LINES = (
    "Write all text fields in English.",
    "Write all question text, options, and answers in English.",
)

_PLACEHOLDER_RE = re.compile(r"\[\[(\w+)\]\]")


def apply_placeholders(text: str, **kwargs: object) -> str:
    """Replace [[name]] tokens without using str.format (translation-safe)."""
    for name, value in kwargs.items():
        text = text.replace(f"[[{name}]]", str(value))
    return text


def _protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    tokens: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        token = f"XPHX{name}XPHX"
        tokens[token] = f"[[{name}]]"
        return token

    return _PLACEHOLDER_RE.sub(repl, text), tokens


def _restore_placeholders(text: str, tokens: dict[str, str]) -> str:
    for token, placeholder in tokens.items():
        text = text.replace(token, placeholder)
    return text


def _cache_path(lang: str) -> Path:
    return CACHE_DIR / f"{lang}.v{I18N_CACHE_VERSION}.json"


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
    protected_texts: list[str] = []
    token_maps: list[dict[str, str]] = []

    for key, text in UI_STRINGS.items():
        if key not in cached:
            protected, tokens = _protect_placeholders(text)
            missing_keys.append(key)
            protected_texts.append(protected)
            token_maps.append(tokens)

    if protected_texts:
        translated = _translate_batch(protected_texts, lang)
        for key, raw, tokens in zip(missing_keys, translated, token_maps, strict=True):
            cached[key] = _restore_placeholders(raw, tokens)
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
    protected, tokens = _protect_placeholders(text)
    translated = _restore_placeholders(_translate_batch([protected], lang)[0], tokens)
    cache[cache_key] = translated
    _save_cache(lang, cache)
    return translated


def get_language_label(lang: str) -> str:
    return LANGUAGES.get(lang, lang)


def get_output_language_name(lang_code: str) -> str:
    return OUTPUT_LANGUAGE_NAMES.get(lang_code, "English")


def llm_output_language_clause(lang_code: str) -> str:
    name = get_output_language_name(lang_code)
    return (
        f"Output language: write all section titles, field labels, analysis text, "
        f"question stems, options, standard answers, grading_keywords, logic_chain, explanations, "
        f"feedback, and summaries in {name}. "
        "Keep JSON keys, question IDs, option letters (A–G), literature section ids "
        "(introduction, methods, results, discussion), and knowledge_point_id section refs unchanged."
    )


def augment_system_prompt_for_language(system: str, lang_code: str) -> str:
    cleaned = system
    for phrase in _ENGLISH_ONLY_LINES:
        cleaned = cleaned.replace(phrase, "")
    return cleaned.rstrip() + "\n\n" + llm_output_language_clause(lang_code)


def translate_content(text: str, lang_code: str) -> str:
    """Translate LLM-adjacent content via Google Translate (not LLM tokens)."""
    return translate_value(text, lang_code)

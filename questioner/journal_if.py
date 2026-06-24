"""Journal impact factor lookup with cache and bundled JCR values."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from questioner import PROJECT_ROOT

CACHE_DIR = PROJECT_ROOT / ".cache" / "journal_if"
BUNDLED_PATH = Path(__file__).resolve().parent / "data" / "journal_if_bundled.json"
_USER_AGENT = "Questioner/1.3 (literature learning tool; mailto:support@example.com)"


def _normalize_journal(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = re.sub(r"^the\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .,")


def _load_bundled() -> dict[str, dict[str, float]]:
    if not BUNDLED_PATH.exists():
        return {}
    try:
        raw = json.loads(BUNDLED_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {str(year): {k: float(v) for k, v in entries.items()} for year, entries in raw.items()}


def _pick_bundled_year(as_of: date, bundled: dict[str, dict[str, float]]) -> str | None:
    if not bundled:
        return None
    years = sorted(int(y) for y in bundled)
    eligible = [y for y in years if y <= as_of.year]
    return str(eligible[-1] if eligible else years[-1])


def _match_bundled(journal: str, as_of: date) -> tuple[float, str] | None:
    bundled = _load_bundled()
    year_key = _pick_bundled_year(as_of, bundled)
    if not year_key:
        return None
    table = bundled[year_key]
    norm = _normalize_journal(journal)
    if norm in table:
        return table[norm], year_key
    for key, value in table.items():
        if key in norm or norm in key:
            return value, year_key
    return None


def _cache_path(journal: str, as_of: date) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "_", _normalize_journal(journal))[:80]
    return CACHE_DIR / f"{safe}_{as_of.year}.json"


def _read_cache(journal: str, as_of: date) -> dict | None:
    path = _cache_path(journal, as_of)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(journal: str, as_of: date, payload: dict) -> None:
    path = _cache_path(journal, as_of)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _http_json(url: str, timeout: float = 12.0) -> dict | list | None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None


def _journal_from_doi(doi: str) -> tuple[str, list[str]]:
    doi_clean = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    if not doi_clean:
        return "", []
    data = _http_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi_clean)}")
    if not isinstance(data, dict):
        return "", []
    message = data.get("message") or {}
    titles = message.get("container-title") or message.get("short-container-title") or []
    journal = titles[0] if titles else ""
    issns = message.get("ISSN") or []
    return journal, [str(i) for i in issns]


def _journal_from_openalex(journal: str) -> tuple[str, list[str]]:
    query = urllib.parse.quote(journal)
    data = _http_json(f"https://api.openalex.org/sources?search={query}&per-page=3")
    if not isinstance(data, dict):
        return journal, []
    results = data.get("results") or []
    if not results:
        return journal, []
    best = results[0]
    display = best.get("display_name") or journal
    issns: list[str] = []
    for key in ("issn", "issn_l"):
        value = best.get(key)
        if isinstance(value, list):
            issns.extend(str(v) for v in value if v)
        elif value:
            issns.append(str(value))
    return display, issns


def lookup_impact_factor(
    journal: str,
    *,
    doi: str = "",
    as_of: date | datetime | None = None,
) -> tuple[str, str, str]:
    """
    Return (display_value, year_label, source_note).
    display_value is e.g. "64.8 (JCR 2024)" or "N/A".
    """
    if isinstance(as_of, datetime):
        as_of = as_of.date()
    as_of = as_of or date.today()

    journal = journal.strip()
    if not journal and doi:
        journal, _ = _journal_from_doi(doi)
    if not journal:
        return "N/A", "", ""

    cached = _read_cache(journal, as_of)
    if cached and cached.get("value"):
        return cached["value"], cached.get("year", ""), cached.get("source", "cache")

    resolved_journal = journal
    if doi and not journal:
        resolved_journal, _ = _journal_from_doi(doi)
    elif len(journal) < 4:
        resolved_journal, _ = _journal_from_openalex(journal)

    matched = _match_bundled(resolved_journal, as_of)
    if matched is None and resolved_journal != journal:
        matched = _match_bundled(journal, as_of)

    if matched:
        value, year = matched
        display = f"{value:g} (JCR {year})"
        source = f"Bundled JCR {year} table"
        _write_cache(journal, as_of, {"value": display, "year": year, "source": source})
        return display, year, source

    if doi:
        crossref_journal, _ = _journal_from_doi(doi)
        if crossref_journal:
            matched = _match_bundled(crossref_journal, as_of)
            if matched:
                value, year = matched
                display = f"{value:g} (JCR {year})"
                source = f"Crossref journal match · JCR {year}"
                _write_cache(journal, as_of, {"value": display, "year": year, "source": source})
                return display, year, source

    openalex_name, _ = _journal_from_openalex(resolved_journal)
    matched = _match_bundled(openalex_name, as_of)
    if matched:
        value, year = matched
        display = f"{value:g} (JCR {year})"
        source = f"OpenAlex journal match · JCR {year}"
        _write_cache(journal, as_of, {"value": display, "year": year, "source": source})
        return display, year, source

    display = "N/A"
    source = "Journal not found in bundled JCR table"
    _write_cache(journal, as_of, {"value": display, "year": "", "source": source})
    return display, "", source

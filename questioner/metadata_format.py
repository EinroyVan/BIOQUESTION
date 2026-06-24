"""Literature bibliographic metadata extraction helpers and report rendering."""

from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import Callable

from questioner.journal_if import lookup_impact_factor
from questioner.schemas import LiteratureMetadata

MetadataLabels = dict[str, str]

DEFAULT_METADATA_LABELS: MetadataLabels = {
    "title": "Title",
    "journal": "Journal",
    "impact_factor": "Impact Factor",
    "first_author": "First Author",
    "first_author_affiliation": "First Author Affiliation",
    "corresponding_author": "Corresponding Author",
    "corresponding_author_affiliation": "Corresponding Author Affiliation",
    "published_date": "Published",
    "doi": "DOI",
    "field_tags": "Tags",
    "header": "Article Information",
}


def metadata_is_present(metadata: LiteratureMetadata) -> bool:
    return bool(
        metadata.title.strip()
        or metadata.journal.strip()
        or metadata.first_author.strip()
        or metadata.corresponding_author.strip()
        or metadata.doi.strip()
        or metadata.field_tags
    )


def normalize_doi(doi: str) -> str:
    cleaned = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned.strip()


def doi_url(doi: str) -> str:
    normalized = normalize_doi(doi)
    return f"https://doi.org/{normalized}" if normalized else ""


def enrich_literature_metadata(
    metadata: LiteratureMetadata,
    *,
    as_of: date | datetime | None = None,
) -> LiteratureMetadata:
    """Resolve DOI URL and impact factor as of report submission time."""
    enriched = metadata.model_copy(deep=True)
    if enriched.doi:
        enriched.doi = normalize_doi(enriched.doi)
        enriched.doi_url = doi_url(enriched.doi)
    if enriched.journal.strip() or enriched.doi:
        value, year, source = lookup_impact_factor(
            enriched.journal,
            doi=enriched.doi,
            as_of=as_of,
        )
        enriched.impact_factor = value
        enriched.impact_factor_year = year
        enriched.impact_factor_source = source
    return enriched


def render_metadata_markdown(
    metadata: LiteratureMetadata,
    labels: MetadataLabels | None = None,
) -> list[str]:
    lbl = {**DEFAULT_METADATA_LABELS, **(labels or {})}
    if not metadata_is_present(metadata):
        return []

    tags = ", ".join(metadata.field_tags) if metadata.field_tags else "—"
    doi_line = metadata.doi_url or metadata.doi or "—"

    rows = [
        (lbl["title"], metadata.title or "—"),
        (lbl["journal"], metadata.journal or "—"),
        (lbl["impact_factor"], metadata.impact_factor or "—"),
        (lbl["first_author"], metadata.first_author or "—"),
        (lbl["first_author_affiliation"], metadata.first_author_affiliation or "—"),
        (lbl["corresponding_author"], metadata.corresponding_author or "—"),
        (
            lbl["corresponding_author_affiliation"],
            metadata.corresponding_author_affiliation or "—",
        ),
        (lbl["published_date"], metadata.published_date or "—"),
        (lbl["doi"], doi_line),
        (lbl["field_tags"], tags),
    ]

    lines = [f"## {lbl['header']}", ""]
    for label, value in rows:
        lines.append(f"- **{label}:** {value}")
    lines.append("")
    return lines


def render_metadata_html(
    metadata: LiteratureMetadata,
    labels: MetadataLabels | None = None,
    *,
    esc: Callable[[str], str] | None = None,
) -> str:
    escape = esc or html.escape
    lbl = {**DEFAULT_METADATA_LABELS, **(labels or {})}
    if not metadata_is_present(metadata):
        return ""

    tags = ", ".join(metadata.field_tags) if metadata.field_tags else "—"
    doi_value = metadata.doi_url or metadata.doi or "—"
    if metadata.doi_url:
        doi_cell = (
            f'<a href="{escape(metadata.doi_url)}">{escape(metadata.doi or metadata.doi_url)}</a>'
        )
    else:
        doi_cell = escape(doi_value)

    rows = [
        (lbl["title"], escape(metadata.title or "—")),
        (lbl["journal"], escape(metadata.journal or "—")),
        (lbl["impact_factor"], escape(metadata.impact_factor or "—")),
        (lbl["first_author"], escape(metadata.first_author or "—")),
        (lbl["first_author_affiliation"], escape(metadata.first_author_affiliation or "—")),
        (lbl["corresponding_author"], escape(metadata.corresponding_author or "—")),
        (
            lbl["corresponding_author_affiliation"],
            escape(metadata.corresponding_author_affiliation or "—"),
        ),
        (lbl["published_date"], escape(metadata.published_date or "—")),
        (lbl["doi"], doi_cell),
        (lbl["field_tags"], escape(tags)),
    ]

    body = "".join(
        f"<tr><th>{escape(label)}</th><td>{value}</td></tr>" for label, value in rows
    )
    return (
        f'<section class="article-metadata">'
        f"<h2>{escape(lbl['header'])}</h2>"
        f'<table class="metadata-table"><tbody>{body}</tbody></table>'
        f"</section>"
    )


def merge_pdf_document_metadata(
    metadata: LiteratureMetadata,
    *,
    pdf_title: str = "",
    pdf_author: str = "",
) -> LiteratureMetadata:
    merged = metadata.model_copy(deep=True)
    if pdf_title.strip() and not merged.title.strip():
        merged.title = pdf_title.strip()
    if pdf_author.strip() and not merged.first_author.strip():
        first = re.split(r"[;,]", pdf_author)[0].strip()
        if first:
            merged.first_author = first
    return merged

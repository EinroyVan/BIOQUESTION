"""Render structured literature analysis (Introduction / Methods / Results / Discussion)."""

from __future__ import annotations

import html
from typing import Callable

from questioner.schemas import LiteratureAnalysis

SectionLabels = dict[str, str]

DEFAULT_SECTION_LABELS: SectionLabels = {
    "introduction": "Introduction",
    "methods": "Methods",
    "results": "Results",
    "discussion": "Discussion",
    "hook": "Hook",
    "research_gap": "Research Gap",
    "proposed_approach": "Proposed Approach",
    "technical_innovation": "Technical Innovation",
    "benchmarks_evaluation": "Benchmarks & Evaluation",
    "key_findings": "Key Findings",
    "evidence_quality": "Evidence Quality",
    "limitations": "Limitations",
    "future_directions": "Future Directions",
}

LITERATURE_SECTION_IDS = ("introduction", "methods", "results", "discussion")


def literature_analysis_is_substantive(analysis: LiteratureAnalysis) -> bool:
    intro = analysis.introduction
    if intro.hook.strip() or intro.research_gap.strip() or intro.proposed_approach.strip():
        return True
    methods = analysis.methods
    if methods.technical_innovation.strip() or methods.benchmarks_evaluation.strip():
        return True
    results = analysis.results
    if any(f.strip() for f in results.key_findings) or results.evidence_quality.strip():
        return True
    discussion = analysis.discussion
    return bool(discussion.limitations.strip() or discussion.future_directions.strip())


def render_literature_analysis_markdown(
    analysis: LiteratureAnalysis,
    labels: SectionLabels | None = None,
    *,
    weak_sections: dict[str, list[str]] | None = None,
) -> list[str]:
    lbl = {**DEFAULT_SECTION_LABELS, **(labels or {})}
    weak = weak_sections or {}
    lines: list[str] = []

    def append_weak(section_id: str) -> None:
        if section_id in weak:
            lines.append("")
            lines.append("**Quiz errors linked to this section:**")
            for note in weak[section_id]:
                lines.append(f"- ❌ {note}")

    intro = analysis.introduction
    if intro.hook or intro.research_gap or intro.proposed_approach:
        title = lbl["introduction"]
        if "introduction" in weak:
            title += " *(quiz error — review)*"
        lines.extend([f"### {title}", ""])
        if intro.hook:
            lines.append(f"- **{lbl['hook']}**: {intro.hook}")
        if intro.research_gap:
            lines.append(f"- **{lbl['research_gap']}**: {intro.research_gap}")
        if intro.proposed_approach:
            lines.append(f"- **{lbl['proposed_approach']}**: {intro.proposed_approach}")
        append_weak("introduction")
        lines.append("")

    methods = analysis.methods
    if methods.technical_innovation or methods.benchmarks_evaluation:
        title = lbl["methods"]
        if "methods" in weak:
            title += " *(quiz error — review)*"
        lines.extend([f"### {title}", ""])
        if methods.technical_innovation:
            lines.append(f"- **{lbl['technical_innovation']}**: {methods.technical_innovation}")
        if methods.benchmarks_evaluation:
            lines.append(f"- **{lbl['benchmarks_evaluation']}**: {methods.benchmarks_evaluation}")
        append_weak("methods")
        lines.append("")

    results = analysis.results
    if results.key_findings or results.evidence_quality:
        title = lbl["results"]
        if "results" in weak:
            title += " *(quiz error — review)*"
        lines.extend([f"### {title}", ""])
        if results.key_findings:
            lines.append(f"- **{lbl['key_findings']}**:")
            for index, finding in enumerate(results.key_findings, start=1):
                text = finding.strip()
                if not text:
                    continue
                if text[0].isdigit() and "." in text[:4]:
                    lines.append(f"  {text}")
                else:
                    lines.append(f"  {index}. {text}")
        if results.evidence_quality:
            lines.append(f"- **{lbl['evidence_quality']}**: {results.evidence_quality}")
        append_weak("results")
        lines.append("")

    discussion = analysis.discussion
    if discussion.limitations or discussion.future_directions:
        title = lbl["discussion"]
        if "discussion" in weak:
            title += " *(quiz error — review)*"
        lines.extend([f"### {title}", ""])
        if discussion.limitations:
            lines.append(f"- **{lbl['limitations']}**: {discussion.limitations}")
        if discussion.future_directions:
            lines.append(f"- **{lbl['future_directions']}**: {discussion.future_directions}")
        append_weak("discussion")
        lines.append("")

    return lines


def render_literature_analysis_html(
    analysis: LiteratureAnalysis,
    labels: SectionLabels | None = None,
    *,
    weak_sections: dict[str, list[str]] | None = None,
    esc: Callable[[str], str] | None = None,
) -> list[str]:
    escape = esc or html.escape
    lbl = {**DEFAULT_SECTION_LABELS, **(labels or {})}
    weak = weak_sections or {}
    parts: list[str] = []

    def section_block(section_id: str, title: str, body_html: str) -> None:
        block_class = "kp-block kp-weak" if section_id in weak else "kp-block"
        parts.append(f'<div class="{block_class}">')
        parts.append(f"<h3>{escape(title)}</h3>")
        parts.append(body_html)
        if section_id in weak:
            notes = "".join(f"<li>{escape(n)}</li>" for n in weak[section_id])
            parts.append(
                '<div class="quiz-error-note"><strong>Quiz errors linked to this section:</strong>'
                f"<ul>{notes}</ul></div>"
            )
        parts.append("</div>")

    intro = analysis.introduction
    if intro.hook or intro.research_gap or intro.proposed_approach:
        items: list[str] = []
        if intro.hook:
            items.append(f"<li><strong>{escape(lbl['hook'])}:</strong> {escape(intro.hook)}</li>")
        if intro.research_gap:
            items.append(
                f"<li><strong>{escape(lbl['research_gap'])}:</strong> "
                f"{escape(intro.research_gap)}</li>"
            )
        if intro.proposed_approach:
            items.append(
                f"<li><strong>{escape(lbl['proposed_approach'])}:</strong> "
                f"{escape(intro.proposed_approach)}</li>"
            )
        section_block("introduction", lbl["introduction"], f"<ul>{''.join(items)}</ul>")

    methods = analysis.methods
    if methods.technical_innovation or methods.benchmarks_evaluation:
        items = []
        if methods.technical_innovation:
            items.append(
                f"<li><strong>{escape(lbl['technical_innovation'])}:</strong> "
                f"{escape(methods.technical_innovation)}</li>"
            )
        if methods.benchmarks_evaluation:
            items.append(
                f"<li><strong>{escape(lbl['benchmarks_evaluation'])}:</strong> "
                f"{escape(methods.benchmarks_evaluation)}</li>"
            )
        section_block("methods", lbl["methods"], f"<ul>{''.join(items)}</ul>")

    results = analysis.results
    if results.key_findings or results.evidence_quality:
        body: list[str] = ["<ul>"]
        if results.key_findings:
            body.append(f"<li><strong>{escape(lbl['key_findings'])}:</strong>")
            body.append("<ol>")
            for finding in results.key_findings:
                text = finding.strip()
                if text:
                    body.append(f"<li>{escape(text)}</li>")
            body.append("</ol></li>")
        if results.evidence_quality:
            body.append(
                f"<li><strong>{escape(lbl['evidence_quality'])}:</strong> "
                f"{escape(results.evidence_quality)}</li>"
            )
        body.append("</ul>")
        section_block("results", lbl["results"], "".join(body))

    discussion = analysis.discussion
    if discussion.limitations or discussion.future_directions:
        items = []
        if discussion.limitations:
            items.append(
                f"<li><strong>{escape(lbl['limitations'])}:</strong> "
                f"{escape(discussion.limitations)}</li>"
            )
        if discussion.future_directions:
            items.append(
                f"<li><strong>{escape(lbl['future_directions'])}:</strong> "
                f"{escape(discussion.future_directions)}</li>"
            )
        section_block("discussion", lbl["discussion"], f"<ul>{''.join(items)}</ul>")

    return parts

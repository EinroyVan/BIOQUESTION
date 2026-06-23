"""Build structured study notes and PDF reports from grading results."""

from __future__ import annotations

import html
import io
from datetime import datetime
from typing import Any

import fitz

from questioner.schemas import (
    GradingReport,
    KnowledgeExtractionResult,
    KnowledgePoint,
    LogicQuestion,
    MultipleChoiceQuestion,
    Question,
    QuestionGradingResult,
    QuestionType,
    QuizResult,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
    UserAnswerSheet,
)

_REPORT_CSS = """
body {
  font-family: sans-serif;
  font-size: 11pt;
  line-height: 1.5;
  color: #1a1a1a;
}
h1 {
  font-size: 20pt;
  color: #0f4c81;
  border-bottom: 2px solid #0f4c81;
  padding-bottom: 6pt;
}
h2 {
  font-size: 14pt;
  color: #2c3e50;
  margin-top: 20pt;
  border-bottom: 1px solid #ddd;
  padding-bottom: 4pt;
}
h3 {
  font-size: 12pt;
  color: #34495e;
  margin-top: 14pt;
}
.meta {
  color: #666;
  font-size: 10pt;
  margin-bottom: 16pt;
}
.score-box {
  background: #eef6fc;
  border: 1px solid #b8d4e8;
  padding: 12pt;
  margin: 12pt 0;
  border-radius: 4pt;
}
.section-note {
  font-size: 10pt;
  color: #666;
  font-style: italic;
  margin-bottom: 12pt;
}
.kp-block {
  margin: 14pt 0;
  padding: 10pt 12pt;
  border: 1px solid #dcdcdc;
  border-radius: 4pt;
  page-break-inside: avoid;
}
.kp-block .kp-title { color: #2c3e50; margin: 0 0 6pt 0; }
.kp-block .kp-body { margin: 6pt 0; }
.kp-block blockquote {
  border-left: 3px solid #bdc3c7;
  margin: 8pt 0 0 0;
  padding: 4pt 12pt;
  color: #555;
  font-size: 10pt;
}
.kp-weak {
  border-color: #e74c3c;
  background: #fff8f7;
}
.kp-weak .kp-title,
.kp-weak .kp-body,
.kp-weak blockquote {
  color: #c0392b;
}
.kp-weak blockquote {
  border-left-color: #e74c3c;
}
.quiz-error-note {
  margin-top: 8pt;
  padding: 8pt;
  border: 1px dashed #e74c3c;
  color: #c0392b;
  font-size: 10pt;
}
.review-banner {
  background: #fdecea;
  border: 1px solid #e74c3c;
  color: #c0392b;
  padding: 10pt;
  margin: 10pt 0;
  border-radius: 4pt;
}
.error, .weak { color: #c0392b; font-weight: bold; }
.correct { color: #1e8449; }
blockquote {
  border-left: 3px solid #bdc3c7;
  margin: 8pt 0;
  padding: 4pt 12pt;
  color: #555;
  font-size: 10pt;
}
ul { margin: 6pt 0; padding-left: 18pt; }
li { margin: 4pt 0; }
.tag-wrong { color: #c0392b; font-weight: bold; }
.tag-missed { color: #c0392b; font-weight: bold; }
.tag-ok { color: #1e8449; }
.appendix { margin-top: 24pt; }
"""


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _answer_for(question_id: str, sheet: UserAnswerSheet | None) -> str | list[str] | None:
    if not sheet:
        return None
    for item in sheet.answers:
        if item.question_id == question_id:
            return item.answer
    return None


def _format_user_mc(answer: list[str] | None) -> str:
    if not answer:
        return "(no answer)"
    return ", ".join(sorted(answer))


def _format_question_error(
    item: QuestionGradingResult,
    q: Question | None,
) -> str:
    if item.question_type in (
        QuestionType.MULTIPLE_CHOICE,
        QuestionType.SINGLE_CHOICE,
        QuestionType.LOGIC,
    ) and item.choice_detail:
        d = item.choice_detail
        parts: list[str] = []
        if d.wrong:
            parts.append(f"wrong selections: {', '.join(d.wrong)}")
        if d.missed:
            parts.append(f"missed / unclear: {', '.join(d.missed)}")
        detail = "; ".join(parts) if parts else "incomplete answer"
        return f"{item.question_id} ({item.score:.1f}/{item.max_score:.1f} pts) — {detail}"
    if item.question_type == QuestionType.SHORT_ANSWER and item.short_answer_detail:
        d = item.short_answer_detail
        parts: list[str] = []
        if d.missing_keywords:
            parts.append(f"missing: {', '.join(d.missing_keywords)}")
        if not d.logic_complete:
            parts.append("logic incomplete or unclear")
        detail = "; ".join(parts) if parts else "needs review"
        return f"{item.question_id} ({item.score:.1f}/{item.max_score:.1f} pts) — {detail}"
    return f"{item.question_id} ({item.score:.1f}/{item.max_score:.1f} pts) — needs review"


def _map_weak_knowledge_points(
    report: GradingReport,
    quiz: QuizResult,
) -> dict[str, list[str]]:
    """Map knowledge-point IDs to quiz error notes for questions the user got wrong."""
    quiz_map = {q.id: q for q in quiz.questions}
    weak: dict[str, list[str]] = {}

    for item in report.question_results:
        if item.is_correct:
            continue
        q = quiz_map.get(item.question_id)
        error_note = _format_question_error(item, q)
        seen_kp: set[str] = set()

        ref_sources = []
        if q is not None:
            ref_sources.extend(q.references)
        ref_sources.extend(item.references)

        for ref in ref_sources:
            kp_id = ref.knowledge_point_id
            if not kp_id or kp_id in seen_kp:
                continue
            seen_kp.add(kp_id)
            notes = weak.setdefault(kp_id, [])
            if error_note not in notes:
                notes.append(error_note)

    return weak


def _collect_weak_points(
    report: GradingReport,
    quiz: QuizResult,
    answers: UserAnswerSheet | None,
) -> list[str]:
    quiz_map = {q.id: q for q in quiz.questions}
    points: list[str] = []
    for item in report.question_results:
        if item.is_correct:
            continue
        q = quiz_map.get(item.question_id)
        points.append(_format_question_error(item, q))
    return points


def _mc_option_lines(
    question: MultipleChoiceQuestion,
    result: QuestionGradingResult,
) -> list[tuple[str, str, str]]:
    detail = result.choice_detail
    user_set = set(detail.user_answers) if detail else set()
    correct_set = set(question.correct_answers)
    lines: list[tuple[str, str, str]] = []

    for key in sorted(question.options):
        text = question.options[key]
        should = key in correct_set
        selected = key in user_set
        if selected and not should:
            status = "wrong"
        elif should and not selected:
            status = "missed"
        elif should and selected:
            status = "ok"
        else:
            status = "neutral"
        lines.append((key, text, status))
    return lines


def _render_knowledge_point_markdown(
    kp: KnowledgePoint,
    weak_notes: list[str] | None,
) -> list[str]:
    cat = kp.category.value.title()
    lines: list[str] = []
    if weak_notes:
        lines.append(f"### ❌ [{kp.id}] {cat} · {kp.title} *(quiz error — review)*")
    else:
        lines.append(f"### [{kp.id}] {cat} · {kp.title}")
    lines.append("")
    lines.append(kp.content)
    lines.append("")
    lines.append(f"> {kp.source_quote}")
    if weak_notes:
        lines.append("")
        lines.append("**Quiz errors linked to this point:**")
        for note in weak_notes:
            lines.append(f"- ❌ {note}")
    lines.append("")
    return lines


def _render_knowledge_point_html(
    kp: KnowledgePoint,
    weak_notes: list[str] | None,
) -> str:
    cat = kp.category.value.title()
    block_class = "kp-block kp-weak" if weak_notes else "kp-block"
    parts = [
        f'<div class="{block_class}">',
        f'<h3 class="kp-title">[{_esc(kp.id)}] {_esc(cat)} · {_esc(kp.title)}</h3>',
        f'<p class="kp-body">{_esc(kp.content)}</p>',
        f"<blockquote>{_esc(kp.source_quote)}</blockquote>",
    ]
    if weak_notes:
        notes = "".join(f"<li>{_esc(n)}</li>" for n in weak_notes)
        parts.append(
            f'<div class="quiz-error-note"><strong>Quiz errors linked to this knowledge point:</strong>'
            f"<ul>{notes}</ul></div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def _render_knowledge_section_markdown(
    knowledge: KnowledgeExtractionResult,
    weak_kp_map: dict[str, list[str]],
) -> list[str]:
    lines: list[str] = [
        "## Complete Literature Knowledge Notes",
        "",
        "All extracted knowledge points from the literature. "
        "Points linked to quiz errors are marked with ❌.",
        "",
        "### Summary",
        "",
        knowledge.summary,
        "",
    ]
    if knowledge.entities:
        lines.append(f"**Core entities:** {', '.join(knowledge.entities)}")
        lines.append("")

    for kp in knowledge.knowledge_points:
        lines.extend(_render_knowledge_point_markdown(kp, weak_kp_map.get(kp.id)))
    return lines


def _render_knowledge_section_html(
    knowledge: KnowledgeExtractionResult,
    weak_kp_map: dict[str, list[str]],
) -> list[str]:
    weak_count = sum(1 for kp in knowledge.knowledge_points if kp.id in weak_kp_map)
    total = len(knowledge.knowledge_points)
    parts: list[str] = [
        "<h2>Complete Literature Knowledge Notes</h2>",
        '<p class="section-note">This section includes every knowledge point extracted from the '
        "literature. Items you answered incorrectly in the quiz are highlighted in "
        "<span class='error'>red</span> with linked error details.</p>",
        f"<p><strong>Coverage:</strong> {total} knowledge point(s); "
        f"<span class='error'>{weak_count} need review</span> based on your quiz answers.</p>",
        "<h3>Summary</h3>",
        f"<p>{_esc(knowledge.summary)}</p>",
    ]
    if knowledge.entities:
        parts.append(f"<p><strong>Core entities:</strong> {_esc(', '.join(knowledge.entities))}</p>")

    for kp in knowledge.knowledge_points:
        parts.append(_render_knowledge_point_html(kp, weak_kp_map.get(kp.id)))
    return parts


def build_report_markdown(
    report: GradingReport,
    quiz: QuizResult,
    knowledge: KnowledgeExtractionResult | None,
    answers: UserAnswerSheet | None,
    *,
    source_label: str = "Literature excerpt",
    generated_at: datetime | None = None,
) -> str:
    ts = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    quiz_map = {q.id: q for q in quiz.questions}
    weak_kp_map = _map_weak_knowledge_points(report, quiz)
    weak = _collect_weak_points(report, quiz, answers)

    lines: list[str] = [
        "# Questioner Learning Report",
        "",
        f"- **Source:** {source_label}",
        f"- **Generated:** {ts}",
        f"- **Score:** {report.total_score:.1f} / {report.max_score:.0f} ({report.percentage:.1f}%)",
        "",
        "## Overall Assessment",
        "",
        report.summary,
        "",
    ]

    if knowledge and knowledge.has_substantive_content and knowledge.knowledge_points:
        lines.extend(_render_knowledge_section_markdown(knowledge, weak_kp_map))
    elif knowledge and knowledge.has_substantive_content:
        lines.extend(["## Literature Summary", "", knowledge.summary, ""])
    else:
        lines.extend(
            [
                "## Literature Knowledge Notes",
                "",
                "_No knowledge extraction data available for this session._",
                "",
            ]
        )

    if weak:
        lines.extend(["## Quiz Error Summary", ""])
        for point in weak:
            lines.append(f"- ❌ {point}")
        lines.append("")

    lines.extend(
        [
            "## Appendix · Question-by-Question Review",
            "",
            "Detailed breakdown of each quiz item and your responses.",
            "",
        ]
    )

    for item in report.question_results:
        q = quiz_map.get(item.question_id)
        verdict = "✅" if item.is_correct else "❌"
        lines.append(f"### {item.question_id} {verdict} ({item.score:.1f}/{item.max_score:.1f} pts)")
        lines.append("")
        if q:
            if isinstance(q, LogicQuestion):
                if q.stem:
                    lines.append(f"**Question:** {q.stem}")
                    lines.append("")
                lines.append(f"**α:** {q.description_alpha}")
                lines.append(f"**β:** {q.description_beta}")
                lines.append("")
            else:
                lines.append(f"**Question:** {q.stem}")
                lines.append("")

        if item.choice_detail and not isinstance(q, ShortAnswerQuestion):
            d = item.choice_detail
            lines.append(f"**Your answer:** {_format_user_mc(d.user_answers)}")
            lines.append(f"**Correct answer:** {', '.join(sorted(d.correct_answers))}")
            if not item.is_correct:
                if d.wrong:
                    lines.append(f"**❌ Wrong selections:** {', '.join(d.wrong)}")
                if d.missed:
                    lines.append(f"**❌ Missed (unclear):** {', '.join(d.missed)}")
            lines.append("")

        elif isinstance(q, ShortAnswerQuestion):
            user_text = _answer_for(item.question_id, answers)
            if isinstance(user_text, str) and user_text.strip():
                prefix = "**Your answer:**" if item.is_correct else "**❌ Your answer:**"
                lines.append(f"{prefix} {user_text.strip()}")
            if item.short_answer_detail and item.short_answer_detail.missing_keywords:
                lines.append(
                    f"**❌ Missing keywords:** "
                    f"{', '.join(item.short_answer_detail.missing_keywords)}"
                )
            lines.extend(["", f"**Model answer:** {q.standard_answer}", ""])

        lines.append(f"**Explanation:** {item.explanation}")
        if q and q.references:
            lines.append("**Linked knowledge points:** " + ", ".join(r.knowledge_point_id for r in q.references))
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_report_html(
    report: GradingReport,
    quiz: QuizResult,
    knowledge: KnowledgeExtractionResult | None,
    answers: UserAnswerSheet | None,
    *,
    source_label: str = "Literature excerpt",
    generated_at: datetime | None = None,
) -> str:
    ts = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    quiz_map = {q.id: q for q in quiz.questions}
    weak_kp_map = _map_weak_knowledge_points(report, quiz)
    weak = _collect_weak_points(report, quiz, answers)

    parts: list[str] = [
        "<h1>Questioner Learning Report</h1>",
        f'<p class="meta"><strong>Source:</strong> {_esc(source_label)}<br/>'
        f"<strong>Generated:</strong> {_esc(ts)}</p>",
        f'<div class="score-box"><strong>Total score:</strong> '
        f"{report.total_score:.1f} / {report.max_score:.0f} "
        f"({report.percentage:.1f}%)</div>",
        "<h2>Overall Assessment</h2>",
        f"<p>{_esc(report.summary)}</p>",
    ]

    if knowledge and knowledge.has_substantive_content and knowledge.knowledge_points:
        parts.extend(_render_knowledge_section_html(knowledge, weak_kp_map))
    elif knowledge and knowledge.has_substantive_content:
        parts.extend(["<h2>Literature Summary</h2>", f"<p>{_esc(knowledge.summary)}</p>"])
    else:
        parts.append("<p><em>No knowledge extraction data available for this session.</em></p>")

    if weak:
        items = "".join(f"<li>{_esc(w)}</li>" for w in weak)
        parts.append(
            f'<div class="review-banner"><strong>Quiz error summary</strong><ul>{items}</ul></div>'
        )

    parts.append('<div class="appendix"><h2>Appendix · Question-by-Question Review</h2>')
    parts.append(
        '<p class="section-note">Detailed quiz breakdown. See the knowledge notes above for the '
        "full literature content with error-linked items in red.</p>"
    )

    for item in report.question_results:
        q = quiz_map.get(item.question_id)
        verdict_class = "correct" if item.is_correct else "error"
        verdict = "Correct" if item.is_correct else "Needs review"
        parts.append(
            f'<h3>{_esc(item.question_id)} '
            f'<span class="{verdict_class}">({verdict})</span> '
            f"— {item.score:.1f}/{item.max_score:.1f} pts</h3>"
        )
        if q:
            if isinstance(q, LogicQuestion):
                if q.stem:
                    parts.append(f"<p><strong>Question:</strong> {_esc(q.stem)}</p>")
                parts.append(f"<p><strong>α:</strong> {_esc(q.description_alpha)}</p>")
                parts.append(f"<p><strong>β:</strong> {_esc(q.description_beta)}</p>")
            else:
                parts.append(f"<p><strong>Question:</strong> {_esc(q.stem)}</p>")

        if item.choice_detail and not isinstance(q, ShortAnswerQuestion):
            d = item.choice_detail
            if item.is_correct:
                parts.append(
                    f"<p><strong>Your answer:</strong> "
                    f'<span class="correct">{_esc(_format_user_mc(d.user_answers))}</span></p>'
                )
            else:
                parts.append(
                    f"<p><strong>Your answer:</strong> "
                    f'<span class="error">{_esc(_format_user_mc(d.user_answers))}</span></p>'
                )
            if not item.is_correct:
                parts.append(
                    f"<p><strong>Correct answer:</strong> "
                    f"{_esc(', '.join(sorted(d.correct_answers)))}</p>"
                )
                parts.append("<ul>")
                if isinstance(q, MultipleChoiceQuestion):
                    for key, text, status in _mc_option_lines(q, item):
                        if status in ("wrong", "missed"):
                            label = "Wrongly selected" if status == "wrong" else "Missed"
                            parts.append(
                                f'<li><span class="tag-wrong">{_esc(key)}. {_esc(text)} [{label}]</span></li>'
                            )
                parts.append("</ul>")

        elif isinstance(q, ShortAnswerQuestion):
            user_text = _answer_for(item.question_id, answers)
            if isinstance(user_text, str) and user_text.strip():
                cls = "" if item.is_correct else ' class="error"'
                parts.append(
                    f"<p><strong>Your answer:</strong> <span{cls}>{_esc(user_text.strip())}</span></p>"
                )
            if item.short_answer_detail and item.short_answer_detail.missing_keywords:
                parts.append(
                    f'<p><strong>Missing concepts:</strong> '
                    f'<span class="error">{_esc(", ".join(item.short_answer_detail.missing_keywords))}</span></p>'
                )
            parts.append(f"<p><strong>Model answer:</strong> {_esc(q.standard_answer)}</p>")

        parts.append(f"<p><strong>Explanation:</strong> {_esc(item.explanation)}</p>")
        if q and q.references:
            kp_ids = ", ".join(r.knowledge_point_id for r in q.references)
            parts.append(f"<p><strong>Linked knowledge points:</strong> {_esc(kp_ids)}</p>")

    parts.append("</div>")
    return "\n".join(parts)


def render_report_pdf(html_body: str) -> bytes:
    document = f"<html><body>{html_body}</body></html>"
    story = fitz.Story(html=document, user_css=_REPORT_CSS)
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (50, 50, -50, -50)
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()


def build_study_report_bundle(
    report: GradingReport,
    quiz: QuizResult,
    knowledge: KnowledgeExtractionResult | None,
    answers: UserAnswerSheet | None,
    *,
    source_label: str = "Literature excerpt",
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    ts = generated_at or datetime.now()
    stem = f"questioner_report_{ts:%Y%m%d_%H%M%S}"
    kwargs = {
        "source_label": source_label,
        "generated_at": ts,
    }
    markdown = build_report_markdown(report, quiz, knowledge, answers, **kwargs)
    html_body = build_report_html(report, quiz, knowledge, answers, **kwargs)
    pdf_bytes = render_report_pdf(html_body)
    return {
        "markdown": markdown,
        "pdf_bytes": pdf_bytes,
        "filename_stem": stem,
    }

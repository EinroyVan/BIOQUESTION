"""Console output helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from questioner.literature_format import render_literature_analysis_markdown
from questioner.schemas import (
    GradingReport,
    KnowledgeExtractionResult,
    MultipleChoiceQuestion,
    QuizResult,
    ShortAnswerQuestion,
)

console = Console()


def print_knowledge(result: KnowledgeExtractionResult) -> None:
    if not result.has_substantive_content:
        console.print("[yellow]No substantive literature content found[/yellow]")
        return

    text = "\n".join(render_literature_analysis_markdown(result.literature_analysis))
    console.print(Panel(text, title="Literature Analysis", border_style="blue"))


def print_quiz(quiz: QuizResult) -> None:
    for q in quiz.questions:
        if isinstance(q, MultipleChoiceQuestion):
            lines = [q.stem, ""]
            for key in sorted(q.options):
                lines.append(f"  {key}. {q.options[key]}")
            lines.append(f"\n[dim]Answer key: {', '.join(sorted(q.correct_answers))}[/dim]")
            console.print(Panel("\n".join(lines), title=f"[{q.id}] Multi-select"))
        elif isinstance(q, ShortAnswerQuestion):
            console.print(
                Panel(
                    f"{q.stem}\n\n[dim]Keywords: {', '.join(q.grading_keywords)}[/dim]",
                    title=f"[{q.id}] Short answer",
                )
            )


def print_grading(report: GradingReport) -> None:
    table = Table(title="Grading Results")
    table.add_column("Question")
    table.add_column("Score")
    table.add_column("Verdict")
    for item in report.question_results:
        verdict = "Correct" if item.is_correct else "Incorrect / incomplete"
        if item.question_type.value == "short_answer" and item.short_answer_detail:
            if item.short_answer_detail.logic_complete:
                verdict = "Logic complete"
        table.add_row(item.question_id, f"{item.score}/{item.max_score}", verdict)
    console.print(table)
    console.print(
        Panel(
            f"Total: {report.total_score:.1f} / {report.max_score:.0f} ({report.percentage:.1f}%)\n\n"
            f"{report.summary}",
            title="Overall Assessment",
            border_style="cyan",
        )
    )
    for item in report.question_results:
        console.print(Panel(item.explanation, title=f"[{item.question_id}] Explanation"))

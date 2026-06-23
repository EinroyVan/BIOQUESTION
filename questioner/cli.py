"""Typer CLI for the three-step workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from questioner import __version__
from questioner.display import print_grading, print_knowledge, print_quiz
from questioner.extract import extract_knowledge, load_knowledge, save_knowledge
from questioner.grade import grade_answers, load_answers, save_report
from questioner.llm import LLMClient
from questioner.quiz import generate_quiz, load_quiz, save_quiz
from questioner.schemas import UserAnswer, UserAnswerSheet

app = typer.Typer(
    help="Natural-science literature workflow: extract → quiz → grade",
    no_args_is_help=True,
)
console = Console()


def _read_document(path: Path) -> str:
    if not path.exists():
        raise typer.BadParameter(f"File not found: {path}")
    if path.suffix.lower() == ".pdf":
        from questioner.pdf_reader import load_uploaded_document

        text, _ = load_uploaded_document(path.name, path.read_bytes())
        return text
    return path.read_text(encoding="utf-8").strip()


def _collect_answers_interactive(quiz_path: Path) -> UserAnswerSheet:
    quiz = load_quiz(quiz_path)
    console.print("[bold]Interactive answers[/bold] (multi-select: comma-separated letters, e.g. A,C)\n")
    answers: list[UserAnswer] = []
    for q in quiz.questions:
        if q.type.value == "multiple_choice":
            raw = Prompt.ask(f"[{q.id}] {q.stem}", default="")
            selected = [part.strip().upper() for part in raw.split(",") if part.strip()]
            answers.append(UserAnswer(question_id=q.id, answer=selected))
        else:
            raw = Prompt.ask(f"[{q.id}] {q.stem}", default="")
            answers.append(UserAnswer(question_id=q.id, answer=raw))
    return UserAnswerSheet(answers=answers)


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
) -> None:
    if version:
        console.print(f"questioner {__version__}")
        raise typer.Exit()


@app.command("extract")
def cmd_extract(
    input: Path = typer.Option(..., "--input", "-i", help="Literature file (.txt or .pdf)"),
    output: Path = typer.Option(
        Path("output/knowledge.json"), "--output", "-o", help="Knowledge JSON output path"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model for the active LLM provider"),
) -> None:
    """Step 1: Extract knowledge points from literature."""
    text = _read_document(input)
    if not text:
        console.print("[red]Input file is empty.[/red]")
        raise typer.Exit(1)

    llm = LLMClient(model=model) if model else LLMClient()
    console.print("[bold]Extracting knowledge points...[/bold]")
    result = extract_knowledge(text, llm)
    save_knowledge(result, output)
    print_knowledge(result)
    console.print(f"\n[green]Saved to {output}[/green]")


@app.command("quiz")
def cmd_quiz(
    knowledge: Path = typer.Option(
        ..., "--knowledge", "-k", help="Knowledge JSON (extract output)"
    ),
    output: Path = typer.Option(
        Path("output/quiz.json"), "--output", "-o", help="Quiz JSON output path"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model for the active LLM provider"),
) -> None:
    """Step 2: Generate quiz from knowledge points."""
    kp = load_knowledge(knowledge)
    llm = LLMClient(model=model) if model else LLMClient()
    console.print("[bold]Generating quiz...[/bold]")
    try:
        result = generate_quiz(kp, llm)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    save_quiz(result, output)
    print_quiz(result)
    console.print(f"\n[green]Saved to {output}[/green]")


@app.command("grade")
def cmd_grade(
    quiz: Path = typer.Option(..., "--quiz", "-q", help="Quiz JSON (quiz output)"),
    answers: Optional[Path] = typer.Option(
        None, "--answers", "-a", help="Answers JSON; omit for interactive mode"
    ),
    output: Path = typer.Option(
        Path("output/grading.json"), "--output", "-o", help="Grading report JSON path"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-I", help="Force interactive answers (ignore --answers)"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model for the active LLM provider"),
) -> None:
    """Step 3: Grade user answers and generate feedback."""
    quiz_data = load_quiz(quiz)
    if interactive or answers is None:
        sheet = _collect_answers_interactive(quiz)
        answers_path = output.parent / "answers.json"
        answers_path.parent.mkdir(parents=True, exist_ok=True)
        answers_path.write_text(
            json.dumps(sheet.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"[dim]Answers saved to {answers_path}[/dim]\n")
    else:
        sheet = load_answers(answers)

    llm = LLMClient(model=model) if model else LLMClient()
    console.print("[bold]Grading...[/bold]")
    report = grade_answers(quiz_data, sheet, llm)
    save_report(report, output)
    print_grading(report)
    console.print(f"\n[green]Report saved to {output}[/green]")


@app.command("pipeline")
def cmd_pipeline(
    input: Path = typer.Option(..., "--input", "-i", help="Literature file (.txt or .pdf)"),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-d", help="Output directory"
    ),
    skip_grade: bool = typer.Option(
        False, "--skip-grade", help="Extract and quiz only; skip grading"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model for the active LLM provider"),
) -> None:
    """Run full pipeline: extract → quiz → (optional) grade."""
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_path = output_dir / "knowledge.json"
    quiz_path = output_dir / "quiz.json"
    grading_path = output_dir / "grading.json"

    text = _read_document(input)
    llm = LLMClient(model=model) if model else LLMClient()

    console.rule("[bold]Step 1/3 · Knowledge Extraction[/bold]")
    knowledge = extract_knowledge(text, llm)
    save_knowledge(knowledge, knowledge_path)
    print_knowledge(knowledge)

    if not knowledge.has_substantive_content:
        console.print("[yellow]No substantive content; stopping.[/yellow]")
        raise typer.Exit(0)

    console.rule("[bold]Step 2/3 · Quiz Generation[/bold]")
    quiz_result = generate_quiz(knowledge, llm)
    save_quiz(quiz_result, quiz_path)
    print_quiz(quiz_result)

    if skip_grade:
        console.print(f"\n[green]Extract and quiz complete. Output: {output_dir}[/green]")
        raise typer.Exit(0)

    console.rule("[bold]Step 3/3 · Answers & Grading[/bold]")
    sheet = _collect_answers_interactive(quiz_path)
    answers_path = output_dir / "answers.json"
    answers_path.write_text(
        json.dumps(sheet.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = grade_answers(quiz_result, sheet, llm)
    save_report(report, grading_path)
    print_grading(report)
    console.print(f"\n[green]Pipeline complete. Output: {output_dir}[/green]")


if __name__ == "__main__":
    app()

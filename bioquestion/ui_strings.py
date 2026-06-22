"""English UI string catalog for Streamlit (source language for Google Translate)."""

from __future__ import annotations

UI_STRINGS: dict[str, str] = {
    "app.title": "BioQuestion",
    "app.tagline": "Extract → Quiz → Grade",
    "app.page_title": "BioQuestion",
    "sidebar.language": "Interface language",
    "sidebar.language_hint": "UI translation via Google Translate (does not use your LLM API).",
    "sidebar.llm_provider": "LLM provider",
    "sidebar.model": "Model",
    "sidebar.api_configured": "{provider} API configured",
    "sidebar.api_missing": "{provider} API key not detected",
    "sidebar.env_hint": "Set `{env_key}` in `{env_file}` (see `.env.example`).",
    "sidebar.provider_rules_title": "API usage rules",
    "sidebar.provider_rules_body": (
        "• **Google Gemini (default)** — store keys in `.env` as `GOOGLE_API_KEY` / `GOOGLE_MODEL`.\n"
        "• **OpenAI** — `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `OPENAI_MODEL`.\n"
        "• **Anthropic Claude** — `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`.\n"
        "• **OpenAI-compatible** — `OPENAI_COMPAT_API_KEY`, `OPENAI_COMPAT_BASE_URL`, "
        "`OPENAI_COMPAT_MODEL` (DeepSeek, Ollama, etc.).\n"
        "• Provider choice in the sidebar applies to this session only; `.env` is not modified.\n"
        "• UI translation uses Google Translate separately and does **not** consume LLM tokens."
    ),
    "sidebar.profile": "Profile",
    "sidebar.display_name": "Display name (for stats)",
    "sidebar.display_name_ph": "Optional",
    "sidebar.workflow": "Workflow",
    "step.literature_input": "Literature Input",
    "step.knowledge_points": "Knowledge Points",
    "step.quiz": "Quiz",
    "step.grading": "Grading",
    "category.entity": "Entity",
    "category.mechanism": "Mechanism",
    "category.finding": "Finding",
    "common.back": "← Back",
    "common.back_literature": "← Back to Literature Input",
    "common.back_knowledge": "← Back to Knowledge Points",
    "common.back_quiz": "← Back to Quiz",
    "input.header": "Step 1 · {step}",
    "input.intro": (
        "Upload a `.txt` or `.pdf` file, or paste a biomedical literature excerpt. "
        "Scanned PDFs are processed with OCR automatically."
    ),
    "input.upload": "Upload document",
    "input.ocr": "Enable OCR for scanned PDFs (recommended)",
    "input.paste": "Or paste text",
    "input.paste_ph": "Paste abstract, results, or discussion sections…",
    "input.parsing_pdf": "Parsing PDF…",
    "input.ocr_label": "OCR",
    "input.text_label": "Text extraction",
    "input.page_progress": "{label}: page {current}/{total}",
    "input.processing_page": "Processing page {current} ({label})",
    "input.pdf_failed": "PDF parsing failed: {error}",
    "input.pdf_done": "PDF parsing complete",
    "input.preview": "Preview extracted text",
    "input.extract_btn": "Extract Knowledge Points",
    "input.reset_btn": "Reset Session",
    "input.empty_warning": "Please enter or upload literature content first.",
    "input.extracting": "Extracting knowledge points…",
    "input.extract_failed": "Extraction failed: {error}",
    "input.no_kp": "No key knowledge points found.",
    "input.pasted_label": "Pasted literature excerpt",
    "knowledge.header": "Step 2 · {step}",
    "knowledge.need_extract": "Extract knowledge points on the Literature Input step first.",
    "knowledge.summary": "Summary",
    "knowledge.entities": "Core Entities",
    "knowledge.points": "Knowledge Points",
    "knowledge.source_quote": "Source quote: {quote}",
    "knowledge.mode_hint": (
        "**Normal mode** — Generate Quiz: 5 multi-select + 2 short-answer, scored out of 100.  "
        "**EZ mode** — Generate EZ Quiz: 4 single-choice + 1 short-answer, feedback only (no scoring)."
    ),
    "knowledge.generate_quiz": "Generate Quiz",
    "knowledge.generate_ez": "Generate EZ Quiz",
    "knowledge.generating_ez": "Generating 4 single-choice + 1 short-answer (EZ mode)…",
    "knowledge.generating_normal": "Generating 5 multi-select + 2 short-answer questions…",
    "knowledge.quiz_failed": "Quiz generation failed: {error}",
    "quiz.header": "Step 3 · {step}",
    "quiz.need_generate": "Generate a quiz on the Knowledge Points step first.",
    "quiz.ez_caption": (
        "EZ mode: 4 single-choice (A–D) + 1 short-answer. Feedback only — no numeric scoring."
    ),
    "quiz.normal_caption": (
        "Normal mode: 5 multi-select questions (15 pts each; 3 pts per option) "
        "and 2 short-answer questions (10 + 15 pts). Total score: 100 points."
    ),
    "quiz.select_one": "Select one answer",
    "quiz.select_many": "Select answer(s)",
    "quiz.your_answer": "Your answer",
    "quiz.answer_ph": "Address mechanism, experimental logic, or clinical significance…",
    "quiz.submit": "Submit & Grade",
    "quiz.unanswered": "Please answer all questions. Unanswered: {ids}",
    "quiz.grading": "Grading…",
    "quiz.grade_failed": "Grading failed: {error}",
    "grading.header": "Step 4 · {step}",
    "grading.need_submit": "Submit your answers on the Quiz step first.",
    "grading.total_score": "Total Score",
    "grading.score_progress": "Score: {pct:.1f}%",
    "grading.ez_info": "EZ mode — feedback only, no numeric scoring.",
    "grading.overall": "Overall Assessment",
    "grading.details": "Question Details",
    "grading.verdict_ok": "✅",
    "grading.verdict_bad": "❌",
    "grading.verdict_logic_ok": "✅ Logic complete",
    "grading.verdict_incomplete": "⚠️ Incomplete",
    "grading.question": "**Question:** {stem}",
    "grading.your_answer": "Your answer: {answer}",
    "grading.correct_answer": "Correct answer: {answer}",
    "grading.missed": "Missed: {items}",
    "grading.extra": "Extra: {items}",
    "grading.missed_zero": "Missed ({items}): more than two misses — question scored 0.",
    "grading.two_miss_wrong": "Two missed ({missed}) and wrong ({wrong}) — question scored 0.",
    "grading.two_miss_cap": "Two missed ({items}): question capped at 3 pts.",
    "grading.two_wrong_zero": "Wrong selections ({items}): 2+ incorrect options — question scored 0.",
    "grading.wrong_penalty": "Wrong: {items} (−3 pts each)",
    "grading.incorrect": "Incorrect: {items}",
    "grading.matched_kw": "Matched keywords: {items}",
    "grading.missing_kw": "Missing keywords: {items}",
    "grading.view_model": "View model answer",
    "grading.grading_kw": "Grading keywords: {items}",
    "grading.explanation": "**Explanation**",
    "grading.leaderboard": "Team Leaderboard",
    "grading.leaderboard_caption": (
        "Reserved for team paper-reading rankings. API endpoint: `{url}` · port **{port}**"
    ),
    "grading.leaderboard_window": "Leaderboard window",
    "grading.leaderboard_placeholder": (
        "Team leaderboard sync is not connected yet. This panel will display cross-member "
        "rankings once the backend on port {port} is enabled."
    ),
    "grading.rank": "Rank",
    "grading.member": "Member",
    "grading.score": "Score",
    "grading.coming_soon": "Coming soon",
    "grading.dash": "—",
    "grading.personal_stats": "Personal Statistics",
    "grading.attempts": "Normal-mode attempts",
    "grading.lifetime_avg": "Lifetime average",
    "grading.best_score": "Best score",
    "grading.week_avg": "7-day average",
    "grading.trend_title": "Recent score trend",
    "grading.trend_caption": (
        "Average Normal-mode score over the last 10 calendar days. "
        "Days with ≤3 submissions are merged into the following day(s)."
    ),
    "grading.chart_period": "Period",
    "grading.chart_avg": "Average score (%)",
    "grading.bucket_details": "Bucket details",
    "grading.no_data": "No data",
    "grading.bucket_line": "**{label}** — {avg} ({count} submission(s))",
    "grading.trend_empty": "Complete Normal-mode quizzes to see your recent score trend.",
    "grading.download_report": "Download Learning Report",
    "grading.download_caption": (
        "Full literature knowledge notes in the PDF — all extracted knowledge points are included. "
        "Points linked to your quiz errors are highlighted in **red**."
    ),
    "grading.report_failed": "Could not build report: {error}",
    "grading.preview_md": "Preview report (Markdown)",
    "grading.preview_truncated": "Preview truncated. Download the full Markdown or PDF.",
    "grading.download_pdf": "Download PDF Report",
    "grading.download_md": "Download Markdown Notes",
    "grading.download_json": "Download JSON",
    "grading.empty_answer": "(empty)",
    "grading.pts_suffix": "({score:.1f}/{max:.1f} pts)",
}

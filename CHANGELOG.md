# Changelog

All notable changes to Questioner are documented in this file.

## [1.3.3] — 2026-06-23

### Literature analysis (IMRaD)

- Replace knowledge-point list with four-section analysis: Introduction, Methods, Results, Discussion.
- Quiz generation and PDF reports use the structured analysis instead of KP summaries.

### Logic & grading

- Add logic options **F** (both correct, no causality) and **G** (mutually exclusive).
- Logic UI shows **Q6–Q8 · shared options** without redundant option descriptions.
- Choice explanations: LLM-generated rationales for wrong/missed options only in UI; full option notes in PDF.
- Short-answer strict scoring: −10 for logic errors and concept confusion; keyword-based partial credit otherwise.
- Multi-select scoring summary clarifies one-miss-one-wrong (4/10) rule.

### PDF report header

- Add **Article Information** table: title, journal, impact factor (JCR lookup at submission), authors & affiliations, publication date, DOI link, field tags.
- Bundled JCR 2024 journal IF database with Crossref/OpenAlex enrichment and cache.

## [1.3.2] — 2026-06-23

### Knowledge extraction

- Fix JSON parse/validation failures when creating knowledge points.
- Google Gemini and OpenAI now use structured JSON schema output for more reliable responses.
- Normalize `category` values (including Chinese aliases) and auto-fill missing knowledge-point IDs.
- Truncate overlong `source_quote` fields; improve error messages with validation details.
- Prompts clarify that `category` must remain English literals (`entity`, `mechanism`, `finding`).

## [1.3.1] — 2026-06-22

### Repository & paths

- GitHub remote updated to **EinroyVan/Questioner** (repo renamed on GitHub).
- Local project folder: **E:\\Questioner** (was `E:\\BIOQUESTION`).
- Push script renamed `push_questioner.ps1`; scripts use `$RepoRoot` instead of hardcoded paths.
- GitHub About/description updated for natural-science Questioner.

## [1.3.0] — 2026-06-22

### Rebrand: BioQuestion → Questioner

- Project renamed **Questioner** for all **natural sciences** (not limited to biomedicine).
- Python package renamed `bioquestion` → `questioner`; CLI entry point `questioner`.
- Prompts and UI copy broadened to physics, chemistry, biology, earth science, astronomy, etc.

### Documentation

- Updated English [README.md](README.md).
- Added Chinese [README.zh-CN.md](README.zh-CN.md).

### Logic scoring

- Logic questions use **independent all-or-nothing** scoring (6 pts correct, 0 pts wrong).
- Grading UI no longer applies multi-select partial-credit rules to logic items.

## [1.2.2] — 2026-06-22

### Logic questions UI

- Logic block (Q6–Q8) shows **one master section** explaining shared A–E options once.
- Each sub-question displays only **α** and **β** descriptions; user picks **A–E** without repeated option text.

### Scoring efficiency

- Single-choice, multi-select, and logic questions are **script-graded only** (no LLM tokens).
- LLM is invoked **only for short-answer** questions; skipped entirely when a quiz has none.
- Quiz prompts require accurate `correct_answer` / `correct_answers` at generation time.

### Profile

- Nickname limit updated to **at most 12 full-width characters** (≤12).

## [1.2.1] — 2026-06-22

### Quiz modes & question types

- Renamed **EZ mode** to **Easy mode**; single-choice questions are now strictly **4 options, pick 1** (A–D).
- Reworked **Normal mode** structure and scoring (total **100 points**):
  - Multi-select: 5 questions × **10 pts** (2 pts per option, A–E)
  - Logic: 3 questions × **6 pts** (wrong answer = 0 pts)
  - Short answer: 2 questions × **16 pts**
- Added **Custom mode**: configure counts of single-choice, multi-select, logic, and short-answer questions.
- Added **logic questions** with fixed A–E relationship template (α/β cause–effect and correctness).

### Scoring

- Multi-select: if the correct set has **only one option**, **1 miss + 1 wrong selection** scores **0**.
- Updated penalty captions and grading UI to reflect 2-pt-per-option rules.

### Localization

- Knowledge extraction, quiz generation, and grading prompts now follow the **sidebar UI language**.
- Logic option labels are translatable via UI strings.

### Personal statistics

- Scored submissions (Normal / Custom) require a **nickname** before saving.
- Nickname must be **fewer than 12 full-width characters**; stored locally in `output/stats/profile.json`.
- Score history supports Normal and Custom modes.

### Other

- Learning reports support logic and single-choice question types.
- i18n cache bumped to v3 for new UI strings.

## [1.2.0] — 2026-06-22

- Multi-provider LLM backend (Google, OpenAI, Anthropic, OpenAI-compatible).
- 12-language UI via Google Translate (`deep-translator`).
- EZ mode (now Easy) and personal score analytics.
- Placeholder-safe i18n (`[[placeholder]]` tokens).

## [1.0.0] — Initial release

- Literature upload (TXT/PDF with OCR).
- Knowledge extraction → quiz generation → grading pipeline.
- Streamlit web UI and CLI.

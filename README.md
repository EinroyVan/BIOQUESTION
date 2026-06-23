# Questioner

Natural-science literature learning workflow: **extract knowledge points → generate quiz → grade answers**.

Works across physics, chemistry, biology, earth science, astronomy, materials science, and related fields. Streamlit web UI + CLI.

**中文文档：** [README.zh-CN.md](README.zh-CN.md)

## Features

- Upload **TXT** or **PDF** (with OCR for scanned pages)
- Extract entities, mechanisms, and findings with source quotes
- **Normal mode**: 5 multi-select (10 pts) + 3 logic (6 pts, all-or-nothing) + 2 short-answer (16 pts); total 100
- **Easy mode**: 4 single-choice (A–D) + 1 short-answer; feedback only
- **Custom mode**: configure your own question mix
- Multi-provider LLM: **Google Gemini**, **OpenAI**, **Anthropic Claude**, **OpenAI-compatible**
- UI languages via Google Translate (English, 中文, 日本語, 한국어, and more)
- Personal score history (local) with nickname; team leaderboard placeholder

## Setup

```bash
cd Questioner   # or your clone directory
python -m pip install -r requirements.txt
python -m pip install -e .
copy .env.example .env   # Windows
```

### API keys (`.env`)

| Provider | Environment variables |
|----------|----------------------|
| Google Gemini (default) | `GOOGLE_API_KEY`, `GOOGLE_MODEL` |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, optional `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| OpenAI-compatible | `OPENAI_COMPAT_API_KEY`, `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_MODEL` |

Choose the active provider in the Streamlit sidebar (session only; `.env` is not modified).

UI translation uses **Google Translate** via `deep-translator` and does **not** consume LLM tokens.

## Web UI (recommended)

```bash
python -m streamlit run app.py
```

Open http://localhost:8502

Or double-click `start.bat` on Windows.

## CLI

```bash
python main.py extract -i examples/literature_sample.txt -o output/knowledge.json
python main.py quiz -k output/knowledge.json -o output/quiz.json
python main.py grade -q output/quiz.json -I -o output/grading.json
python main.py pipeline -i examples/literature_sample.txt -d output
```

Set `LLM_PROVIDER=google` (or `openai`, `anthropic`, `openai_compatible`) in `.env` for CLI defaults.

## Project structure

```
Questioner/
├── app.py              # Streamlit entry
├── main.py             # CLI entry
├── questioner/         # Python package
├── examples/
└── .streamlit/         # Port 8502
```

## Scoring notes

- **Single-choice / multi-select / logic**: script-graded from generated answer keys (no LLM tokens).
- **Logic questions**: independent scoring — correct = 6 pts, wrong = 0 pts (not subject to multi-select partial-credit rules).
- **Short-answer**: LLM grading with partial credit.

## Security

Never commit `.env`. Use `.env.example` as a template only.

## License

MIT

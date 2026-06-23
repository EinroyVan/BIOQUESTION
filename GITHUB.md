# Push to GitHub (EinroyVan)

GitHub **does not accept account passwords** for git push. Use **GitHub CLI** with browser login instead.

## 1. Install GitHub CLI (one time)

```powershell
winget install GitHub.cli
```

Restart your terminal, then:

```powershell
gh auth login
```

Choose:
- GitHub.com
- HTTPS
- **Login with a web browser** (this opens the auth window you asked for)

## 2. Push Questioner

```powershell
cd E:\BIOQUESTION
.\scripts\push_bioquestion.ps1
```

Creates / updates: https://github.com/EinroyVan/BIOQUESTION (project name: **Questioner**)

## 3. Push BioReader (PaperReader)

```powershell
cd C:\PaperReader
.\scripts\push_bioreader.ps1
```

Creates: https://github.com/EinroyVan/bioreader

## What is excluded (never uploaded)

| Project | Excluded files |
|---------|----------------|
| BIOQUESTION | `.env`, `output/`, `.venv/`, `*.egg-info/` |
| BioReader | `.streamlit/secrets.toml`, `.venv/`, test payloads |

## Note on "bioreader"

The local folder is `C:\PaperReader`. It will be published as repo **`bioreader`** on GitHub.

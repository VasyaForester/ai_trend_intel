# AI Security Trend Finder

A platform that parses and aggregates publicly available messages about **AI security** and **LLM/AI agent security**,
normalizes the content, and analyzes patterns to surface **emerging trends**.

This project is focused on **safety, risk, governance, robustness, and mitigation** of AI systems.
It is not aimed at building offensive capabilities.

## What it does

1. **Ingest**: Collect messages from configurable sources (RSS, websites, public feeds, etc.).
2. **Normalize**: Clean, deduplicate, and map items to a common schema (title, author, timestamp, content, topic tags).
3. **Analyze**: Extract themes and risks (for example: prompt injection, data leakage, agent tool misuse, supply-chain issues).
4. **Report**: Produce trend summaries and outputs that you can export or visualize.

## Focus areas (LLM and AI agents)

- Prompt injection and jailbreak-adjacent risks (including indirect injection)
- Data privacy: leakage, model inversion, membership inference
- AI agent safety: tool/function calling abuse, access control, policy enforcement
- Secure RAG and retrieval risks
- Model/data supply chain: poisoning, integrity and provenance
- Evaluation and benchmarks for safety and robustness

## Documentation

See:
- `docs/AI_SECURITY_SOURCES.md` for suggested source categories and connectors
- `docs/AI_SECURITY_KEYWORDS.md` for initial keyword sets and topic taxonomy ideas

## Local setup

This repository currently contains the initial project documents and blueprint.
After you add the implementation code, typical steps will be:

1. Copy `.env.example` to `.env`
2. Configure source lists and any optional API keys
3. Run ingestion + analysis pipeline commands

The source registry lives in `config/search_sources.json`. Restricted sources (for example LinkedIn, Slack, and social APIs that require authorization) are listed there but should only be used by collectors after manual access/configuration.

## UI

The repository includes a lightweight browser UI in `ui/` (no build step). The dashboard reads real trend data from `ui/data.json`.

Regenerate data from Hacker News Algolia API (real non-cumulative weekly counts):

```powershell
python scripts/collect_hn.py
```

Collect arXiv links once (no API key required):

```powershell
python scripts/collect_arxiv.py
```

Keep searching arXiv every 10 minutes and accumulating links:

```powershell
$env:ARXIV_USER_AGENT = "ai-trend-intel/1.0 (research; contact: your-email@example.com)"
python scripts/collect_arxiv.py --watch --interval-minutes 10
```

Or use the Windows helper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_arxiv_watcher.ps1 -ContactEmail "your-email@example.com"
```

arXiv limits clients to one request every 3 seconds and one connection at a time. The collector follows this by default and writes accumulated links to `data/arxiv_links.json` and `ui/arxiv_links.json`.

Thank you to arXiv for use of its open access interoperability.

Run a local server from the repo root:

```powershell
python -m http.server 8000
```

Then open:
- `http://localhost:8000/ui/`

## GitHub upload pipeline (Windows + PowerShell, verified)

From the repo root (this folder):

### One-time git identity setup (required before first commit)

Run once (choose your real email/name):

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### Initialize and commit

```powershell
git status -sb
git commit -m "chore: initialize repository documents"
```

If your default branch is `master`, switch to `main`:

```powershell
git branch -M main
git branch --show-current
```

### Create GitHub repo and push

1) Create an empty repository on GitHub (no README/.gitignore).

2) Add remote and push:

```powershell
git remote add origin <YOUR_GITHUB_REPO_URL>
git remote -v
git push -u origin main
```

### Day-to-day flow (feature branches + PR)

```powershell
git checkout -b feature/<short-name>
git add .
git commit -m "feat: <message>"
git push -u origin HEAD
```

## Data and privacy

By default, the platform should only ingest **publicly available** content.
When storing data:
- Avoid collecting personal data unless explicitly required
- Store only what you need for trend analysis
- Protect stored content and logs from accidental leaks


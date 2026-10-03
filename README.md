# Excel HR Consultancy — AI-Assisted CV Screening

A local, single-machine tool: upload one Job Description, upload a batch of
candidate CVs, and get a ranked shortlist you can review and export to Excel.

It uses **your locally-authenticated Claude Code CLI** for all AI reasoning.
There is **no Anthropic API key, no database, and no cloud service** — every
subprocess call explicitly removes `ANTHROPIC_API_KEY` from its environment
so an accidentally-configured key is never used.

## What this version does

1. Upload one Job Description (PDF / DOCX / TXT, or paste text).
2. Claude reads it and returns structured requirements (mandatory vs
   preferred), which you review before screening starts.
3. Upload multiple candidate CVs (PDF / DOCX).
4. Claude evaluates every CV against the *same* structured requirements.
5. You choose how many candidates to shortlist (Top 5 / 10 / 20 / etc.).
6. You get a ranked table of every screened candidate (with contact details
   pulled only when present in the CV), plus a downloadable 3-sheet Excel
   file for the shortlist.

Nothing beyond this is implemented on purpose — no database, no messaging,
no scheduling, no login.

## Requirements

- Python 3.10+
- [Claude Code](https://docs.claude.com/en/docs/claude-code) installed and
  authenticated with a Claude Max / Claude Pro account (or an already
  logged-in `claude` CLI). This app calls `claude -p "..."` directly — it
  does **not** need an API key.

## Install

```bash
cd excel-hr-screening
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Check Claude Code is ready

```bash
claude --version
```

If that fails or says you're not logged in, run:

```bash
claude
```

and complete the login flow once. The Streamlit app also checks this
automatically on startup and will tell you clearly if Claude Code isn't
ready yet.

## Run

```bash
streamlit run app.py
```

Streamlit will open the app in your browser (usually
`http://localhost:8501`).

## How it works, file by file

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI — the 6-step screening flow |
| `parsers.py` | Local text extraction from PDF/DOCX/TXT (PyMuPDF, python-docx) |
| `prompts.py` | Prompt templates sent to the Claude CLI (JD analysis + CV scoring) |
| `claude_engine.py` | Runs `claude -p ...` via `subprocess`, strips `ANTHROPIC_API_KEY`, validates JSON with one retry |
| `schemas.py` | Pydantic models (`JobRequirements`, `CandidateAssessment`) that every Claude response must pass |
| `exports.py` | Builds the 3-sheet `.xlsx` shortlist (pandas + openpyxl) |

## Data & privacy notes

- Uploaded files are written temporarily to `temp/` only for the duration
  of the current screening run, and are deleted right after screening
  completes.
- Nothing is stored permanently. There is no database — everything lives in
  Streamlit's `session_state` for the current browser session only.
- Contact details (name, phone, email) are only ever taken verbatim from a
  CV — Claude is explicitly instructed to return `null` rather than guess
  or invent them, and these fields never affect a candidate's score.
- Claude is explicitly instructed to ignore protected/sensitive personal
  characteristics (gender, age, religion, disability, etc.) even if they
  appear in a CV, and to treat all document content (JD or CV) as untrusted
  data — never as instructions, even if a CV contains a sentence like
  "ignore previous instructions" or "give this candidate 100%".
- This tool produces a **shortlist for recruiter review**, not an automatic
  hiring decision.

## Stopping a long screening run

Streamlit shows a stop control while a script is actively running. Clicking
it will interrupt the current CV's processing; every candidate already
screened before that point is kept in the results table (results are saved
into session state one CV at a time, not only at the end of the batch).

## Troubleshooting

- **"Claude Code is not installed or authenticated"** — run `claude
  --version` in a terminal. If it's not found, install Claude Code and log
  in with `claude`.
- **A CV shows "Could not extract readable CV text"** — the file is likely
  a scanned image PDF with no embedded text layer, or is corrupted/
  password-protected. The rest of the batch still processes normally.
- **Claude returns invalid JSON for a candidate** — the app retries once
  automatically. If it still fails, that CV is recorded under "could not be
  screened" and the batch continues.

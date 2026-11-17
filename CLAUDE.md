# CLAUDE.md

Instructions for AI assistants working in this repo.

- **Source of truth:** `planning/03_spec_v2.1_turnout_report.md`. Record any change to it while building in `planning/build_log.md` (what the spec said, what was built, why).
- **Docs:** Markdown by default. Planning docs go in `planning/`.
- **Owner preferences:** Dan codes mostly in Python and likes things step by step. Explain setup and run steps simply; don't assume he knows every command.
- **Decisions:** present them one at a time, with three options (A/B/C) and one recommended.
- **Principles:** LLMs only read; all math is deterministic. Every number traces to its source (a quote, or an XBRL tag + accession). A missing input means a rule doesn't fire, never a guess.
- **Stack:** Python 3.12+, `httpx`, `beautifulsoup4`, `pytest`. Outside services sit behind `Protocol` interfaces so tests use fakes and never hit the network.
- **Run tests:** `pytest`. Keep them passing before every commit.
- **Never commit:** `.env`, `data/raw/`.

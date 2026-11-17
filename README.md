# The Turnout Report

*Restaurants and retailers: are customers showing up, and is the business holding up?*

A free, automated dashboard on the health of U.S. public restaurant and retail chains. It's built on one idea: **people actually showing up and buying is the foundation of these businesses.** When turnout slips, bigger trouble usually follows.

- **Same-Store Vitals:** comp sales, traffic, ticket and store margin, with a badge per chain (True Compounder, Price-Masking Warning, and so on).
- **Company Health:** revenue growth, operating margin, free cash flow, inventory vs. sales and interest coverage, with a Strong / Watch / Stressed grade.

Every number comes from SEC filings and traces back to its source. The full plan is in [`planning/`](planning/).

---

## Status

| Phase | What | Status |
|---|---|---|
| 1 | Fetch and cache filings | ✅ Built |
| 2 | Extract numbers with an LLM, then verify the quotes | Next |
| 3 | Derived signals and badges | — |
| 4 | Company Health from XBRL | — |
| 5 | Full universe and backfill | — |
| 6 | Website | — |
| 7 | Weekly automation | — |

---

## Getting started (Phase 1)

You need **Python 3.12 or newer**. Check with `python --version`.

**1. Get the code**
```bash
git clone https://github.com/danielwipert/retail.turnout.report.git
cd retail.turnout.report
```

**2. Make a virtual environment** (keeps this project's packages separate)
```bash
python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

**3. Install**
```bash
pip install -e ".[dev]"
```

**4. Add your SEC identity.** The SEC requires a name and email on every request. It's not a password.
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
Open `.env` and set:
```
SEC_USER_AGENT="Dan Wipert your.email@example.com"
```

**5. Run the tests** (these use sample data, not the internet)
```bash
pytest
```

**6. Fetch real filings** for the three test chains (Texas Roadhouse, Walmart, Floor & Decor)
```bash
python -m turnout fetch
```
It looks up each company's CIK, finds the last 8 quarters of 10-Q/10-K reports and earnings press releases, and saves them. This takes a few minutes because the SEC asks us to go slowly.

**7. See what you got**
```bash
python -m turnout status
```

---

## Commands

| Command | What it does |
|---|---|
| `python -m turnout fetch` | Fetch the 3 test chains (8 quarters) |
| `python -m turnout fetch --tickers CAKE SHAK` | Fetch specific chains |
| `python -m turnout fetch --all` | Fetch every chain in `data/universe.json` |
| `python -m turnout fetch --quarters 4` | Change how far back to go |
| `python -m turnout fetch --force` | Re-download even if already saved |
| `python -m turnout status` | List saved quarters and anything flagged |
| `python -m turnout resolve-ciks` | Save each chain's SEC CIK number into `data/universe.json` |

---

## Where things are saved

```
data/raw/TXRH/2026-09-29/
  manifest.json      what was fetched, from where, and which 8-K was chosen
  periodic.txt       the 10-Q (or 10-K) as plain text  (.htm = original)
  ex99_1.txt         the earnings press release as plain text
  candidates/        every earnings 8-K considered for this quarter
```

`data/raw/` isn't committed to git. It can always be rebuilt from the SEC.

**Flags in `status`** tell you a quarter needs a quick look:

| Flag | Meaning |
|---|---|
| `multiple_8k_candidates` | More than one earnings 8-K was found (e.g. a preliminary release); the pipeline picked one. Check `manifest.json` → `candidates`. |
| `low_confidence_8k_choice` | The chosen press release didn't clearly look like quarterly results. |
| `no_earnings_8k_found` | No Item 2.02 8-K in the window; only the 10-Q/10-K was saved. |
| `earnings_8k_has_no_ex99` | The 8-K had no press-release exhibit. |

---

## Project layout

```
planning/      specs and build log (the source of truth)
turnout/       Python package
  sources/     talking to outside data sources (SEC so far)
  filings.py   finding each quarter's 10-Q/10-K and earnings 8-K
  cache.py     saving filings to data/raw/
  text.py      HTML → plain text
  cli.py       the `python -m turnout` commands
data/          universe.json (the chains we track) and saved data
tests/         automated tests (no internet needed)
```

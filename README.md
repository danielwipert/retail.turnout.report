# The Turnout Report

*Restaurants and retailers: are customers showing up, and is the business holding up?*

A free, automated dashboard on the health of U.S. public restaurant and retail chains. It's built on one idea: **people actually showing up and buying is the foundation of these businesses.** When turnout slips, bigger trouble usually follows.

- **Same-Store Vitals:** comp sales, traffic, ticket and store margin, with a badge per chain (True Compounder, Price-Masking Warning, and so on).
- **Company Health:** revenue growth, operating margin, free cash flow, inventory vs. sales and interest coverage, with a Strong / Watch / Stressed grade.

Every number comes from SEC filings and traces back to its source. The full plan is in [`planning/`](planning/).

**Everything runs in the cloud on GitHub Actions.** Nothing is ever run on a local computer.

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

## One-time setup: add your SEC identity

The SEC requires a name and email on every request. It's not a password.

1. In this repo on GitHub, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `SEC_USER_AGENT`
4. Secret: your name and email, e.g. `Dan Wipert you@example.com`
5. Click **Add secret**.

(Later phases add `OPENROUTER_API_KEY` and `FRED_API_KEY` the same way.)

---

## Workflows (the "buttons")

| Workflow | When it runs | What it does |
|---|---|---|
| **tests** | Automatically on every push | Runs the automated tests (sample data, no internet) |
| **fetch filings** | When you click **Run workflow** | Downloads 10-Q/10-Ks and earnings releases from the SEC |

**To fetch filings:**
1. Open the **Actions** tab → **fetch filings** → **Run workflow**.
2. Leave the boxes as they are for the 3 test chains (Texas Roadhouse, Walmart, Floor & Decor), or type other tickers, or `ALL`.
3. Click the green **Run workflow** button. A run takes a few minutes, since the SEC asks scripts to go slowly.
4. Open the finished run. The **Summary** shows every saved quarter and any flags. The saved files can be downloaded under **Artifacts → raw-filings**.

Saved filings are reused by the next run, so nothing is downloaded twice.

---

## What gets saved

```
data/raw/TXRH/2026-09-29/
  manifest.json      what was fetched, from where, and which 8-K was chosen
  periodic.txt       the 10-Q (or 10-K) as plain text  (.htm = original)
  ex99_1.txt         the earnings press release as plain text
  candidates/        every earnings 8-K considered for this quarter
```

**Flags in the Summary** tell you a quarter needs a quick look:

| Flag | Meaning |
|---|---|
| `multiple_8k_candidates` | More than one earnings 8-K was found (e.g. a preliminary release); the pipeline picked one. |
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
  cache.py     saving filings
  text.py      HTML → plain text
  cli.py       the commands the workflows run
data/          universe.json (the chains we track)
tests/         automated tests
.github/       the cloud workflows
```

# Build log

What each phase delivered, plus decisions made while building that refine the spec.

---

## Phase 1: Fetch and cache filings · 2026-11-17

**Delivered**
- Package skeleton (`turnout/`), `pyproject.toml`, `.env.example`, README.
- `data/universe.json`: 30 core chains (8 / 8 / 6 / 8 by group) and 23 watch-list candidates. Each has its group, segment, segment keywords, fiscal calendar and confirmation status. CIKs are filled in by `resolve-ciks`.
- SEC client: polite (~6 requests/sec max), retries on 429 and 5xx errors, needs `SEC_USER_AGENT`.
- Filing discovery: the latest N 10-Q/10-Ks, each paired with the earnings 8-Ks (Item 2.02) that could belong to it. Pages back through older submission files when needed.
- Cache in `data/raw/{TICKER}/{period_end}/` with a manifest, HTML and plain text for each document.
- CLI: `fetch`, `status`, `resolve-ciks`.
- 16 tests, all using sample data (no network).

**Refinements to the spec**

| # | Spec said | Built as | Why |
|---|---|---|---|
| B-1 | Cache folder named `{fiscal_period}` | Folder named by **period end date** (e.g. `2026-09-29`) | Period end comes straight from the SEC with no guessing. The fiscal label and calendar quarter get attached in Phase 3. |
| B-2 | "The 8-K with Item 2.02 nearest the quarter end" | **All** Item 2.02 8-Ks filed after the period end, within 75 days and no later than 7 days after the 10-Q/10-K, are kept as candidates. Each press release is scored (quarter-results headline +3, comps language +1, "preliminary" −4, monthly-sales wording −2); highest wins, ties go to the latest. | Restaurants often pre-announce at the January ICR conference, and some retailers file monthly sales 8-Ks. "Nearest" would pick the wrong one. Every candidate is kept for audit. |
| B-3 | Exhibit 99.1 only | Saves **all EX-99 exhibits** (99.1 first) | Some chains (e.g. Shake Shack) put results in a shareholder letter, and supplemental tables are often in 99.2. |

**Cloud-only rule (2026-11-17):** Dan doesn't run anything locally. All runs happen on GitHub Actions:
- `tests.yml` runs on every push.
- `fetch.yml` is started with **Run workflow**. It needs a `SEC_USER_AGENT` repo secret. Filings are kept between runs with the Actions cache, uploaded as a downloadable artifact (30 days), and a run summary lists every saved quarter and its flags. Looked-up CIKs are committed back to `data/universe.json`.
- Long-term storage for filings (beyond the Actions cache) is an open decision. Phase 2 needs to read them.

**Not yet verified live:** the build workspace can't reach sec.gov, so the first real run is the `fetch filings` workflow. Things to check on that first run:
1. Every quarter for TXRH, WMT and FND has an `ex99_1.txt` that is clearly the quarterly results release.
2. Any `multiple_8k_candidates` quarters picked the right release.
3. FND's `periodic.txt` contains the "comparable transactions" sentence.

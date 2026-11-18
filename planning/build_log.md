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

**Live verification (2026-11-17, Actions run 44163075756):** TXRH, WMT and FND each got 8 quarters (2 10-Ks + 6 10-Qs) with one earnings 8-K per quarter, filed 2–6 weeks after the period end, and no flags. A first run flagged 18 quarters `low_confidence` because the "monthly sales" rule matched "thirteen weeks ended", which normal quarterly releases use. Fixed, and the release headline is now in the manifest and the run summary.

Original checklist for the first live run:
1. Every quarter for TXRH, WMT and FND has an `ex99_1.txt` that is clearly the quarterly results release.
2. Any `multiple_8k_candidates` quarters picked the right release.
3. FND's `periodic.txt` contains the "comparable transactions" sentence.

---

## Phase 2: Extract + verify · 2026-11-17

**Decisions (logic gates)**

| Date | Gate | Decision | Why |
|---|---|---|---|
| 2026-11-17 | P2-1 Storage | **Cloudflare R2** for raw filings (`raw/{TICKER}/{period_end}/…`) | Permanent, cheap, already in Dan's stack. Replaces the Actions cache, which evicts after 7 days. |
| 2026-11-17 | P2-2 Model | **Bake-off of 3 models** on the saved quarters; keep the cheapest with zero suspected false passes | Pick on our own data; the model id lives in `data/settings.json`. |
| 2026-11-17 | P2-3 Input | **Keyword snippets first**; any field still missing gets one retry on the full documents | Cheaper and more accurate for small models. Quotes are always checked against the full filing. |
| 2026-11-17 | P2-4 Review | **One GitHub Issue per flagged field**; owner replies `/approve`, `/value X` or `/reject` | Works from any browser or phone, with email notifications and a permanent record. |

**Delivered**
- `turnout/storage.py`: R2 sync (`storage pull` / `storage push`). The pipeline still works on `data/raw/` locally inside each run.
- `turnout/extract/`: fields + strict JSON schema, keyword snippets, OpenRouter extractor (Protocol, temperature 0, structured output, provider must support it), deterministic checks (spec 5.2: quote exists, number in quote incl. `(x)%` and basis points, sign vs words, range, segment keyword in or just before the quote), derived ticket = comp − traffic when ticket isn't stated, arithmetic flag.
- `turnout/extract/bakeoff.py`: per-model verified / flagged / missing / cost, and "suspected false pass" = a verified value that disagrees with the majority of the other models.
- `turnout/review.py`: opens review issues (value, quote, reasons, nearby filing text, SEC links) and applies replies.
- Workflows: `fetch filings` (now uses R2), `model bake-off`, `extract numbers`, `apply review` (runs on owner comments on `review` issues).
- Results: `data/extracted/{TICKER}/{period_end}.json` (committed). Bake-off results: `data/bakeoff/`.

**Refinements to the spec**

| # | Spec said | Built as | Why |
|---|---|---|---|
| B-4 | Review via CLI | Review via GitHub Issues | Decision P2-4 + cloud-only rule. |
| B-5 | Results in `data/quarters/` | Raw extraction results in `data/extracted/`; `data/quarters/` is built in Phase 3 | Keeps "what the filing said" separate from computed signals. |
| B-6 | Status values verified / derived / approved_manual / missing | Adds `flagged` (awaiting review) and `rejected` | Needed for the review loop. |
| B-7 | Segment match = keyword in quote | Keyword in the quote **or within ~2,000 characters before it** | Segment names usually sit in a heading above the sentence. |

**Run order for the first time:** `fetch filings` (fills R2) → `model bake-off` → set `extraction_model` in `data/settings.json` → `extract numbers`.

**Fixes after the first live test (2026-11-17):** quotes from table rows failed "quote in filing" because the model wrote cell separators differently. `normalize()` now ignores `|` and spacing before `%`. The segment lookback was widened from 2,000 to 6,000 characters (TXRH's "Company restaurants" heading sits above a long table). The full-text retry is capped at 150k characters per document. Gemini 2.5 Flash on 3 TXRH quarters returned the right values (Q3 2026: comp 4.4, traffic 0.7, check 3.6) for about $0.02.

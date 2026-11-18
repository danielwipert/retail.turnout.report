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

**Bake-off run 1 (2026-11-17) hit its 60-minute limit.** Models ran one after another, and gpt-oss-20b was slow (about 800s for 27 calls), sometimes returned empty answers, and overflowed its 131k context on WMT full-text retries. Fixes: models now run as **parallel jobs**; full-text retry is capped at 80k characters per document; empty answers are retried; `max_tokens` is 4000. The quote check gained a **token-order fallback**: every word and number of the quote must appear in order in the filing, with at most 3 tokens between each. That handles table rows with blank cells, zero-width characters and trailing punctuation, while still rejecting paraphrases. Saved answers are now **re-checked for free** with the current checker whenever a run reuses them.

**Model locked (2026-11-17, gate P2-2b): Gemini 2.5 Flash** (`data/settings.json`). Bake-off over 24 quarters: verified 108 / flagged 2 / not found 10 at $0.22. Flash-Lite: 106 / 9 / 5 at $0.24. gpt-oss-20b: 105 / 9 / 3 at $0.05, but it made real errors (e.g. TXRH check 5.8 vs 1.8) and reworded quotes.

**Definition gaps found by the bake-off and fixed with per-chain `field_notes`** in `data/universe.json`, which are injected into the prompt:
- TXRH: use "Company restaurants (all concepts)" (comps 4.3% in Q3 2026; 737 company restaurants), not the Texas Roadhouse-brand row (4.4%; 664).
- WMT: Walmart U.S. comp sales ex-fuel, Transactions, Average ticket; Walmart U.S. unit count (not Sam's Club); margin = consolidated gross profit rate.
- FND: comparable transactions and average ticket; warehouse-format store count.
- New prompt rules for all chains: prefer ex-fuel figures; prefer the quarter over year-to-date.
Other chains get notes as they're onboarded in Phase 5.

**Bake-off workflow bug fixed:** each parallel job's artifact contained stale copies of the other models' folders, which overwrote re-checked results when merged. Each job now uploads only its own folder.

**Known gap:** Q4 (10-K) quarters often have no Q4-only traffic or check figure, and all models agree. These stay "missing", never guessed.

**Verified-but-wrong values found on the first real extraction, and the guards added:**
- WMT store count picked "Retail square feet at period end | 698" (Walmart U.S. square footage in millions). → Counts quoting square feet are rejected, and a count's quote must contain a store/restaurant/unit word.
- TXRH store count picked "Total restaurants | 840" (includes franchises). → Per-chain `quote_must_include` (TXRH `ending_units` must say "company") plus sharper notes.
- **Neighbour-quarter check** (`check_series`): a store count more than 15% away from **both** adjacent quarters, or a margin more than 4 points away from both, is flagged for review. This catches "right number, wrong row" that a quote check can't see.
- Review issues that no longer apply after a re-extraction are closed automatically.
- Open question for Dan: FND Q2 2026 GAAP gross margin is 48.2% because of a one-time tariff refund (adjusted: 43.7%).

**Decision P2-5 (2026-11-17): margin basis.** When a company reports both GAAP and adjusted (non-GAAP) margin for the quarter, use **adjusted**; otherwise GAAP. Every margin records `basis: adjusted | gaap`, read deterministically from the quote. Why: one-time items (e.g. FND's Q2 2026 tariff refund: GAAP 48.2% vs adjusted 43.7%) would otherwise trigger false margin-expansion badges. Spec §4.1 `margin_pct` is refined by this.

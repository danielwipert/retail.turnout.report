# Project Specification v2: Retail & Dining Same-Store Vitals Dashboard

> **Archived.** Superseded by `03_spec_v2.1_turnout_report.md`, which contains everything below plus the Company Health layer and the new name.

**Version:** 2.0 · **Date:** 2026-11-17 · **Owner:** Dan Wipert · **Status:** Superseded
**Supersedes:** v1 (Gemini draft, 50-ticker universe)

---

## 0. What changed from v1

| Area | v1 | v2 | Why |
|---|---|---|---|
| Foot traffic | Placer.ai field + Omni-Channel flag | **Removed** | Free tier is limited, and Placer's license bans scraping and systematic API calls. |
| Universe | 50 tickers, "all report traffic/ticket" | **30 core chains + a watch list** | Only 30 report traffic and ticket as numbers in SEC filings. DENN went private; PZZA and NDLS are at risk. |
| Watch list | — | Cut chains that **say in words** which way traffic/ticket moved | Keeps bellwethers like WING and JACK visible without fake numbers. |
| Extraction | Not specified | **Cheap LLM + quote verification** | Comp/traffic aren't in XBRL. Every number must trace to a sentence in the filing. |
| Sector benchmark | FRED NAICS sales YoY | **Peer-group median comp** (FRED = context only) | The FRED limited-service series stopped in 2021, and Census sales include new stores (comps don't). |
| Badges | 5 rules, overlaps undefined | **Fixed priority, worst news first** + secondary tags | A chain can match Distress and Price-Masking at once. |
| Deliverable | — | Markdown spec | Easier for LLMs and diffs. |

---

## 1. Purpose

A free, automated, static dashboard tracking **comp sales, traffic, average ticket and store-level margin** for U.S. public restaurant and retail chains. It exists to separate:

- **Surging chains:** real customer growth, real basket growth and margin leverage.
- **Chains in trouble:** positive comps propped up by price hikes while traffic and margins erode.

### 1.1 Design principles

1. **Every number traces to a quote.** No figure is stored without the exact filing sentence it came from.
2. **Deterministic math.** LLMs only *read*. All derived signals and badges are plain formulas.
3. **Numbers only from SEC filings.** Earnings-call transcripts and news are not sources.
4. **Static-first.** Python on a schedule writes JSON to the repo, and a static site reads it.
5. **Graceful degradation.** A missing input means a rule can't fire. It never means a guess.
6. **Provider abstraction.** The LLM, filing source and macro source sit behind Python `Protocol` interfaces.

---

## 2. Data sources

| Source | Access | Cost | Used for |
|---|---|---|---|
| **SEC EDGAR** | `data.sec.gov/submissions/CIK##########.json` and `www.sec.gov/Archives/...` | Free. Needs a custom `User-Agent`; stay under 10 requests/sec. | 8-K Exhibit 99.1 (earnings release), 10-Q / 10-K MD&A |
| **SEC ticker map** | `www.sec.gov/files/company_tickers.json` | Free | Ticker → CIK lookup at build time |
| **OpenRouter** | Chat completions API | ~cents per quarter | Reading filings (extraction only) |
| **FRED API** | `api.stlouisfed.org/fred/series/observations` | Free key | CPI sub-indices; Census MARTS sector sales (context) |

**Removed:** Placer.ai, BLS direct API (CPI is pulled through FRED instead).

---

## 3. Universe

Same as v2.1 §3 (core 30 in four groups, watch list of cut chains with direction arrows, annual re-check). Difference: in v2.0, watch-list rows got no rating at all.

---

## 4–6. Data contract, extraction pipeline, macro inputs

Identical to v2.1 §4–§6.

---

## 7. Classification

Identical to v2.1 §7 (priority badges: Structural Distress → Price-Masking → True Compounder → Traffic Share Stealer → Stable; secondary tags: also-matched, Cannibalization Alert, Derived Ticket).

---

## 8–9. JSON output and architecture

Same as v2.1 §8–§9, minus the `health` block, `xbrl.py` and `health.py`. Package was named `vitals/`.

---

## 10. Build phases (v2.0)

| Phase | Builds |
|---|---|
| 1. Fetch | Ticker→CIK map, filing discovery, caching for TXRH, WMT, FND |
| 2. Extract + verify | LLM extractor, verification checks, review queue + CLI |
| 3. Compute | Calendar mapping, derived fields, CPI pull, peer medians, badges |
| 4. Full universe | All 30 core + watch-list eligibility, 8-quarter backfill |
| 5. Site | Static dashboard |
| 6. Automation | Weekly Action |

---

## 11. Open items (v2.0)

O-1 to O-5, carried into v2.1 unchanged.

---

## 12. Decision log (v2.0)

| Date | Decision | Why |
|---|---|---|
| 2026-11-15 | Drop Placer.ai and the Omni-Channel flag | Free tier is limited; license bans scraping/systematic API use |
| 2026-11-15 | Only include chains that report traffic and ticket as numbers | Keeps every badge real |
| 2026-11-15 | Vet every chain now; ship a confirmed list + annual re-check rule | List known before code runs |
| 2026-11-15 | 30 core chains + a watch list | Full rigor for the 30, visibility for the big names |
| 2026-11-17 | Watch list uses the filing's own words for direction arrows | Most coverage while staying filing-only |
| 2026-11-17 | Extraction = cheap LLM + quote verification + review queue | Automated, and every number traces to a sentence |
| 2026-11-17 | Share delta measured against peer-group median comp; FRED as context | Same-store vs same-store; FRED limited-service series is dead |
| 2026-11-17 | One badge per chain by fixed priority (worst first) | Resolves rule overlaps, stays deterministic |
| 2026-11-17 | Spec format = Markdown | Easier for LLMs to read |

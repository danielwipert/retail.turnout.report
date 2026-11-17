# Project Specification v2.1: The Turnout Report

**Tagline:** *Restaurants and retailers: are customers showing up, and is the business holding up?*

**Version:** 2.1 · **Date:** 2026-11-17 · **Owner:** Dan Wipert · **Status:** Spec, ready for Phase 1
**Supersedes:** v2.0 (Same-Store Vitals Dashboard) and v1 (Gemini draft, 50-ticker universe)

**Sections of the site**
1. **Same-Store Vitals:** comp sales, traffic, ticket, margin leverage → vitals badge (core 30) or direction arrows (watch list).
2. **Company Health:** five whole-company metrics from SEC structured data → Health grade (every chain).

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
| **Scope (v2.1)** | Same-store metrics only | **+ Company Health layer** (5 metrics, Health grade) | Broadens the dashboard beyond a niche metric. |
| **Name (v2.1)** | Same-Store Vitals Dashboard | **The Turnout Report** | Measures company health built on people showing up; covers restaurants and stores. |

---

## 1. Purpose

A free, automated, static dashboard on the health of U.S. public restaurant and retail chains, built on the foundation of that health: **people actually showing up and buying.** When turnout slips, bigger trouble usually follows. It tracks **comp sales, traffic, average ticket and store-level margin**, plus **whole-company health** (growth, profit, cash, inventory risk, debt risk). It exists to separate:

- **Surging chains:** real customer growth, real basket growth and margin leverage.
- **Chains in trouble:** positive comps propped up by price hikes while traffic and margins erode.

### 1.1 Design principles

1. **Every number traces to its source.** Vitals numbers keep the exact filing sentence they came from; Health numbers keep the XBRL tag and filing accession.
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
| **SEC XBRL company facts** | `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | Free (same limits) | Company Health metrics (§7A). No LLM needed |
| **SEC ticker map** | `www.sec.gov/files/company_tickers.json` | Free | Ticker → CIK lookup at build time |
| **OpenRouter** | Chat completions API | ~cents per quarter | Reading filings (extraction only) |
| **FRED API** | `api.stlouisfed.org/fred/series/observations` | Free key | CPI sub-indices; Census MARTS sector sales (context) |

**Removed:** Placer.ai, BLS direct API (CPI is pulled through FRED instead).

---

## 3. Universe

### 3.1 Core 30 (full metrics + badges)

**Inclusion rule:** the chain reports **comp sales %** and **traffic/transactions %** as numbers, and either **ticket %** or **price/mix %**, in an SEC filing (8-K Ex. 99.1 or 10-Q) for **each of the last 4 quarters**.

**Annual re-check:** every January, re-run the rule on all core and watch-list chains. Chains that fail drop to the watch list, and watch-list chains that pass are promoted.

✓ = confirmed in a 2026 filing or release during spec research. ○ = reported historically; confirm on first run.

#### Limited-Service (8)
| Ticker | Chain | Segment to use | Note |
|---|---|---|---|
| SBUX | Starbucks | North America comps | ✓ |
| BROS | Dutch Bros | Systemwide same-shop | ✓ Also reports company-operated |
| LOCO | El Pollo Loco | System-wide | ✓ Company and franchise splits also reported |
| SHAK | Shake Shack | Company-operated same-Shack | ✓ Traffic + price/mix |
| PTLO | Portillo's | Same-restaurant | ✓ |
| SG | Sweetgreen | Same-store | ✓ Traffic + mix + price |
| CMG | Chipotle | Comparable restaurant | ○ |
| CAVA | Cava | Same-restaurant | ○ |

#### Full-Service (8)
| Ticker | Chain | Segment to use | Note |
|---|---|---|---|
| TXRH | Texas Roadhouse | Company restaurants | ✓ |
| EAT | Brinker | Chili's | ✓ |
| CAKE | Cheesecake Factory | Cheesecake Factory brand | ✓ Traffic + pricing + mix |
| BLMN | Bloomin' Brands | Combined U.S. | ✓ |
| CBRL | Cracker Barrel | Restaurant comps | ✓ Fiscal year ends ~Aug 1 |
| BJRI | BJ's Restaurants | Comparable restaurant | ✓ New in v2 |
| KRUS | Kura Sushi | Comparable restaurant | ✓ New in v2. Fiscal year ends Aug 31 |
| FWRG | First Watch | Same-restaurant | ○ |

#### Mass, Club & Value (6)
| Ticker | Chain | Segment to use | Note |
|---|---|---|---|
| WMT | Walmart | Walmart U.S., ex-fuel | ✓ NRF calendar |
| COST | Costco | U.S., adjusted (ex-gas, ex-FX) | ✓ Fiscal year ends ~Aug 31 |
| TGT | Target | Total comparable | ✓ NRF calendar |
| GO | Grocery Outlet | Comparable store | ✓ |
| DG | Dollar General | Same-store | ○ NRF calendar |
| DLTR | Dollar Tree | Dollar Tree segment | ○ NRF calendar |

#### Home & Specialty (8)
| Ticker | Chain | Segment to use | Note |
|---|---|---|---|
| HD | Home Depot | U.S. comps | ✓ NRF calendar |
| LOW | Lowe's | U.S. comps | ○ NRF calendar |
| FND | Floor & Decor | Comparable store | ✓ New in v2. Traffic is reported in the 10-Q |
| DKS | DICK'S | DICK'S Business only (exclude Foot Locker) | ✓ NRF calendar |
| ULTA | Ulta Beauty | Comparable sales | ○ NRF calendar |
| ASO | Academy Sports | Comparable sales | ○ NRF calendar |
| TSCO | Tractor Supply | Comparable store | ○ |
| FIVE | Five Below | Comparable sales | ○ NRF calendar |

> No traditional grocer qualifies. KR, ACI and SFM don't report traffic as numbers, so the former "Grocery" group is now **Mass, Club & Value**.

### 3.2 Watch list (comp + direction arrows, no badges)

**Inclusion rule:** the chain reports **comp sales % as a number** and its filing **states in words which way** traffic and/or ticket moved. Examples: "lower transactions, partially offset by higher prices" or "flat transactions and a decrease in average basket."

Watch-list rows store:
- `comp_sales_pct` (number)
- `traffic_direction` and `ticket_direction`: each one of `up` / `down` / `flat` / `null`
- the supporting quote for each

Watch-list rows **never** get a vitals badge, a price-masking spread or real ticket growth. They **do** get the full Company Health layer and a Health grade (§7A).

**Starting candidates** (eligibility is tested on first run):
MCD, WEN, DPZ, JACK, WING, DRI, PLAY, BJ, AZO, ORLY, KR, ACI, SFM, TJX, ROST, BURL, BBY, ANF, AEO, BBWI, OLLI, PZZA, NDLS.

**Exits:** a chain is removed when it stops filing with the SEC (take-private, delisting). DENN is excluded from the start because it went private in January 2026.

---

## 4. Data contract

### 4.1 Raw inputs (core chains)

| Field | Type | Definition |
|---|---|---|
| `comp_sales_pct` | float, % YoY | Comparable sales for the chosen segment (ex-fuel / constant currency where the company reports it) |
| `comp_traffic_pct` | float, % YoY | Comparable transactions / guest counts / customer visits |
| `comp_ticket_pct` | float, % YoY | Average check / ticket / basket, or price + mix combined |
| `ticket_is_derived` | bool | `true` if ticket = comp − traffic because the filing didn't state it |
| `ending_units` | int | Store count at period end, for the chosen segment |
| `margin_pct` | float, % | Restaurant-level margin (restaurants) or gross margin (retail) |
| `margin_type` | enum | `restaurant_level` / `gross` / `segment_profit` |

### 4.2 Derived signals (pure formulas)

| Field | Formula | Meaning |
|---|---|---|
| `net_unit_growth_pct` | `(units_t − units_t−4) / units_t−4 × 100` | Store-base growth |
| `margin_yoy_bps` | `(margin_t − margin_t−4) × 100` | Store-level leverage (+) or squeeze (−) |
| `price_masking_spread` | `comp_ticket_pct − comp_traffic_pct` | Price doing the work instead of customers |
| `real_ticket_growth_pct` | `comp_ticket_pct − group_cpi_yoy` | Basket growth after inflation |
| `peer_share_delta_pct` | `comp_sales_pct − median(comp_sales_pct of other core chains in same group, same calendar quarter)` | Gaining or losing ground against peers |

**Peer median rules:** leave the chain itself out of its own median. If fewer than 3 peers have data for the quarter, `peer_share_delta_pct = null`.

**History requirement:** `margin_yoy_bps` and `net_unit_growth_pct` need the same quarter last year, so Phase 1 backfills **8 quarters** per chain.

### 4.3 Provenance (every extracted field)

```json
"comp_traffic_pct": {
  "value": 0.7,
  "quote": "Comparable sales increased 4.3% ... driven by a 3.6% increase in average check and 0.7% traffic growth.",
  "source_doc": "8-K Ex-99.1",
  "accession": "0001289460-26-0000XX",
  "status": "verified"
}
```

`status` is one of `verified` / `derived` / `approved_manual` / `missing`.

---

## 5. Extraction pipeline

### 5.1 Steps per chain per quarter

1. **Find filings.** Read `submissions/CIK….json`. Find the 8-K with Item 2.02 nearest the quarter end and download Exhibit 99.1. Also note the matching 10-Q / 10-K.
2. **Cache.** Save the raw HTML and the extracted plain text to `data/raw/{ticker}/{fiscal_period}/`. Never re-download a cached accession.
3. **Extract (LLM).** Send the plain text to a cheap OpenRouter model with a fixed prompt and JSON schema. For each field, the model returns `value` and the **verbatim `quote`**, or `null`. For watch-list chains, it returns direction enums and quotes instead.
4. **Fallback.** If traffic or ticket is `null` from the 8-K, repeat step 3 on the 10-Q MD&A (FND needs this).
5. **Verify (Python, deterministic).** See 5.2.
6. **Route.** If all checks pass, write the record to `data/quarters/`. If any check fails, write it to `data/review/{ticker}_{period}.json`.
7. **Review CLI.** `python -m turnout review` shows each failed item with its quote and lets you approve, edit or reject it. Approved items get `status: approved_manual`.

### 5.2 Verification checks

| Check | Rule |
|---|---|
| Quote exists | After normalizing whitespace and quote characters, `quote` is a substring of the filing text |
| Number in quote | `abs(value)` appears in the quote. Accepts `2.9%`, `(2.9%)`, `(2.9) %` and `290 basis points` (→ 2.9) |
| Sign matches words | If the quote says *decrease / decline / fell / down / lower* next to the number, `value < 0`. If it says *increase / grew / up / higher*, `value > 0` |
| Arithmetic sanity | When comp, traffic and ticket are all stated, `abs(comp − (traffic + ticket)) ≤ 0.5`. If not, flag it; don't reject |
| Segment match | The quote mentions the segment keyword set for that ticker (e.g. "U.S.", "DICK'S Business", "Chili's") when one is configured |
| Plausible range | Comp, traffic and ticket fall between −40 and +40. Margin falls between 0 and 70 |

### 5.3 LLM settings

- **Model:** a cheap model via OpenRouter (pick at build time). Temperature 0. JSON mode / response schema.
- **Interface:** `class Extractor(Protocol): def extract(self, text: str, schema: dict) -> dict`.
- **Prompt rules:** never compute, convert or infer; copy the sentence exactly; return `null` if not stated.
- **Small calls:** one call per filing per chain, never a batch of chains.

---

## 6. Macro inputs (FRED)

### 6.1 CPI deflators (for `real_ticket_growth_pct`)

Use **not-seasonally-adjusted** series for year-over-year change. Quarterly value = average of the 3 monthly YoY % changes in that calendar quarter.

| Group | Series (FRED ID) |
|---|---|
| Limited-Service | CPI-U Food Away From Home (`CUUR0000SEFV`) |
| Full-Service | CPI-U Food Away From Home (`CUUR0000SEFV`) |
| Mass, Club & Value | **Open item O-1:** see section 11 |
| Home & Specialty | CPI-U Commodities Less Food & Energy (`CUUR0000SACL1E`) |

### 6.2 Sector context lines (display only, not in any formula)

| Group | Series | Status |
|---|---|---|
| Both restaurant groups | Food Services & Drinking Places (`MRTSSM722USN`) | Live (confirmed) |
| Mass, Club & Value | Census general merchandise series | Confirm ID at build |
| Home & Specialty | Census building materials / GAFO series | Confirm ID at build |

The limited-service (`MRTSSM7222USN`) and full-service splits are **not used**, because the limited-service series stopped updating in May 2021.

### 6.3 Calendar alignment

Each fiscal quarter is assigned to the **calendar quarter that contains the majority of its days**. For example, an NRF Q3 ending Nov 1, 2026 (Aug 3 – Nov 1) → `2026-Q3`. 16-week quarters (COST Q4, KRUS) follow the same majority rule. The original `fiscal_period` and `period_end_date` are always stored.

---

## 7. Classification

### 7.1 Primary badge: first match wins, worst news first

| Priority | Badge | Rule |
|---|---|---|
| 1 | 🔴 **Structural Distress** | `traffic < −2.0` AND `margin_yoy_bps < −50` |
| 2 | 🟠 **Price-Masking Warning** | `comp > 0` AND `traffic < −1.0` AND `price_masking_spread > 3.0` |
| 3 | 🟢 **True Compounder** | `traffic > 1.5` AND `real_ticket > 0.0` AND `margin_yoy_bps ≥ 0` |
| 4 | 🔵 **Traffic Share Stealer** | `traffic > 1.5` AND `real_ticket ≤ 0.0` |
| 5 | ⚪ **Stable / Transitional** | Nothing above matched |

**Null rule:** if any input a rule needs is `null`, that rule can't match and evaluation moves to the next rule. A chain with no traffic number at all gets ⚪ plus the tag `Insufficient data`.

### 7.2 Secondary tags

- **Also-matched:** every lower-priority badge rule that also matched, e.g. a 🔴 chain tagged `also: Price-Masking`.
- **Cannibalization Alert:** `net_unit_growth_pct > 6.0` AND `traffic < −1.5`.
- **Derived Ticket:** shown when `ticket_is_derived = true`.

(v1's Omni-Channel Divergence flag is removed along with Placer.)

---

## 7A. Company Health layer

Applies to **every chain**: the core 30 and the watch list. It's fully deterministic, with no LLM, and comes from SEC XBRL company facts.

### 7A.1 Raw XBRL concepts

Each concept has an ordered fallback list of tags. The pipeline uses the first tag that has data and records which tag it used.

| Concept | Tag fallback order (us-gaap) |
|---|---|
| Revenue | `Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax` → `SalesRevenueNet` |
| Operating income | `OperatingIncomeLoss` |
| Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` |
| Capital spending | `PaymentsToAcquirePropertyPlantAndEquipment` → `PaymentsToAcquireProductiveAssets` |
| Inventory | `InventoryNet` → `InventoryFinishedGoods` |
| Interest expense | `InterestExpense` → `InterestExpenseNonoperating` → `InterestExpenseDebt` |

A per-ticker override map (`data/xbrl_overrides.json`) handles companies that use custom tags.

### 7A.2 Quarter math

- **Income statement items** come straight from each 10-Q. **Q4 = full year (10-K) − first nine months.**
- **Cash flow items** are reported year-to-date in 10-Qs. **Quarterly value = this YTD − last quarter's YTD** (Q1 is used as-is).
- **TTM (trailing 12 months)** = sum of the last 4 quarterly values.
- **Inventory** is a point-in-time balance at quarter end.

### 7A.3 The five health metrics

| Field | Formula | Question it answers |
|---|---|---|
| `revenue_growth_pct` | `(rev_t − rev_t−4) / rev_t−4 × 100` | Is the whole company growing, counting new stores? |
| `op_margin_yoy_bps` | `(op_inc_t/rev_t − op_inc_t−4/rev_t−4) × 10,000` | Is the company as a whole getting more profitable? |
| `fcf_margin_ttm_pct` | `(OCF_ttm − capex_ttm) / rev_ttm × 100` | Is it producing cash after reinvesting? |
| `inventory_sales_spread_pct` | `inventory YoY % − revenue YoY %` (**retail groups only**; restaurants = `null`) | Is stock piling up faster than sales? (markdown risk) |
| `interest_coverage_ttm` | `op_inc_ttm / interest_ttm` (interest ≤ 0 or missing with no debt → `"no_debt"`) | Can it comfortably carry its debt? |

Unit growth (§4.2) stays in the Vitals section; the Health section shows it as context only.

**Lease note:** restaurant and store rents are operating costs, not interest, so coverage understates the burden for lease-heavy chains. The chain page notes this.

### 7A.4 Health grade: first match wins

| Priority | Grade | Rule (any one condition triggers it) |
|---|---|---|
| 1 | 🔴 **Stressed** | `interest_coverage_ttm < 2.0` · `fcf_margin_ttm_pct < 0` · `inventory_sales_spread_pct > 10` |
| 2 | 🟡 **Watch** | `interest_coverage_ttm < 4.0` · `fcf_margin_ttm_pct < 2.0` · `op_margin_yoy_bps < −100` · `revenue_growth_pct < 0` · `inventory_sales_spread_pct > 5` |
| 3 | 🟢 **Strong** | None of the above, **and** revenue, operating margin and FCF are all non-null |
| — | ⚪ **Insufficient data** | Revenue, operating margin or FCF is null |

Each grade lists the condition(s) that triggered it, e.g. `Watch: revenue_growth_pct −1.2`. Thresholds are starting defaults (open item O-6).

### 7A.5 Checks (deterministic)

| Check | Rule |
|---|---|
| Quarters add up | `Q1+Q2+Q3+Q4` revenue within 0.5% of the 10-K full year |
| Tag continuity | If the chosen tag changes between quarters, flag for review |
| Plausible range | Revenue growth within ±60%; op margin between −50% and 60% |
| Segment caveat | Health uses **consolidated** totals (e.g. DKS includes Foot Locker; COST is worldwide). The chain page says so. |

---

## 8. JSON output

### 8.1 `data/quarters/2026-Q3.json`

Values below are **illustrative** except TXRH's reported figures (comp 4.3, traffic 0.7, check 3.6, margin 14.6, +30 bps, revenue +9.5%) and JACK's quotes. All `health` values other than TXRH revenue growth are placeholders. CIK, dates and accession numbers are placeholders; the pipeline fills real ones.

```json
{
  "calendar_quarter": "2026-Q3",
  "generated_at": "2026-11-17T18:00:00Z",
  "spec_version": "2.1",
  "macro": {
    "cpi_yoy": {
      "food_away_from_home": 3.4,
      "mass_club_value": 2.0,
      "core_goods": 0.6
    },
    "sector_context_yoy": {
      "food_services_drinking": 3.1
    }
  },
  "peer_medians": {
    "full_service": { "comp_sales_pct": 1.9, "n": 8 }
  },
  "core": [
    {
      "ticker": "TXRH",
      "company_name": "Texas Roadhouse, Inc.",
      "cik": "0001289460",
      "group": "full_service",
      "segment": "Company restaurants",
      "fiscal_period": "FY2026-Q3",
      "period_end_date": "2026-09-29",
      "metrics": {
        "comp_sales_pct": 4.3,
        "comp_traffic_pct": 0.7,
        "comp_ticket_pct": 3.6,
        "ticket_is_derived": false,
        "ending_units": null,
        "margin_pct": 14.6,
        "margin_type": "restaurant_level"
      },
      "derived": {
        "net_unit_growth_pct": null,
        "margin_yoy_bps": 30,
        "price_masking_spread": 2.9,
        "real_ticket_growth_pct": 0.2,
        "peer_share_delta_pct": 2.4,
        "badge": "Stable / Transitional",
        "tags": []
      },
      "health": {
        "revenue_growth_pct": 9.5,
        "op_margin_yoy_bps": -20,
        "fcf_margin_ttm_pct": 6.1,
        "inventory_sales_spread_pct": null,
        "interest_coverage_ttm": "no_debt",
        "grade": "Strong",
        "triggers": [],
        "xbrl_tags_used": { "revenue": "Revenues" }
      },
      "provenance": { "...": "one entry per extracted field, see 4.3" }
    }
  ],
  "watch_list": [
    {
      "ticker": "JACK",
      "comp_sales_pct": -1.1,
      "traffic_direction": "down",
      "ticket_direction": "up",
      "health": { "grade": "Watch", "triggers": ["revenue_growth_pct < 0"] },
      "quotes": {
        "comp_sales_pct": "Same-store sales declined 1.1% in the third quarter ...",
        "direction": "Sales performance resulted primarily from a decline in transactions, partially offset by an increase in price."
      }
    }
  ]
}
```

### 8.2 Other files

| Path | Contents |
|---|---|
| `data/universe.json` | Core and watch-list tickers, group, segment keywords, fiscal calendar type, CIK |
| `data/history/{ticker}.json` | All quarters for one chain (feeds the chain page) |
| `data/review/*.json` | Items that failed verification |
| `data/raw/...` | Cached filings (git-ignored or LFS, decide at build) |

---

## 9. Architecture

```
turnout/
  sources/        sec.py, xbrl.py, fred.py  # Protocol-based fetchers
  extract/        llm.py, prompts/, verify.py
  compute/        derive.py, peers.py, badges.py, calendar.py, health.py
  publish/        build_json.py
  cli.py          # run, backfill, review, recheck-universe
site/             # static frontend (reads data/*.json)
data/
.github/workflows/quarterly.yml
```

- **Python 3.12.** HTTP via `httpx`, HTML text via `selectolax` or `BeautifulSoup`.
- **Schedule:** a GitHub Actions cron runs **weekly**. A run only does work when a new 8-K or 10-Q has appeared since the last run. Earnings dates are spread out, so weekly catches everything without guessing dates.
- **Secrets:** `OPENROUTER_API_KEY`, `FRED_API_KEY`, `SEC_USER_AGENT` as GitHub secrets.
- **Hosting:** GitHub Pages.

---

## 10. Build phases (each one runs on its own)

| Phase | Builds | Done when |
|---|---|---|
| 1. Fetch | Ticker→CIK map, filing discovery, caching for 3 test chains (TXRH, WMT, FND) | Raw 8-K and 10-Q text for 8 quarters is on disk |
| 2. Extract + verify | LLM extractor, all 5.2 checks, review queue + CLI | Test chains produce verified records; a deliberately broken quote lands in review |
| 3. Compute | Calendar mapping, derived fields, CPI pull, peer medians, badges | `2026-Q3.json` builds for the test chains with correct badges (hand-check) |
| 4. Company Health | XBRL fetch, tag fallback + overrides, quarter math, 5 metrics, Health grade | Test chains' health numbers match their 10-Q/10-K by hand; "quarters add up" check passes |
| 5. Full universe | All 30 core + watch-list eligibility pass, 8-quarter backfill (vitals + health) | Universe test report shows which ○ chains pass; review queue cleared |
| 6. Site | The Turnout Report: two sections (Same-Store Vitals, Company Health), quadrant grid, group tables, chain pages showing badge + Health grade, watch list | Site renders from JSON on GitHub Pages |
| 7. Automation | Weekly Action, new-filing detection, commit of updated JSON | A new filing triggers an update with no manual step |

---

## 11. Open items (decide during build)

| ID | Question | Default if not decided |
|---|---|---|
| O-1 | CPI deflator for Mass, Club & Value (they sell food *and* goods) | 50/50 blend of Food at Home (`CUUR0000SAF11`) and Commodities Less Food & Energy |
| O-2 | Which cheap OpenRouter model to use for extraction | Benchmark 2–3 models on Phase 2 test chains; pick the cheapest with zero false verifications |
| O-3 | Exact FRED IDs for the retail context lines | Confirm on FRED at build time |
| O-4 | Commit raw filings to git, or keep them local only | Keep local only; cache rebuilds from SEC |
| O-5 | Site design direction | Separate design pass after Phase 5 |
| O-6 | Health grade thresholds (§7A.4) | Use the defaults; tune after seeing the first full quarter across all chains |
| O-7 | Whether to add lease-adjusted coverage later | Not in v2.1; revisit if restaurant grades look too generous |

---

## 12. Decision log

| Date | Decision | Why | Where it lives |
|---|---|---|---|
| 2026-11-15 | Drop Placer.ai and the Omni-Channel flag | Free tier is limited; license bans scraping/systematic API use | §0, §2, §7.2 |
| 2026-11-15 | Only include chains that report traffic and ticket as numbers | Keeps every badge real; preserves "strict uniformity" | §3.1 |
| 2026-11-15 | Vet every chain now; ship a confirmed list + annual re-check rule | List known before code runs | §3.1 |
| 2026-11-15 | 30 core chains + a watch list | Full rigor for the 30, visibility for the big names | §3 |
| 2026-11-17 | Watch list uses the filing's own words for direction arrows | Most coverage while staying filing-only | §3.2 |
| 2026-11-17 | Extraction = cheap LLM + quote verification + review queue | Automated, and every number traces to a sentence | §5 |
| 2026-11-17 | Share delta measured against peer-group median comp; FRED as context | Same-store vs same-store; FRED limited-service series is dead | §4.2, §6.2 |
| 2026-11-17 | One badge per chain by fixed priority (worst first); others become tags | Resolves rule overlaps, stays deterministic | §7 |
| 2026-11-17 | Spec format = Markdown | Easier for LLMs to read; default for all specs | This file |
| 2026-11-17 | Broaden with a whole-company health layer from SEC XBRL | Same free source, deterministic, covers every chain incl. watch list | §2, §7A |
| 2026-11-17 | Five health metrics: revenue growth, op margin change, FCF margin, inventory vs. sales, interest coverage | Covers growth, profit, cash, inventory risk, debt risk with light upkeep | §7A.3 |
| 2026-11-17 | Separate Health grade (Strong / Watch / Stressed); vitals badge unchanged | Two clear verdicts; watch list gets a rating too | §7A.4 |
| 2026-11-17 | Broader umbrella name; Same-Store Vitals becomes a section | What we measure is company health built on people showing up | Title, §0 |
| 2026-11-17 | Name = **The Turnout Report** | Covers restaurants and stores equally; short; no conflicting product found | Title |

---

## Appendix A: Evidence notes from spec research

- **FRED:** `MRTSSM7222USN` (Limited Service Eating Places) last updated May 2021; `MRTSSM722USN/USS` (Food Services & Drinking Places) is current.
- **Placer.ai:** the free version is deliberately limited; the license prohibits web scraping and systematic API calling.
- **Denny's:** take-private by TriArtisan consortium completed Jan 16, 2026.
- **Papa John's:** in take-private talks during 2026 (Irth Capital, TriArtisan reported).
- **Noodles & Co.:** received a Nasdaq delisting determination (Dec 2025); did a 1-for-8 reverse split in Feb 2026.
- **FND:** reports comparable transactions and average ticket in its 10-Q, not its 8-K headline.
- **Direction-only examples:** JACK ("decline in transactions, partially offset by an increase in price"), OLLI ("flat transactions and a decrease in basket"), WING ("lower transaction volumes").

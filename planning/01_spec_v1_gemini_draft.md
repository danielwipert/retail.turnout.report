# Project Specification: Retail & Dining Same-Store Vitals Dashboard

## 1. Executive Summary & Project Goal

### 1.1 Purpose
Build an automated, zero-cost, static web analytics platform that tracks **same-store sales (SSS)**, **customer traffic/transactions**, **average ticket size**, and **four-wall unit economics** across **50 bellwether U.S. public retail and food-service companies**.

### 1.2 Core Problem Solved
Headline financial dashboards report top-line revenue growth and nominal same-store sales, masking structural deterioration when companies hike prices to hide declining customer foot traffic. By triangulating **SEC quarterly filings**, **Federal Reserve/Census sector sales**, **BLS inflation sub-indices**, and **Placer.ai foot-traffic benchmarks**, this platform exposes:
* **Surging Chains (True Compounders):** Brands growing real customer counts, expanding inflation-adjusted basket sizes, and capturing store-level operating leverage.
* **Chains in Trouble (Price-Masking & Distress):** Brands masking negative customer traffic behind aggressive price increases or store openings while suffering four-wall margin compression.

### 1.3 Design Philosophy
* **Strict Data Uniformity:** Every company in the 50-ticker universe must report the exact same underlying operational KPIs (`Comp Sales %` = `Traffic/Transactions %` + `Average Ticket %`) from identical authoritative public sources.
* **Deterministic Computation:** All derived signals, peer comparisons, and quadrant classifications are calculated via deterministic formulas—no black-box scoring.
* **Local-First, Docs-as-Code Architecture:** Data pipelines run via scheduled Python scripts outputting version-controlled JSON/CSV snapshots directly to GitHub, powering a fast static frontend hosted on GitHub Pages or Cloudflare Pages.

---

## 2. Authoritative Free Public Data Sources

| Source | Endpoint / Access Method | Auth / Cost | Data Extracted |
| :--- | :--- | :--- | :--- |
| **SEC EDGAR API** | `https://data.sec.gov/submissions/CIK{cik}.json`<br>`https://www.sec.gov/Archives/edgar/data/...` | Free (Requires custom `User-Agent` header) | Quarterly 10-Q (Item 2 MD&A), Annual 10-K (Item 7 MD&A), and Form 8-K (Exhibit 99.1) for Comp Sales %, Traffic %, Ticket %, Store Counts, and Store/Gross Margins. |
| **FRED API** | `https://api.stlouisfed.org/fred/series/observations` | Free API Key | Monthly U.S. Census MARTS retail & dining sales series by NAICS code to benchmark brand performance against sector growth. |
| **BLS Public Data API** | `https://api.bls.gov/publicAPI/v2/timeseries/data/` (or mirrored via FRED) | Free | Monthly Consumer Price Index (CPI-U) sub-indices (`Food Away From Home`, `Food at Home`, `Commodities Less Food & Energy`) to deflate nominal ticket growth. |
| **Placer.ai ("The Anchor")** | `https://www.placer.ai/anchor` & Monthly Retail/Dining Index Reports | Free Tier / Public Reports | External physical geolocation foot-traffic YoY % changes to cross-verify physical store visits against SEC completed register transactions. |

---

## 3. Canonical 10-Metric Data Contract

Every ticker in every calendar quarter resolves into an identical 10-field schema:

### 3.1 Raw & Normalized Inputs
1. **`comp_sales_pct`** *(Float, % YoY)*: Comparable store/restaurant sales growth (`ex-fuel` and `constant currency` where applicable).
2. **`comp_traffic_pct`** *(Float, % YoY)*: Comparable customer transactions, guest counts, or check volume growth.
3. **`comp_ticket_pct`** *(Float, % YoY)*: Average check, ticket, or basket size growth (`comp_sales_pct - comp_traffic_pct` if reported implicitly).
4. **`net_unit_growth_pct`** *(Float, % YoY)*: Year-over-year percentage change in ending store count (`(Ending Units_t - Ending Units_{t-4}) / Ending Units_{t-4}`).
5. **`store_or_gross_margin_pct`** *(Float, %)*: Four-wall Restaurant-Level Operating Margin % (for food service) or Gross Margin % (for retail/grocery).
6. **`placer_foot_traffic_yoy_pct`** *(Float, % YoY, Nullable)*: External physical geolocation visit growth YoY % from Placer.ai public indices.

### 3.2 Derived Forensic Signals
7. **`margin_yoy_bps`** *(Integer, bps)*:
   $$\text{Margin YoY (bps)} = (\text{Margin}_t - \text{Margin}_{t-4}) \times 100$$
   *Measures four-wall operating leverage (positive) versus labor/COGS/occupancy squeeze (negative).*
8. **`price_masking_spread`** *(Float, % pts)*:
   $$\text{Price-Masking Spread} = \text{comp\_ticket\_pct} - \text{comp\_traffic\_pct}$$
   *Flags chains using menu/shelf price hikes to mask declining customer counts.*
9. **`real_ticket_growth_pct`** *(Float, % YoY)*:
   $$\text{Real Ticket Growth} = \text{comp\_ticket\_pct} - \text{BLS\_Sector\_CPI\_YoY}$$
   *Strips out macro inflation to reveal true basket expansion (more items per order) vs. pure price pass-through.*
10. **`sector_share_delta_pct`** *(Float, % pts)*:
    $$\text{Sector Share Delta} = \text{comp\_sales\_pct} - \text{FRED\_NAICS\_Sales\_YoY}$$
    *Measures whether the brand is gaining or losing market share relative to its exact NAICS industry peer group.*

---

## 4. Curated 50-Ticker Bellwether Universe

All 50 tickers are pre-screened to guarantee consistent quarterly disclosure of Traffic vs. Ticket splits in SEC filings.

### 4.1 Quick-Service Restaurants (QSR), Pizza & Coffee (12 Tickers)
* **BLS CPI Deflator:** `CUSR0000SEFV` (*CPI: Food Away From Home*)
* **FRED Sector Benchmark:** `MRTSSM722513USN` (*Retail Sales: Limited-Service Eating Places*)
* **Tickers:** `MCD` (McDonald's U.S.), `SBUX` (Starbucks N.A.), `WEN` (Wendy's U.S.), `DPZ` (Domino's U.S.), `BROS` (Dutch Bros), `JACK` (Jack in the Box), `PZZA` (Papa John's N.A.), `WING` (Wingstop Domestic), `LOCO` (El Pollo Loco), `SHAK` (Shake Shack), `PTLO` (Portillo's), `SG` (Sweetgreen).

### 4.2 Fast Casual & Casual Dining (12 Tickers)
* **BLS CPI Deflator:** `CUSR0000SEFV` (*CPI: Food Away From Home*)
* **FRED Sector Benchmark:** `MRTSSM722511USN` (*Retail Sales: Full-Service Restaurants*)
* **Tickers:** `CMG` (Chipotle), `CAVA` (Cava Group), `TXRH` (Texas Roadhouse), `DRI` (Darden / Olive Garden), `EAT` (Brinker / Chili's), `CAKE` (Cheesecake Factory), `BLMN` (Bloomin' Brands / Outback), `PLAY` (Dave & Buster's), `CBRL` (Cracker Barrel), `DENN` (Denny's Domestic), `FWRG` (First Watch), `NDLS` (Noodles & Company).

### 4.3 Grocery, Warehouse Clubs & Value/Convenience (10 Tickers)
* **BLS CPI Deflator:** `CUSR0000SAF11` (*CPI: Food at Home*)
* **FRED Sector Benchmark:** `MRTSSM4451USN` (*Retail Sales: Grocery Stores*)
* **Tickers:** `WMT` (Walmart U.S. ex-fuel), `COST` (Costco U.S. core ex-gas/FX), `KR` (Kroger ID sales ex-fuel), `SFM` (Sprouts Farmers Market), `ACI` (Albertsons ID sales), `BJ` (BJ's Wholesale ex-gas), `GO` (Grocery Outlet), `TGT` (Target Corp.), `DG` (Dollar General), `DLTR` (Dollar Tree Consolidated).

### 4.4 Traditional, Home Improvement & Specialty Retail (16 Tickers)
* **BLS CPI Deflator:** `CUUR0000SACL1E` (*CPI: Commodities Less Food & Energy*)
* **FRED Sector Benchmark:** `GAFO` (*General Merchandise, Apparel, Furniture & Other*)
* **Tickers:** `HD` (Home Depot U.S.), `LOW` (Lowe's U.S.), `TJX` (TJX Companies), `ROST` (Ross Stores), `BURL` (Burlington Stores), `ULTA` (Ulta Beauty), `BBY` (Best Buy Domestic), `DKS` (Dick's Sporting Goods), `ASO` (Academy Sports + Outdoors), `TSCO` (Tractor Supply Co.), `FIVE` (Five Below), `ORLY` (O'Reilly Automotive), `AZO` (AutoZone Domestic), `ANF` (Abercrombie & Fitch), `AEO` (American Eagle Outfitters), `BBWI` (Bath & Body Works N.A.).

---

## 5. Deterministic Classification & Alerting Rules

Each company is assigned a primary quadrant badge every quarter using strict threshold rules:

| Status Badge | Deterministic Rule Condition | Operational Diagnosis |
| :--- | :--- | :--- |
| **🟢 True Compounder (Surging)** | `comp_traffic_pct > 1.5` AND `real_ticket_growth_pct > 0.0` AND `margin_yoy_bps >= 0` | Healthy, organic demand growth. Growing customer counts and real basket size while expanding store margins. |
| **🔵 Traffic Share Stealer** | `comp_traffic_pct > 1.5` AND `real_ticket_growth_pct <= 0.0` | Using value menus, promotions, or price restraint to pack stores and capture market share from peers. |
| **🟠 Price-Masking Warning** | `comp_sales_pct > 0.0` AND `comp_traffic_pct < -1.0` AND `price_masking_spread > 3.0` | Top-line comps look positive only due to price hikes while core customer traffic erodes. |
| **🔴 Structural Distress (In Trouble)** | `comp_traffic_pct < -2.0` AND `margin_yoy_bps < -50` | Severe operational trouble: losing both customer visits and four-wall profitability simultaneously. |
| **⚪ Stable / Transitional** | All other combinations | Mixed or flat performance; monitor sequential quarter-over-quarter inflection. |

### Secondary Forensic Flags
* **Cannibalization Alert:** Triggered when `net_unit_growth_pct > 6.0` AND `comp_traffic_pct < -1.5` (aggressive new store openings cannibalizing existing store trade areas).
* **Omni-Channel Divergence Flag:** Triggered when `abs(comp_traffic_pct - placer_foot_traffic_yoy_pct) > 3.5` (indicates major shift toward digital/delivery conversion if SEC transactions exceed Placer foot traffic, or checkout friction/walk-outs if Placer visits exceed SEC transactions).

---

## 6. Normalization & Parsing Rules

1. **Fiscal-to-Calendar Quarter Alignment:**
   * Traditional retailers (`WMT`, `TGT`, `HD`, `LOW`, `TJX`, `ROST`, `BURL`, `ULTA`, `BBY`, `DKS`, `DG`, `DLTR`, `FIVE`, `ANF`, `AEO`, `BBWI`) operate on a Feb–Jan retail calendar (NRF calendar).
   * The ingestion pipeline maps each company's `fiscal_period` (e.g., `FY26-Q3` ended Oct 31, 2026) to a standardized `calendar_quarter` (`2026-Q3`) based on the quarter end date containing at least 2 months of that calendar quarter.
2. **Ex-Fuel & Domestic Normalization:**
   * Always ingest **ex-fuel / ex-gasoline** comparable figures for `WMT`, `COST`, `KR`, `ACI`, and `BJ` to remove crude oil price volatility.
   * Always prioritize **U.S. / North America / Domestic** segments for multinational chains (`MCD`, `SBUX`, `DPZ`, `PZZA`, `HD`, `LOW`, `BBY`, `AZO`) so metrics align cleanly with U.S. FRED and BLS macro baselines.
3. **Franchise System-Wide vs. Company-Operated Split:**
   * For heavily franchised QSRs (`MCD`, `DPZ`, `WEN`, `PZZA`, `WING`, `DENN`), ingest **U.S. System-Wide Comps** for traffic/ticket demand signals, and **Company-Operated Restaurant Margin %** for four-wall cost pressure.

---

## 7. Data Schema (JSON Output Specification)

### 7.1 `data/quarters/2026-Q3.json`
```json
{
  "calendar_quarter": "2026-Q3",
  "generated_at": "2026-11-15T19:00:00Z",
  "macro_baselines": {
    "food_away_from_home_cpi_yoy": 3.2,
    "food_at_home_cpi_yoy": 1.8,
    "core_goods_cpi_yoy": -0.4,
    "fred_limited_service_sales_yoy": 3.5,
    "fred_full_service_sales_yoy": 2.9,
    "fred_grocery_sales_yoy": 2.1,
    "fred_gafo_sales_yoy": 1.9
  },
  "records": [
    {
      "ticker": "CMG",
      "company_name": "Chipotle Mexican Grill, Inc.",
      "cik": "0001058090",
      "sector": "Fast Casual & Casual Dining",
      "fiscal_period": "FY2026-Q3",
      "period_end_date": "2026-09-30",
      "filing_url": "[https://www.sec.gov/Archives/edgar/data/1058090/](https://www.sec.gov/Archives/edgar/data/1058090/)...",
      "metrics": {
        "comp_sales_pct": 2.1,
        "comp_traffic_pct": 0.8,
        "comp_ticket_pct": 1.3,
        "net_unit_growth_pct": 8.4,
        "store_or_gross_margin_pct": 23.3,
        "placer_foot_traffic_yoy_pct": 1.2
      },
      "derived": {
        "margin_yoy_bps": -120,
        "price_masking_spread": 0.5,
        "real_ticket_growth_pct": -1.9,
        "sector_share_delta_pct": -0.8,
        "status_badge": "Stable / Transitional",
        "flags": ["Cannibalization Watch"]
      }
    }
  ]
}
# `/data/` — OTA Industry & Competitive Intelligence Datasets

This folder is the **single source of truth** for every figure the OTA-Worldmap dashboard renders. It backs the KPI catalog in [`docs/necessary_figures.md`](../docs/necessary_figures.md) and the warehouse schema in [`specs/design.md`](../specs/design.md). Each row carries a `source_url` so the dashboard's **View Source** modal (FR-08.6) can link directly back to the underlying public disclosure.

Generated: 2026-05-21 · Curated by web research over SEC EDGAR, HKEX, IR pages, UNWTO, national tourism boards, Statista, Phocuswright, Skift, and PhocusWire. See `sources.csv` for the full registry (288 unique URLs across 7 datasets).

---

## Folder Layout

```text
data/
├── geo/
│   └── countries.simplified.geo.json    # 30-country boundary polygons (unchanged)
├── seeds/
│   └── seed.py                          # Dev/test seed (synthetic) — kept for backwards compat
├── rivals/
│   ├── rivals.{csv,json}                # 21 OTAs — roster + metadata
│   └── rival_financials.{csv,json}      # 50 rows, FY 2022–2025/TTM
├── market/
│   └── market_growth.{csv,json}         # 139 rows, 30 regions × 2022–2026
├── regions/
│   ├── inbound_tourism.{csv,json}       # 90 rows, 30 regions × 2022–2024
│   └── region_metrics.{csv,json}        # 60 rows, 30 regions × 2023–2024
├── strategy/
│   ├── ai_features.{csv,json}           # 58 AI/ML product launches per rival
│   └── strategy_events.{csv,json}       # 93 M&A, partnership, IPO, leadership events
├── sources.{csv,json}                   # Provenance registry (288 unique URLs)
└── README.md                            # This file
```

Every row in every dataset carries `is_estimated: true | false`. Treat estimated values as directional, not authoritative.

---

## Dataset Reference

### `rivals/rivals.{csv,json}` — 21 rows

The full list from `docs/necessary_figures.md` plus the two subsidiaries (Kayak, Skyscanner) that surfaced organically in the news research. Columns: `id, name, parent, ticker, exchange, hq_country, hq_iso, categories, business_model, ai_strategy, website`.

| Column | Notes |
| --- | --- |
| `id` | UUID5 derived from the canonical name — stable across re-runs of `build_data_files.py`. |
| `categories` | JSON array: `["B2C"]`, `["B2B"]`, `["B2C","B2B"]`, or `["B2C","Meta"]` for meta-search players. |
| `parent` | Helps trace subsidiary financials (e.g. Goibibo → MakeMyTrip Group). |

### `rivals/rival_financials.{csv,json}` — 50 rows

Revenue, gross bookings (GMV / TTV), take rate, and operating margin per rival × fiscal year. Backs the **Operational KPIs (Apples-to-Apples Comparison)** table in `necessary_figures.md`.

| Column | Unit | Notes |
| --- | --- | --- |
| `revenue_usd_millions` | $M | Converted at year-average FX. |
| `gross_bookings_usd_millions` | $M | Total transaction value through the platform. |
| `take_rate_pct` | % | `revenue / gross_bookings × 100`. |
| `operating_margin_pct` | % | `operating_income / revenue × 100`. |
| `room_nights_millions`, `active_customers_millions` | M | Populated where the company discloses it. |
| `segment_breakdown` | JSON object | Geographic % split when published. |
| `source_url` | URL | 10-K, 20-F, 6-K, earnings release, or credible third-party. |
| `is_estimated` | bool | `true` for private companies / forward TTM. |

Source mix: SEC EDGAR (BKNG, EXPE, ABNB, TCOM, MMYT, YTRA), BSE/NSE (EASEMYTRIP, YATRA in India), BME (EDR), and PR-Newswire / Skift / Inc42 / Entrackr / CB Insights / DealStreetAsia for the private players.

### `market/market_growth.{csv,json}` — 139 rows

Regional OTA-relevant market size in $M and YoY growth, 2022–2026, per ISO country. Feeds the **Total Addressable Market (TAM)** denominator and the choropleth coloring of the world map (FR-01).

Definition: "Online travel sales" = flights + hotels + packages + experiences booked through OTAs and OTA-adjacent platforms (a subset of national tourism spend). Source mix: Statista Travel & Tourism outlook, Phocuswright regional reports, Mordor Intelligence, Skift Research, government tourism boards (JNTO, NTTO, INE).

### `regions/inbound_tourism.{csv,json}` — 90 rows

International tourist arrivals (thousands) and tourism receipts ($M) per region × 2022–2024. Feeds **Inbound Tourist Arrivals** and the macro-context KPIs.

Sourced from each country's official statistics office (NTTO US, JNTO Japan, INE Spain, ISTAT Italy, ABS Australia, BPS Indonesia, KTO South Korea, etc.) — UNWTO and World Bank are used only as fallbacks for the small markets (NG, AR).

### `regions/region_metrics.{csv,json}` — 60 rows

`avg_booking_value_usd`, `demand_index` (0–100), `seasonality_index` per region × 2023–2024. `avg_booking_value_usd` is mostly estimated (no public dataset publishes "OTA per-transaction value" by country), derived from STR ADR × ~2 nights + IATA regional airfare averages + national tourism-board per-visitor spend.

### `strategy/ai_features.{csv,json}` — 58 rows

Specific AI/ML feature launches per rival, 2022-01-01 through 2026-05-21. Backs the **AI Velocity**, **Share-of-Voice — AI Features**, and **AI Capability Gap** synthesis layer.

Categories: `GenAI assistant`, `ML pricing`, `Personalization`, `Customer service AI`, `Trip planning`, `Supply optimization`, `Content generation`, `Other AI`.

### `strategy/strategy_events.{csv,json}` — 93 rows

M&A, IPO filings, partnerships, leadership changes, geographic expansions, regulatory events. Backs the **Strategy Recency**, **Rival Strategy Card** (FR-02 + FR-08.3), and feeds the LLM narrative generator.

Categories: `M&A`, `Partnership`, `Product launch`, `Leadership`, `Funding/IPO`, `Geographic expansion`, `Restructuring`, `Regulatory`.

### `sources.{csv,json}` — 288 unique URLs

The provenance registry. Each row groups one source URL with the datasets that cite it and the number of facts derived from it.

---

## How This Maps to the Warehouse Schema (`specs/design.md`)

| Warehouse table | Source file(s) | Notes |
| --- | --- | --- |
| `REGION` | `data/geo/countries.simplified.geo.json` | Pre-existing. |
| `RIVAL` | `data/rivals/rivals.{csv,json}` | Replaces the synthetic `RIVALS` list in `seeds/seed.py`. |
| `RIVAL_FINANCIAL` | `data/rivals/rival_financials.{csv,json}` | Real annual figures. |
| `MARKET_GROWTH` | `data/market/market_growth.{csv,json}` | Annual TAM + growth rate per region. |
| `REGION_METRICS` | `data/regions/region_metrics.{csv,json}` | `avg_booking_value`, `demand_index`. |
| `AI_FEATURE` | `data/strategy/ai_features.{csv,json}` | One row per launch. |
| `STRATEGY_EVENT` | `data/strategy/strategy_events.{csv,json}` | One row per disclosed event. |
| `SOURCE` | `data/sources.{csv,json}` | Provenance registry — `source_url` lookups. |
| `MARKET_SHARE_ESTIMATE` | **Derived at query time** | `share_pct = rival_revenue × geo_weight / market_size` (FR-08.4). |
| `OWN_REGIONAL_FINANCIAL` | **Pending** | The skyticket / ADVENTURE internal P&L — to be populated from the data warehouse, not here. |
| `JOB_POSTING_SNAPSHOT` | **Pending** | Requires a job-board scraping flow (`ingestion/adapters/job_board.py`). |

---

## Loading the Data

### Quick load with Python (pandas)

```python
import json, pandas as pd
fin = pd.read_csv("data/rivals/rival_financials.csv")
mkt = pd.read_csv("data/market/market_growth.csv")
# Cross-join to compute per-rival market share:
own_rev = fin[fin.fiscal_year == 2024].groupby("rival_name")["revenue_usd_millions"].sum()
total_mkt = mkt[mkt.year == 2024]["market_size_usd_millions"].sum()
```

### Load into Postgres (matching `backend/migrations/`)

```bash
psql $DATABASE_URL \
  -c "\\copy rivals FROM 'data/rivals/rivals.csv' WITH CSV HEADER" \
  -c "\\copy rival_financials FROM 'data/rivals/rival_financials.csv' WITH CSV HEADER" \
  -c "\\copy market_growth FROM 'data/market/market_growth.csv' WITH CSV HEADER"
# (etc.)
```

The seed script (`data/seeds/seed.py`) is intentionally kept untouched — it still drives the dev/CI fixture. To switch the dashboard to the real data, point the loader at `data/*.csv` instead of running `seed.py`.

---

## Refresh Cadence (NFR-01)

| Dataset | Refresh | Upstream Cadence |
| --- | --- | --- |
| `rival_financials` | Quarterly | 10-Q / 6-K filings within 24h |
| `market_growth` | Annually | Statista/Phocuswright annual updates |
| `inbound_tourism` | Annually | National statistics offices; UNWTO Q1 release |
| `region_metrics` | Annually | STR/IATA aggregates |
| `ai_features` | Daily | Press releases + corporate blogs |
| `strategy_events` | Daily | RSS + financial news |

When the ingestion pipeline (`ingestion/flows/`) goes live, these flat files become the **fallback** rather than the **primary** data source — every fact will then carry both a `source_url` *and* an extracted raw-payload reference in S3.

---

## Known Limitations

1. **`avg_booking_value_usd` is estimated** for nearly every region — no public dataset publishes OTA-specific per-transaction values by country. Values are derived from STR ADR + IATA airfare averages.
2. **China inbound 2022** is distorted by zero-COVID; the 27.4M figure dominantly counts HK/Macao/Taiwan crossings.
3. **Private OTAs** (ShareTrip, KKday, Kiwi.com, Klook for older years) have sparse financials; rows are flagged `is_estimated=true`.
4. **2026 figures** are forward TTM / consensus for the four US-listed names (BKNG, EXPE, ABNB, TCOM) — explicitly flagged.
5. **Subsidiaries** (Agoda, Kayak, Goibibo, Skyscanner) are not separately disclosed by their parents; their rows are derived from parent segment data and marked accordingly.

For the canonical KPI definitions and refresh contract, see [`docs/necessary_figures.md`](../docs/necessary_figures.md).

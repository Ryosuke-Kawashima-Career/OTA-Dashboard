# OTA Competitive Intelligence Dashboard

A world-map-based dashboard that lets an Online Travel Agency (OTA) and its broader organization benchmark themselves against rivals and against each regional market's growth rate, with full source provenance behind every figure. Built end-to-end on real, public OTA data — no mock numbers in the warehouse.

## Architecture at a Glance

The system follows a four-layer pipeline so that **every figure shown to a user is derived from a real, traceable, public source** (FR-08, FR-08.6):

```text
External Public Sources  ──►  Ingestion  ──►  Storage  ──►  Backend API  ──►  Frontend
  SEC EDGAR · HKEX           Prefect flows    Postgres +     FastAPI         React +
  UNWTO · JNTO               + adapters       PostGIS        services        Leaflet +
  World Bank · IMF           + provenance     warehouse                      Recharts
  Statista · Phocuswright    recorder         (v2 fact
  Booking / Expedia /        + raw-payload    tables +
  Airbnb IR pages            store            sources)
```

Every fact row in the warehouse carries a `source_id` foreign key into a central `sources` registry (one row per `(url, content_hash)`). Estimated values carry an `is_estimated` flag plus a `calculation_method` string — the View-Source modal will surface both. See [specs/design.md](specs/design.md) for the full architecture diagram, data model, KPI catalog, and ingestion design.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19 + TypeScript + Vite |
| Map | Leaflet (react-leaflet) |
| Charts | Recharts |
| State | Zustand |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Migrations | Alembic (0001 → 0009) |
| Ingestion orchestration | Prefect 3 |
| Raw payload store | Local FS (dev) / S3-compatible (prod), content-addressed by SHA-256 |
| Financial parsing toolkit | `pdfplumber`, `beautifulsoup4`, `python-xbrl` (XBRL > regex > LLM fallback chain) |
| HTTP ingestion middleware | `requests` + `urllib.robotparser` + token-bucket rate limiter (per-host, honours `Crawl-delay`) |
| Container | Docker Compose |

---

## Prerequisites

### System Dependencies (macOS)

If you are on macOS, we recommend using **Homebrew** to install the necessary system tools:

```bash
# Install PostgreSQL and PostGIS
brew install postgresql postgis

# Start PostgreSQL service
brew services start postgresql
```

### Language Runtimes

| Tool | Minimum Version | Install |
| --- | --- | --- |
| Node.js | 22 | <https://nodejs.org> |
| Python | 3.12 | <https://python.org> |
| Docker Desktop | latest | <https://docker.com/products/docker-desktop> |
| Git | any | <https://git-scm.com> |

---

## Running the App (after first-time setup)

Three processes must be up, in this order. Use **three separate terminals** so each one streams its own logs.

```bash
# Terminal 1 — Database (detached)
docker compose up -d db

# Terminal 2 — Backend API on :8000
cd backend
source .venv/bin/activate          # macOS / Linux (see Prerequisites for other shells)
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend on :3000
cd frontend
npm run dev
```

Then open **<http://localhost:3000>**. Vite proxies `/api/*` to `:8000`, so no CORS config is needed.

Stop everything:

```bash
# Ctrl-C in the backend and frontend terminals, then:
docker compose stop db             # keeps DB data
# docker compose down -v           # ↳ use -v to also delete the volume
```

Smoke-check the stack in a fourth terminal:

```bash
curl -s http://localhost:8000/healthz                                  # → {"status":"ok"}
curl -s http://localhost:8000/api/regions | jq '.features | length'    # → 233
curl -s http://localhost:8000/api/rivals  | jq '.count'                # → 20 (curated roster minus 1 HQ without map coords)
curl -s http://localhost:8000/api/snapshots                            # → {"months":[…5 years…], "latest":"2026-04-01"}
curl -s http://localhost:8000/api/kpis/global | jq '{markets_covered, tracked_rivals, snapshot_month}'
curl -s http://localhost:8000/api/regions/FR | jq '.name, .demand_index'   # → "France", 83
```

> [!TIP]
> `.venv/bin/activate` is a shell script — it must be **sourced**, not executed. `source .venv/bin/activate` (or `. .venv/bin/activate`) avoids the `zsh: permission denied` error you get from calling it as a program.

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Ryosuke-Kawashima-Career/OTA-Worldmap.git
cd OTA-Worldmap
```

### 2. Start the database

**Option A: Docker (Recommended)**

```bash
docker compose up -d db
```

**Option B: Local PostgreSQL (macOS)**

If you prefer not to use Docker, you must create the database and user manually:

```bash
# Connect to the default postgres database
psql postgres

# Inside the psql prompt:
CREATE ROLE ota WITH LOGIN PASSWORD 'ota_secret' SUPERUSER;
CREATE DATABASE ota_worldmap OWNER ota;
\q
```

### 3. Backend setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
```

Activate it — **choose the line that matches your shell**:

| Shell | Command |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows CMD | `.venv\Scripts\activate.bat` |
| Git Bash / WSL | `source .venv/Scripts/activate` |
| macOS / Linux | `source .venv/bin/activate` |

Your prompt will show `(.venv)` when active. Verify you are using the right Python before continuing:

```bash
which python      # Git Bash / macOS / Linux → should end with .venv/...
where python      # Windows CMD / PowerShell → first result must be .venv\...
```

```bash
# Install runtime dependencies into the active venv
pip install -r requirements.txt

# (Optional) Install dev/test tools — linting, type-checking, pytest
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env              # edit if your DB credentials differ

# Apply database migrations (0001 schema → 0009 Phase-8 upsert constraints)
alembic upgrade head

# Seed the warehouse with the real curated OTA dataset:
#   30 regions, 21 rivals (B2C + B2B), 50 rival financials,
#   139 market-growth rows, 60 region metrics, 90 inbound-tourism rows,
#   58 AI features, 93 strategy events, 288 source rows (provenance registry),
#   880 rival_region_snapshots (interim, Phase 1–5 compat).
# All sourced from data/*.csv with publisher URLs preserved in `sources`.
python ../data/seeds/seed.py

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API docs are available at `http://localhost:8000/docs`.

### 4. Frontend setup

Open a second terminal:

```bash
cd frontend

# Install dependencies (use --legacy-peer-deps to avoid React 19 peer conflicts with react-leaflet)
npm install --legacy-peer-deps

# Start the dev server
npm run dev
```

Open `http://localhost:3000` in your browser.

### 5. Interact with the dashboard

Once all three services are up, these user actions should produce the following results:

| Action | Expected result |
| --- | --- |
| Page load at `:3000` | Top app header (title + year slider + compare picker + category chips + KPI selector), KPI tile bar (Markets Covered / Tracked Rivals / Hottest Growth / Last Updated + Export CSV), and the world map centered at [20, 0] zoom 2. 233 country boundaries, 30 color-shaded . 15 violet rival pins, clustered at zoom < 5 . |
| Click a rival pin | Violet summary card slides in top-right with name, HQ, categories (e.g. "B2C / B2B" for Expedia), business model, AI strategy, website. |
| **Click a country** (e.g. France) | Left-side panel slides in within ~320 ms showing KPIs (Demand Index, Avg Booking Value), a 12-month demand bar chart peaking in July, a demographics donut summing to 100%, top routes, and the rival ranking table with **local share + worldwide rank** per rival. |
| Click Australia / Brazil | Same panel — demand chart peaks in **January** (Southern-hemisphere seasonality). |
| Press Esc or click × | Panel closes; map retains current zoom/pan. |
| Switch KPI in header dropdown | Choropleth colors and hover tooltips update atomically. |
| Toggle a category chip (B2C / B2B) | Rival pins with at least one matching category stay; the *Tracked Rivals* tile re-counts live without a refetch. |
| Pick 2+ regions from the **Compare** dropdown | A floating comparison panel appears bottom-right with 5 metric rows × N region columns; the highest cell in each row is highlighted green. Picker has no upper cap and disables only when every seeded region is selected. |
| Drag the **Year** slider (2022 → 2026) | World map choropleth, KPI tiles, open region panel, comparison table, and *Last Updated* badge all re-fetch against the chosen year. |
| Click **Export CSV** | Browser downloads `ota-export-<YYYY-MM-DD>.csv` with one row per region for the active snapshot. |

## Project Structure

```text
OTA-Worldmap/
├── frontend/                          # React 19 + TypeScript (Vite) — Phase 1–5 UI
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx · App.tsx · index.css · types.ts
│   │   ├── api/                       # fetch wrappers for the Phase 1–5 endpoints
│   │   │   ├── regions.ts · regionDetail.ts · rivals.ts
│   │   │   ├── globalKpis.ts          # /api/kpis/global + exportCsvUrl helper
│   │   │   └── snapshots.ts           # /api/snapshots (year slider)
│   │   ├── components/                # WorldMap, RegionPanel, ComparisonPanel,
│   │   │                              # RivalMarkersLayer, KpiHeaderBar, etc.
│   │   ├── stores/                    # Zustand stores (kpi, rival, region, comparison, timePeriod)
│   │   └── utils/                     # colorScale, demographics, comparison + Vitest tests
│   ├── e2e/rivals.spec.ts             # Playwright smoke test (FR-02)
│   └── package.json · vite.config.ts · playwright.config.ts
├── backend/                           # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── main.py                    # FastAPI app + router registration
│   │   ├── config.py · database.py · base.py · snapshot.py
│   │   ├── models/                    # ── v2 provenance-backed schema (Phase 6 + 7b) ──
│   │   │   ├── region.py              # Region, RegionMetrics
│   │   │   ├── rival.py               # Rival (+ parent, hq_iso, ticker, exchange) +
│   │   │   │                          #   RivalRegionSnapshot (interim, Phase 1–5 compat)
│   │   │   ├── market_growth.py       # MarketGrowth (TAM + growth rate per region/year)
│   │   │   ├── rival_financial.py     # RivalFinancial (revenue, take rate, op margin, segments)
│   │   │   ├── own_financial.py       # OwnRegionalFinancial
│   │   │   ├── market_share.py        # MarketShareEstimate (FR-08.4, is_estimated flag)
│   │   │   ├── strategy_event.py      # StrategyEvent + AIFeature (categorised)
│   │   │   ├── inbound_tourism.py     # Inbound arrivals + receipts per region/year
│   │   │   ├── job_posting.py         # JobPostingSnapshot (Phase 9 leading indicator)
│   │   │   └── source.py              # Source registry (FR-08.6 provenance)
│   │   ├── routers/                   # /api/regions, /api/regions/{iso}, /api/snapshots,
│   │   │                              # /api/rivals, /api/kpis/global, /api/export
│   │   │                              # (FR-04b/06/07/08.6 routers land in Phase 10–13)
│   │   └── services/                  # ── Backend services ──
│   │       └── share_estimator.py     # FR-08.4 — derives MarketShareEstimate rows
│   ├── migrations/versions/           # Alembic chain 0001 → 0009
│   │   ├── 0001_initial_schema.py
│   │   ├── 0002_rival_multi_category.py    # category VARCHAR → categories VARCHAR[]
│   │   ├── 0003_source_registry.py         # sources(url, publisher, content_hash, …)
│   │   ├── 0004_financials.py              # market_growth, rival_financial, own_regional_financial
│   │   ├── 0005_market_share.py            # market_share_estimate (is_estimated, method)
│   │   ├── 0006_strategy.py                # strategy_event, ai_feature, job_posting_snapshot
│   │   ├── 0007_rival_metadata.py          # ticker, exchange, strategy_summary, summary_updated_at
│   │   ├── 0008_curated_data_schema.py     # parent, hq_iso, is_estimated/notes pair, inbound_tourism
│   │   └── 0009_phase8_upsert_constraints.py  # unique constraints rival_financial / own_regional
│   ├── scripts/
│   │   └── validate_provenance.py     # Asserts every fact row carries a non-null source_id
│   ├── alembic.ini
│   └── requirements.txt
├── ingestion/                         # ── Phase 7 + 8 ingestion pipeline (FR-08) ──
│   ├── __init__.py · db.py · requirements.txt
│   ├── adapters/                      # One module per external source
│   │   ├── _base.py                   # AdapterExtraction / FactRow / run_adapter()
│   │   ├── _http.py                   # HttpClient (robots.txt + token bucket, FR-08.5)
│   │   ├── _financials_fixture.py     # Shared rival_financials.csv reader for SEC/HKEX/IR
│   │   ├── echo.py                    # Synthetic adapter — proves the pipeline (T-7.5)
│   │   ├── unwto.py                   # UNWTO tourism stats → inbound_tourism
│   │   ├── jnto.py                    # JNTO Japan inbound → inbound_tourism (JP slice)
│   │   ├── world_bank.py              # ST.INT.RCPT.CD API → inbound_tourism
│   │   ├── imf.py                     # SDMX-JSON FX rates (parse_rates exposed)
│   │   ├── industry_research.py       # Statista / Phocuswright / Mordor / IMARC / …
│   │   ├── sec_edgar.py               # Booking, Expedia, Airbnb, MMYT, DESP, Yatra → rival_financial
│   │   ├── hkex.py                    # Trip.com HKEX filings → rival_financial
│   │   ├── ir_page.py                 # Generic HTML IR pages → rival_financial
│   │   └── pdf_report.py              # PDF earnings reports (pdfplumber)
│   ├── flows/                         # Prefect 3 flows
│   │   ├── echo_flow.py               # End-to-end pipeline canary
│   │   ├── monthly_market.py          # NFR-01 monthly — UNWTO + JNTO + 16 research publishers
│   │   └── daily_filings.py           # NFR-01 24h SLA — SEC + HKEX + IR + share_estimator
│   ├── normalizer/schema.py           # upsert(session, target, natural_key, payload, …)
│   ├── provenance/recorder.py         # ON-CONFLICT-DO-NOTHING sources upsert
│   ├── monitor/                       # layout_change_detector.py + alerts.py
│   ├── raw_store/s3_client.py         # LocalRawPayloadStore / S3RawPayloadStore
│   └── tests/                         # 32 pytest cases (raw store, HTTP, layout, Phase 8, echo)
├── data/
│   ├── geo/countries.simplified.geo.json    # Boundaries for 233 countries
│   ├── market/market_growth.csv             # 139 rows · 16 publishers
│   ├── regions/region_metrics.csv           # 60 rows
│   ├── regions/inbound_tourism.csv          # 90 rows
│   ├── rivals/rivals.csv                    # 21 rivals (real, sourced)
│   ├── rivals/rival_financials.csv          # 50 rows · SEC + HKEX + IR
│   ├── strategy/ai_features.csv             # 58 AI features (7 categories)
│   ├── strategy/strategy_events.csv         # 93 events
│   ├── sources.csv                          # 288 distinct source URLs
│   ├── README.md
│   └── seeds/seed.py                        # Loads every CSV into the v2 warehouse (idempotent)
├── docs/walkthrough.md                # Per-phase implementation log
├── specs/
│   ├── user_story.md                  # 知彼知己 vision (president feedback)
│   ├── requirements.md                # FR-01 → FR-08 + NFR-01/02
│   ├── design.md                      # 4-layer architecture · KPI catalog · synthesis rules
│   └── implementation_plan.md         # 14-phase roadmap (0–8 ✅, 9–14 planned)
├── docker-compose.yml
└── pytest.ini · conftest.py
```

---

## API Endpoints

All read endpoints that touch metrics accept an optional `?snapshot_month=YYYY-MM-DD` query parameter. Omit it to get the latest snapshot present in the database; a malformed value returns `400` with an explanatory `detail` message.

> **Phase 6–8 expanded the warehouse (provenance-backed fact tables + real ingestion) but did not yet add new routers.** The user-facing endpoints below still drive the Phase 1–5 UI. The Phase 10–13 endpoints (`/api/benchmark`, `/api/share-trajectory`, `/api/win-loss`, `/api/strategy/{id}`, `/api/narrative`, `/api/sources/{id}`) are scaffolded in [specs/design.md](specs/design.md) and will land alongside their React components.

| Method | Path | Purpose | Response |
| --- | --- | --- | --- |
| `GET` | `/healthz` | Liveness probe | `{"status": "ok"}` |
| `GET` | `/api/snapshots` | List of available snapshot months — drives the year slider | `{ "months": ["2022-04-01", …, "2026-04-01"], "latest": "2026-04-01" }` |
| `GET` | `/api/regions` | Country boundaries merged with the requested KPI snapshot per region. Accepts `?snapshot_month=` | GeoJSON `FeatureCollection` — 233 features; `properties` include `iso_code`, `name`, `continent`, `demand_index`, `avg_booking_value`, `snapshot_month`. Top-level `snapshot_month` echoes the resolved date. |
| `GET` | `/api/regions/{iso_code}` | Region detail for a single country (FR-03 + FR-06). Returns 404 on unknown ISO. Accepts `?snapshot_month=` | `{ iso_code, name, continent, demand_index, avg_booking_value, snapshot_month, monthly_demand, top_routes, demographics, rival_ranking: [{rival_id, name, categories: ["B2C","B2B"]?, market_share_pct, booking_volume, global_rank}] }` |
| `GET` | `/api/rivals` | Rival OTA roster with HQ coordinates. `?category=B2C&category=B2B` filters via Postgres array overlap (rivals carrying *any* of the requested categories match) | `{ "rivals": [{id, name, hq_country, categories: string[], business_model, ai_strategy, website, lat, lng}], "count": n }` |
| `GET` | `/api/kpis/global` | Three header KPIs at the requested snapshot. Accepts `?snapshot_month=` | `{ markets_covered, tracked_rivals, hottest_growth_region: {iso_code, name, demand_index} \| null, snapshot_month }` |
| `GET` | `/api/export` | One CSV row per region for the requested snapshot. Accepts `?snapshot_month=` | `text/csv` body with header `snapshot_month, iso_code, name, continent, demand_index, avg_booking_value, top_rival, top_rival_share_pct`; `Content-Disposition: attachment; filename="ota-export-<snap>.csv"` |

Interactive OpenAPI docs are available at `http://localhost:8000/docs` when the backend is running.

Smoke-check from the terminal:

```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/api/snapshots                                                # five months 2022 → 2026
curl -s http://localhost:8000/api/regions | jq '.features | length'                        # 233
curl -s http://localhost:8000/api/regions \
  | jq '[.features[] | select(.properties.demand_index != null)] | length'                 # 30
curl -s http://localhost:8000/api/rivals  | jq '.count'                                    # 15
curl -s 'http://localhost:8000/api/rivals?category=B2B' | jq '.count'                      # 8 (5 pure-B2B + 3 dual)
curl -s http://localhost:8000/api/kpis/global \
  | jq '{markets_covered, tracked_rivals, hottest: .hottest_growth_region.name, snapshot_month}'
# → {"markets_covered":30,"tracked_rivals":15,"hottest":"United States","snapshot_month":"2026-04-01"}

# Time-period filter: 2022 vs 2026 shows the seeded recovery curve
curl -s 'http://localhost:8000/api/kpis/global?snapshot_month=2022-04-01' | jq '.hottest_growth_region.demand_index'  # 72
curl -s 'http://localhost:8000/api/kpis/global?snapshot_month=2026-04-01' | jq '.hottest_growth_region.demand_index'  # 92

# Region detail now includes global_rank per rival
curl -s http://localhost:8000/api/regions/FR \
  | jq '{name, demand_index, peak_month: (.monthly_demand | max_by(.value).month), top_rival: .rival_ranking[0] | {name, share: .market_share_pct, global: .global_rank}}'
# → {"name":"France","demand_index":83,"peak_month":7,"top_rival":{...}}
curl -s http://localhost:8000/api/regions/AU \
  | jq '.monthly_demand | max_by(.value).month'                                            # 1 (Southern hemisphere)

# CSV export — headers + first three rows
curl -s -D - http://localhost:8000/api/export | head -5
# Content-Type: text/csv; charset=utf-8
# Content-Disposition: attachment; filename="ota-export-2026-04-01.csv"
```

---

## Development Commands

### Frontend

```bash
cd frontend
npm run dev       # start dev server on :3000
npm run build     # type-check + production build
npm run lint      # ESLint (zero warnings enforced)
npx tsc --noEmit  # TypeScript strict check
npm test          # Vitest unit tests
npm run test:e2e  # Playwright smoke test (needs backend + DB running)
```

First-time Playwright users must install the Chromium binary:

```bash
cd frontend
npx playwright install chromium
```

### Backend

```bash
cd backend
uvicorn app.main:app --reload           # dev server with hot-reload
alembic upgrade head                    # apply all pending migrations
alembic revision --autogenerate -m "x"  # generate migration from model changes
alembic downgrade -1                    # roll back one migration
```

### Database

```bash
docker compose up -d db       # start DB in background
docker compose stop db        # stop DB (keeps data)
docker compose down -v        # stop DB and delete volume
psql -h localhost -U ota -d ota_worldmap   # open psql shell
```

### Ingestion (Phase 7 + 8 — refreshes the warehouse from real public data)

```bash
# Run the two production flows in fixture mode (no network calls; the curated
# CSVs in data/ are the regression baseline for live HTTP mode).
PYTHONPATH=backend:. python -m ingestion.flows.monthly_market   # UNWTO + JNTO + 16 research publishers
PYTHONPATH=backend:. python -m ingestion.flows.daily_filings    # SEC EDGAR + HKEX + IR + share_estimator

# Both flows are idempotent — re-running upserts onto the same source_ids
# (no duplicate fact rows). Expect on first run:
#   MonthlyMarketRunSummary(total_fact_rows=232, …)
#   DailyFilingsRunSummary(total_financial_rows=50, derived_share_rows=112, …)

# Provenance contract — must exit 0 (every fact row carries a source_id):
(cd backend && python scripts/validate_provenance.py)

# Full ingestion test suite (raw store + HTTP + layout detector + Phase 8 adapters + echo):
pytest ingestion/tests -v
```

Each adapter ships in two modes: `fetch_via_http(http_client, …)` for live production and `fetch_from_curated()` / `fetch_from_fixture()` for the offline regression baseline used by the test suite and the flow defaults above.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and adjust if needed:

```env
DATABASE_URL=postgresql://ota:ota_secret@localhost:5432/ota_worldmap
ASYNC_DATABASE_URL=postgresql+asyncpg://ota:ota_secret@localhost:5432/ota_worldmap
```

---

## CI/CD

GitHub Actions runs three jobs on every push and pull request to `main`:

| Job | What it checks |
| --- | --- |
| `frontend` | `tsc --noEmit` + ESLint |
| `backend` | `mypy` type check |
| `db-migration` | `alembic upgrade head` on a live PostGIS container |

---

## Troubleshooting (macOS)

### `FeatureNotSupportedError: extension "postgis" is not available`

This means PostgreSQL is running but cannot find the PostGIS extension files. Ensure you have run `brew install postgis` and restarted your PostgreSQL service:

```bash
brew services restart postgresql
```

### `ValueError: the greenlet library is required`

This occurs when using SQLAlchemy's async driver on certain Python versions (like 3.14). It is included in `requirements.txt`, but if you see this error, run:

```bash
pip install greenlet
```

### `InvalidAuthorizationSpecificationError: role "ota" does not exist`

This means the local PostgreSQL role `ota` has not been created. Follow the "Option B" steps in the Quick Start section to create the role and database.

### `sh: .../vite: Permission denied`

This can happen if the execution bit is missing from the binaries in `node_modules`. Fix it with:

```bash
chmod +x frontend/node_modules/.bin/*
```

### World map is blank at `http://localhost:3000`

The page renders the header but the map area is empty or white. This is almost always a stale-client problem after scaffolding changes — not a code bug. Resolve in this order:

1. Stop both dev servers and clear the Vite module cache, then restart cleanly:

   ```bash
   kill $(lsof -t -i:3000 -i:8000) 2>/dev/null
   rm -rf frontend/node_modules/.vite
   ```

2. Confirm the backend is serving KPIs — `/api/regions` must return 233 features with 30 of them carrying a non-null `demand_index` (see the smoke-check under [API Endpoints](#api-endpoints)). If the count is 0, re-run the seed script.
3. Hard-reload the browser (`⌘⇧R` on macOS, `Ctrl+Shift+R` on Windows/Linux), or open the page in a private window to bypass cached assets.
4. If the map still doesn't appear, open DevTools → Console. A `Map container is already initialized` error points to a `react-leaflet@4` + React 19 StrictMode double-mount; a `Failed to fetch /api/regions` message means the backend isn't actually reachable from Vite's proxy.

# Implementation Plan — OTA Competitive Intelligence Dashboard

**Version:** 1.0
**Last Updated:** 2026-04-18
**Source Spec:** [specs/user_story.md](user_story.md)

---

## 1. Executive Summary

Build a world-map-based competitive intelligence dashboard for the OTA president to monitor rival companies and regional travel market characteristics, prioritizing a working map core before layering analytics on top.

---

## 2. Tech Stack Decision

| Layer | Choice | Rationale |
|---|---|---|
| Frontend Framework | React 19 + TypeScript | Type safety, ecosystem maturity |
| Map Library | Leaflet (react-leaflet) | Open-source, free, and lightweight mapping |
| Charts | Recharts | Lightweight, React-native, composable |
| State Management | Zustand | Simple, minimal boilerplate for dashboard state |
| Backend API | Python + FastAPI | Fast prototyping, async I/O, auto-generated docs |
| Database | PostgreSQL + PostGIS | Relational + geospatial queries |
| Data Ingestion | Python scripts + cron | Scraping/API fetch pipeline, monthly cadence |
| Hosting | Vercel (frontend) + Railway (backend) | Fast deployment, free tier for prototype |

---

## 3. Phase Plan

### Phase 0 — Project Setup

**Goal:** Runnable skeleton, CI, and seed data loaded.

| Task | Output | Acceptance Criteria | Verification |
|---|---|---|---|
| Create monorepo structure | Repo scaffold | `/frontend`, `/backend`, `/data` folders exist | `ls -R` directory check |
| Configure Linting/TypeScript | Config files | Strict mode enabled, zero lint errors | `npm run lint` and `tsc --noEmit` |
| Set up PostgreSQL + PostGIS | DB running | Local and Railway instances accessible | `psql -c "SELECT version();"` |
| Database Migrations | `migrations/` | Schema matches Data Model (Section 4) | `\d` command to verify tables |
| Seed Database | Seed script | 9 rivals and 30 countries loaded | `SELECT COUNT(*)` count check |
| Configure CI/CD | Pipeline | Preview deployments active on Vercel | PR trigger + preview URL validation |

**Milestone:** `http://localhost:3000` loads a blank page and DB connectivity is confirmed.

---

### Phase 1 — Interactive World Map Core

**Goal:** Satisfy FR-01 fully.

| Task | Output | Acceptance | Verification |
|---|---|---|---|
| Leaflet Integration | Map renders | Map visible with OSM tiles | Manual visual check |
| Zoom / pan controls | Controls | Zoom 2–10 works smoothly | Manual interaction trace |
| Fetch /api/regions | Boundaries | All 195 borders drawn | Browser console: GeoJSON check |
| KPI Choropleth | Color layer | Dropdown switches KPI, colors update | Visual vs expected palette |
| Hover Tooltips | Tooltip | Appears within 200ms | Performance monitor (DevTools) |
| KPI Scale Unit Tests | Tests | 100% pass | `npm test` or `vitest` |

**Milestone:** World map with color-coded KPI choropleth is live in staging.

---

### Phase 2 — Rival Company Overlay ✅ [COMPLETED 2026-04-22]

**Goal:** Satisfy FR-02 fully.

| ID | Task | Output | Acceptance | Verification | Status |
|---|---|---|---|---|---|
| T-2.1 | Backend `/api/rivals` | [backend/app/routers/rivals.py](../backend/app/routers/rivals.py) | Returns JSON in < 200ms, supports `?category=` filter | `curl -sw '\n%{time_total}s\n' http://localhost:8000/api/rivals` | ✅ |
| T-2.2 | Rival markers | [RivalMarkersLayer.tsx](../frontend/src/components/RivalMarkersLayer.tsx) | 9 seed rivals visible as violet SVG pins | Visual marker count check at zoom ≥ 6 | ✅ |
| T-2.3 | Marker clustering | `leaflet.markercluster` via `useMap()` | No overlap at zoom < 5 (`maxClusterRadius: 80`) | Manual zoom-out verification | ✅ |
| T-2.4 | Rival summary card | [RivalSummaryCard.tsx](../frontend/src/components/RivalSummaryCard.tsx) | Card opens within 300ms on marker click; Esc + × close | Interaction profiling via DevTools | ✅ |
| T-2.5 | Category filters | [RivalCategoryFilter.tsx](../frontend/src/components/RivalCategoryFilter.tsx) + [rivalStore.ts](../frontend/src/stores/rivalStore.ts) | Toggling a chip adds/removes rivals of that category | Toggle each category manual test | ✅ |
| T-2.6 | Playwright E2E | [e2e/rivals.spec.ts](../frontend/e2e/rivals.spec.ts) + [playwright.config.ts](../frontend/playwright.config.ts) | `npm run test:e2e` exercises marker click, card open/close, chip toggle | `npx playwright install chromium && npm run test:e2e` | Scaffolded — runtime pending DB/browser |

**Milestone:** All 9 seed rivals are clickable on the map with summary cards, filterable by category, and covered by a Playwright smoke test.

---

### Phase 3 — Regional Characteristics Panel ✅ [COMPLETED 2026-04-22]

**Goal:** Satisfy FR-03 fully.

| ID | Task | Output | Acceptance | Verification | Status |
|---|---|---|---|---|---|
| T-3.1 | Backend `/api/regions/{iso}` | [backend/app/routers/regions.py](../backend/app/routers/regions.py) | Returns metrics + monthly_demand + demographics + top_routes + rival_ranking; 404 on unknown ISO | `curl -s http://localhost:8000/api/regions/FR \| jq` | ✅ |
| T-3.2 | Side panel slide-in | [RegionPanel.tsx](../frontend/src/components/RegionPanel.tsx) | Opens in < 400ms via 320ms CSS transform | Manual inspection of `region-panel-slide-in` keyframes | ✅ |
| T-3.3 | Seasonal demand chart | [DemandChart.tsx](../frontend/src/components/DemandChart.tsx) | 12-month Recharts `BarChart`; peaks synthesized from `demand_index` + hemisphere | Northern sample peaks in Jul, Southern in Jan | ✅ |
| T-3.4 | Demographics donut | [DemographicsDonut.tsx](../frontend/src/components/DemographicsDonut.tsx) + [demographics.ts](../frontend/src/utils/demographics.ts) | Segments re-normalize to sum to 100 | `npm test` — 7/7 donut-logic tests in [demographics.test.ts](../frontend/src/utils/demographics.test.ts) | ✅ |
| T-3.5 | Close / collapse UX | `closeRegion()` on Esc + × button | Panel dismounts; map retains bounds | Click-path manual test | ✅ |
| T-3.6 | Rival ranking table | [RivalRankingTable.tsx](../frontend/src/components/RivalRankingTable.tsx) + seed_update for [data/seeds/seed.py](../data/seeds/seed.py) | Dominant rival first; rows ≤ 7 per region; 30 × ~6 rows seeded | `SELECT COUNT(*) FROM rival_region_snapshots;` ≥ 150 | ✅ |

**Milestone:** Clicking any country opens a panel with demand chart, demographics donut, top routes, and rival ranking.

---

### Phase 4 — KPI Header + Comparison View ✅ [COMPLETED 2026-04-30]

**Goal:** Satisfy FR-04 and FR-05.

| ID | Task | Output | Acceptance | Verification | Status |
|---|---|---|---|---|---|
| T-4.1 | Backend `/api/kpis/global` | [backend/app/routers/kpis.py](../backend/app/routers/kpis.py) | Returns `markets_covered`, `tracked_rivals`, `hottest_growth_region`, `snapshot_month`; latency < 200ms | `curl -sw '\n%{time_total}s\n' http://localhost:8000/api/kpis/global` → 30 / 9 / US (92) / 2026-04-01 in 33ms | ✅ |
| T-4.2 | KPI header bar | [KpiHeaderBar.tsx](../frontend/src/components/KpiHeaderBar.tsx) + [api/globalKpis.ts](../frontend/src/api/globalKpis.ts) | Three-tile bar; "Tracked Rivals" recomputes live from `rivalStore.activeCategories` | Toggle category chips → `filteredRivalCount` re-renders without re-fetch | ✅ |
| T-4.3 | Multi-select picker | [ComparisonPicker.tsx](../frontend/src/components/ComparisonPicker.tsx) + [comparisonStore.ts](../frontend/src/stores/comparisonStore.ts) | Unlimited selection; chips removable; restricted to seeded regions; `<select>` disables only when every seeded region is already picked | `addRegion` no-ops on duplicates; dropdown shows only `demand_index !== null` regions | ✅ |
| T-4.4 | Comparison table | [ComparisonPanel.tsx](../frontend/src/components/ComparisonPanel.tsx) | 5 metric rows × N region columns aligned by `selectedIsos` order; renders only when ≥2 regions picked; panel auto-sizes with `min-width 520px` / `max-width calc(100vw - 32px)` and the table scrolls horizontally past that bound | `buildComparisonRows` unit tests assert column order and values per region | ✅ |
| T-4.5 | Highlight winner cell | [comparison.ts](../frontend/src/utils/comparison.ts) + [comparison.test.ts](../frontend/src/utils/comparison.test.ts) | Highest value gets `comparison-table__cell--winner` (green); ties produce no winner; null/NaN never wins | `npm test` — 13/13 comparison tests pass (37/37 total) | ✅ |

**Milestone:** President can compare up to 3 regions in a table with row-level winner highlighting; KPI header bar reflects rival-category filter live. Verified via `npm run lint`, `npm run build` (TS strict), `npm test` (37/37), and live `/api/kpis/global` curl.

#### Small Tweak Phase 4 ✅ [COMPLETED 2026-04-30]

**Situation:** the rival roster only carried B2C OTAs, and `rivals.category` was a single VARCHAR — it couldn't represent OTAs that operate in both segments.

**Resolution:**

- Schema: migration [0002_rival_multi_category.py](../backend/migrations/versions/0002_rival_multi_category.py) drops `category VARCHAR` and adds `categories VARCHAR[]`, backfilling each existing row's prior category as a single-element array.
- Model: [Rival.categories: ARRAY(String(50))](../backend/app/models/rival.py) replaces the scalar field.
- API: [routers/rivals.py](../backend/app/routers/rivals.py) filters via Postgres array overlap (`Rival.categories.overlap(...)`), so `?category=B2B` matches both pure-B2B rivals and dual-category ones.
- Seed: [seed.py](../data/seeds/seed.py) adds 6 new entries (Amadeus, Hotelbeds, TBO Tek, HRS, Riya Connect — pure B2B; Traveloka — both) and re-tags Expedia / Etraveli as `["B2C", "B2B"]` to reflect Expedia Partner Solutions and Etraveli's white-label arm.
- Frontend: [types.ts](../frontend/src/types.ts), [rivalStore.ts](../frontend/src/stores/rivalStore.ts), [RivalCategoryFilter.tsx](../frontend/src/components/RivalCategoryFilter.tsx), [RivalMarkersLayer.tsx](../frontend/src/components/RivalMarkersLayer.tsx), [RivalSummaryCard.tsx](../frontend/src/components/RivalSummaryCard.tsx), [KpiHeaderBar.tsx](../frontend/src/components/KpiHeaderBar.tsx), and [RivalRankingTable.tsx](../frontend/src/components/RivalRankingTable.tsx) all consume `categories: string[]`. Visibility is "any active category" (overlap semantics, mirroring the backend).

##### Acceptance Criteria

- [x] User can review both B2C and B2B OTAs (some categorized to **both**). Verified: `/api/rivals` returns 15 rivals; Expedia, Etraveli, Traveloka show `["B2C", "B2B"]`.
- [x] User can filter B2C and B2B OTAs. Verified: `/api/rivals?category=B2B` → 8 results (5 pure-B2B + 3 dual); `?category=B2C` → 10 results (7 pure-B2C + 3 dual).

**Verification:** `alembic upgrade head` (0001 → 0002), `python data/seeds/seed.py` (15 rivals / 30 regions / 175 snapshots), `npm run lint` clean, `npm run build` (TS strict) clean, `npm test` 37/37, live `/api/rivals?category=B2B|B2C` curl confirmed.

#### Small Tweak Phase 4b — Lift comparison cap ✅ [COMPLETED 2026-04-30]

**Situation:** the comparison view originally capped selection at 3 regions via a `COMPARISON_MAX` constant, and the panel had a fixed 520 px width — adding more regions would have crushed columns.

**Resolution:**

- [comparisonStore.ts](../frontend/src/stores/comparisonStore.ts) drops the `COMPARISON_MAX` constant and the cap guard in `addRegion`; duplicate-ISO suppression remains.
- [ComparisonPicker.tsx](../frontend/src/components/ComparisonPicker.tsx) removes the "max N reached" copy; the `<select>` now disables only once every seeded region is already picked.
- [index.css](../frontend/src/index.css) makes `.comparison-panel` `width: auto` with `min-width: 520px` and `max-width: calc(100vw - 32px)`; each region column gets `min-width: 130px`. The existing `.comparison-panel__scroll` `overflow: auto` takes over horizontal scroll once the table exceeds the panel's max-width.

##### Acceptance Criteria

- [x] User can compare more than 3 regions on the table — store no longer caps; dropdown stays enabled until every seeded region is selected.
- [x] The table extends properly as the number of compared countries increases — panel grows up to viewport, then the inner scroll wrapper scrolls horizontally; columns retain a 130 px minimum so values stay legible.

**Verification:** `npm run lint` clean, `npm run build` (TS strict) clean, `npm test` 37/37 (comparison logic is column-count-agnostic, so existing unit tests still validate the row construction).

---

### Phase 5 — Time-Period Filter + Export ✅ [COMPLETED 2026-04-30]

**Goal:** Satisfy FR-06.

| ID | Task | Output | Acceptance | Verification | Status |
|---|---|---|---|---|---|
| T-5.1 | Time range slider | [TimePeriodFilter.tsx](../frontend/src/components/TimePeriodFilter.tsx) + [timePeriodStore.ts](../frontend/src/stores/timePeriodStore.ts) | Range slider over the years returned by `/api/snapshots`; moving the handle re-fetches regions, region detail, KPI header, and comparison panel | Slider drives `selectedSnapshot`; every consumer effect re-runs against the new value | ✅ |
| T-5.2 | Ranking among Global OTAs | `global_rank` field added to each row of `rival_ranking` in [regions.py](../backend/app/routers/regions.py); shown alongside local rank in [RivalRankingTable.tsx](../frontend/src/components/RivalRankingTable.tsx) | Each region row shows local position **and** worldwide rank by booking volume; values match between region panel and DB | `curl /api/regions/US` → Expedia local #1 / global #1, Airbnb local #2 / global #6, etc. | ✅ |
| T-5.3 | Backend query param | `?snapshot_month=YYYY-MM-DD` accepted by [/api/regions](../backend/app/routers/regions.py), [/api/regions/{iso}](../backend/app/routers/regions.py), [/api/kpis/global](../backend/app/routers/kpis.py), and [/api/export](../backend/app/routers/export.py) via shared [snapshot.py](../backend/app/snapshot.py) helper | Bad date → 400 with explanatory message; missing param → falls back to latest snapshot in DB | `?snapshot_month=garbage` → `400 {"detail":"Invalid snapshot_month 'garbage'; expected YYYY-MM-DD."}` | ✅ |
| T-5.4 | New `/api/snapshots` | [routers/regions.py](../backend/app/routers/regions.py) | Returns `{ months: [...], latest }` so the frontend can populate the slider | `curl /api/snapshots` → 5 months 2022→2026 | ✅ |
| T-5.5 | Multi-year seed | [data/seeds/seed.py](../data/seeds/seed.py) | Yearly snapshots 2022→2026 with a deterministic recovery curve (`YEAR_MULTIPLIER`); rival assignments stable per region across years so ranks read as a clean trend | `python data/seeds/seed.py` → "5 distinct snapshot months"; US demand 72 → 92 across years | ✅ |
| T-5.6 | Backend `/api/export` | [routers/export.py](../backend/app/routers/export.py) | Returns `text/csv` with `Content-Disposition: attachment; filename="ota-export-<snap>.csv"`; columns: snapshot_month, iso_code, name, continent, demand_index, avg_booking_value, top_rival, top_rival_share_pct | `curl /api/export` → CSV header + 30 rows; `?snapshot_month=2022-04-01` re-renders with 2022 values | ✅ |
| T-5.7 | "Last updated" badge + Export CSV button | [KpiHeaderBar.tsx](../frontend/src/components/KpiHeaderBar.tsx) | Right-aligned column in the KPI header showing the active `snapshot_month` and a "Export CSV" link that downloads the same snapshot the dashboard is showing | Manual: badge updates with slider; button downloads `ota-export-2026-04-01.csv` | ✅ |

**Milestone:** Full filter + export flow works end-to-end. Verified via `npm run lint` clean, `npm run build` (TS strict) clean, `npm test` 37/37, multi-year `/api/kpis/global` curls, `/api/export` CSV inspection, and live `/api/regions/US` showing the new `global_rank` field.

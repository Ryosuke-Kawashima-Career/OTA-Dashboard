# Requirements of OTA Strategy System

## Functional Requirements

### FR-01: Interactive World Map

- Display a zoomable, pannable 2D world map as the primary interface (focused on regional connectivity).
- Color-code regions based on a selectable KPI (e.g., market size, competitor density, demand index).
- Show country/region boundaries with tooltips on hover.

### FR-02: Rival Company Overlay

- Plot rival OTA companies as markers on the map based on their primary operating region(s).
- Display a summary card per rival on click: company name, headquarter country, estimated market share, key products/services.
- Allow filtering rivals by category (e.g., budget, luxury, B2B, B2C).
- Display a **ranking** of rivals by market share in the selected region.
- Explain each company's business model and **strategy**, especially AI-driven features.
- Visualize **competitor win/loss trends**: which rivals are gaining share and which are losing it, period-over-period, in each region.

Example of rival companies:

- Booking.com
- Expedia
- Trip.com
- Airbnb
- Agoda
- MakeMyTrip
- ShareTrip
- Kayak
- Traveloka
- kiwi.com
- etraveli
- eDream ODIGEO
- KKday
- Goibibo
- Klook
- Cleartrip
- EaseMyTrip
- Yatra.com
- yanolja

### FR-03: Regional Characteristics Panel

On selecting a region, display a side panel with:

- Top travel destinations and routes.
- Seasonal demand trends (monthly chart).
- Average booking value and traveler demographics.
- Dominant rival players in that region with the ranking.

### FR-04: KPI Dashboard Header

- Show global summary KPIs at the top: total addressable markets covered, number of tracked rivals, hottest-growth region.
- KPIs must update dynamically when filters are applied.
- Surface the **investor-critical KPIs** at top-level visibility:
  - Our revenue growth rate vs. the regional market growth rate — a clear "won / lost vs. the market" indicator.
  - Our market share trajectory for the selected region and period.
  - Net share gained or lost against named rivals over the selected period.

### FR-04b: Self vs. Market Benchmark

- For any selected region and time window, display a chart comparing **our company's growth** against the **regional market growth rate**, making it immediately visible whether we beat or lost to the market.
- Provide a plain-language explanation of *what the gap means* (e.g., "Our APAC revenue grew 8% while the market grew 12% — we lost 4 percentage points of relative position"), so non-analyst employees can interpret the result.
- Link financial statement metrics (revenue, operating margin, take rate) for our company side-by-side with the same metrics for top rivals.

### FR-05: Comparison View

- Allow the president to select up to 3 regions and render a side-by-side comparison table of key metrics.

### FR-06: Time-Period Filter

- Provide a date-range selector (yearly granularity minimum) to analyze historical trends per region and rival.
- Filter must drive a **market share trajectory chart** showing our company and each tracked rival on a single time series, so that share gains/losses are visible at a glance.

### FR-07: Company-wide Accessibility & Data Storytelling

- The dashboard must be designed for use by employees across the company (strategy, finance, marketing, product), not only the executive team — language, tooltips, and units must be understandable to non-analyst users.
- Each major chart must include a short, auto-generated narrative (200 characters or fewer) that states *what the data means* and *what action it suggests*, so that users move from "revenue went up/down" discussions to position-based discussions.
- Provide an "Investor View" preset that surfaces only the metrics institutional investors prioritize: market growth comparison, share trajectory, and competitor win/loss trend.

### FR-08: External Data Ingestion

The dashboard must be backed by an automated ingestion layer that collects **real, up-to-date data** about the OTA market and rival companies from public web sources. No metric may be hard-coded or manually curated unless explicitly justified as a fallback.

#### FR-08.1: Market Data Acquisition

- Ingest **regional market size and growth rate** data from authoritative public sources, including but not limited to:
  - National statistics bureaus and tourism boards (e.g., UNWTO, JNTO, US Travel Association).
  - Industry research summaries published openly by firms such as Statista, Phocuswright, Skift, and similar.
  - Public central bank / IMF / World Bank datasets for currency, GDP, and inbound-tourism indicators.
- Each market data point must store: source URL, publisher, retrieval timestamp, original currency, and original units, so that figures are auditable.
- The ingestion layer must normalize data into a consistent schema (region → year → KPI → value → source) before it reaches the dashboard.

#### FR-08.2: Rival Performance Data Acquisition

- Automatically collect rival financial and operational performance from public sources:
  - **Investor Relations (IR) pages** of listed rivals (e.g., Booking Holdings, Expedia Group, Trip.com Group, Airbnb): annual reports (10-K, 20-F), quarterly earnings releases, investor presentations.
  - **Regulatory filings**: SEC EDGAR for US-listed rivals, HKEX disclosures for Trip.com, equivalent regulators for other jurisdictions.
  - Extract structured fields: revenue, gross bookings, take rate, operating margin, room nights / room nights booked, active customers, and any region-segmented revenue breakdown disclosed.
- The system must handle both PDF (financial reports) and HTML (press releases) as input formats.
- Each extracted figure must be traceable to its source document (URL or filing ID) and reporting period.

#### FR-08.3: Rival Strategy & AI-Feature Intelligence

- Continuously monitor rival public communications to surface strategy signals, especially AI-driven feature launches:
  - Official corporate blogs, product release notes, and press releases.
  - Conference keynote summaries and IR-day transcripts where publicly available.
  - Job postings on rival career sites as a leading indicator of strategic investment areas (e.g., a surge in ML engineer roles signals AI-product investment).
- Use natural language processing — including LLM-based summarization — to extract:
  - A one-paragraph strategy summary per rival, updated as new sources are detected.
  - A list of AI-features launched in the last 12 months per rival, each with a source link and launch date.
- All summaries must cite the underlying source links so users can verify claims.

#### FR-08.4: Market Share Estimation

- Where rivals do not directly disclose per-region market share, the system must **derive estimates** by combining:
  - Reported regional revenue or gross bookings (from FR-08.2).
  - Total regional market size (from FR-08.1).
- Estimates must be flagged in the UI as "estimated" with the calculation method shown on hover, distinguishing them from disclosed figures.

#### FR-08.5: Ingestion Reliability & Compliance

- The ingestion pipeline must:
  - Respect each source's `robots.txt`, Terms of Service, and any explicit rate limits — no aggressive scraping.
  - Prefer official APIs and structured data feeds (RSS, Atom, XBRL) over HTML scraping when available.
  - Detect schema or layout changes on tracked sites and emit alerts rather than silently corrupting data.
  - Retain raw payloads (HTML/PDF) for at least 24 months for re-processing and audit.
- All ingestion jobs must be idempotent and re-runnable for a given source/date combination.

#### FR-08.6: Data Provenance & Trust

- Every figure rendered in the dashboard (KPI, chart point, narrative claim) must be traceable to one or more **source** records via a "View source" action.
- The dashboard must display each source's freshness (retrieval timestamp) and the publisher's name so users can judge the trustworthiness of any number they see.

---

## Non-functional Requirements

### NFR-01: Data Freshness

- Market and competitor data must be refreshed automatically via ingestion pipelines (see FR-08), with the following minimum cadences per data class:
  - **Earnings releases / regulatory filings**: ingested within 24 hours of public posting.
  - **Press releases, blogs, and AI-feature announcements**: ingested within 48 hours of publication.
  - **Market size / growth-rate datasets**: refreshed at least monthly.
  - **Job postings (leading indicator)**: refreshed weekly.
- A "last updated" timestamp must be visible on the dashboard at the chart level (per KPI), not only at the global level.
- The dashboard must show a "stale data" warning when any visible figure exceeds twice the expected refresh interval for its class.

### NFR-02: Scalability

- The system must support tracking up to 500 rival companies and data for all 195 UN-recognized countries without degradation.

---

## Acceptance Criteria

### ToDo

- [ ] World map renders with region color-coding based on at least one KPI.
- [ ] At least 10 rival companies are plotted and clickable on the map.
- [ ] Regional characteristics panel displays demand trend chart and top rivals for any selected region.
- [ ] Time-period filter correctly updates all visualizations.
- [ ] Comparison view renders side-by-side metrics for 2–3 selected regions.
- [ ] CSV export produces a valid, formatted file for any selected region dataset.
- [ ] Page load time is verified to be under 3 seconds in a performance test.
- [ ] **Self vs. market benchmark** chart renders for any selected region, clearly indicating whether our growth beat or lost to the regional market growth rate.
- [ ] **Market share trajectory** time-series chart renders our company and at least the top 5 rivals on a shared axis for the selected period.
- [ ] **Competitor win/loss trend** view labels each tracked rival as a share-gainer or share-loser for the selected period.
- [ ] Investor View preset is selectable and exposes only the three institutional-investor KPIs (market growth comparison, share trajectory, competitor win/loss trend).
- [ ] Every major chart displays a plain-language narrative (≤200 chars) explaining what the data means and what it suggests.
- [ ] Non-analyst employee usability is validated via a walkthrough with at least one non-finance team member who can correctly interpret the Self vs. Market chart unaided.
- [ ] An automated ingestion pipeline retrieves market data (market size / growth rate) from at least 2 distinct public sources per region and persists each record with source URL, publisher, and retrieval timestamp.
- [ ] Rival financial figures (revenue, gross bookings, take rate, operating margin) are automatically extracted from the most recent earnings releases or regulatory filings for at least the top 5 listed rivals.
- [ ] An automated job ingests rival press releases and blog posts at least daily and produces an LLM-generated strategy summary per rival with source citations.
- [ ] When per-region market share is not disclosed by a rival, the dashboard displays an "estimated" badge with the calculation method shown on hover.
- [ ] Every figure on the dashboard exposes a "View source" action that opens the underlying source URL or filing.
- [ ] The ingestion pipeline respects `robots.txt` and configured rate limits; layout-change failures emit alerts instead of corrupt data.
- [ ] A "stale data" warning is rendered whenever any displayed figure exceeds twice its expected refresh cadence.

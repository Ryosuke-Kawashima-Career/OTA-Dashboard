# Necessary Figures for the OTA Industry Analysis

## Online Traveling Agencies

Our company's Service:

- skyticket <https://skyticket.com/>
- ADVENTURE <https://adventure.inc>

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
- Yeogiotte

## KPI Catalog — What We Measure and Why

The dashboard's purpose is to answer two strategic questions simultaneously per the **"Know youself, Know the enemy"** principle: *Are we winning vs. the market?* (Know Yourself) and *Which rivals are winning, and how?* (Know the Enemy). The KPIs below are organized to serve those questions directly, and every one is computable from the data model above.

### 1. Strategic Position KPIs (Know Yourself)

These KPIs answer "where do we stand?" and feed the **Self vs. Market Benchmark** and **Investor View**.

| KPI | Formula | Backing Tables | Refresh |
| --- | --- | --- | --- |
| **Market Outperformance** | `own_growth_rate − market_growth_rate` | `OWN_REGIONAL_FINANCIAL` + `MARKET_GROWTH` | Quarterly |
| Own Revenue Growth (YoY) | `(rev_t − rev_{t-4Q}) / rev_{t-4Q}` | `OWN_REGIONAL_FINANCIAL` | Quarterly |
| **Own Market Share** | `own_revenue / regional_market_size` | `OWN_REGIONAL_FINANCIAL` + `MARKET_GROWTH` | Quarterly |
| **Share Trajectory Slope** | Linear-regression slope of `share` over selected period | `MARKET_SHARE_ESTIMATE` (own rows) | Per-query |
| Share-of-Voice — AI Features | `count(own AI features in 12m) / sum(rivals + own)` | `AI_FEATURE` | Monthly |
| Own Take Rate | `own_revenue / own_gross_bookings` | `OWN_REGIONAL_FINANCIAL` | Quarterly |

### 2. Competitive Intelligence KPIs (Know the Enemy)

These feed the **Competitor Win/Loss Panel** (FR-02) and **Rival Strategy Card**.

| KPI | Formula | Backing Tables | Refresh |
| --- | --- | --- | --- |
| Rival Market Share per region | `rival_segment_revenue / regional_market_size` (or estimate, FR-08.4) | `RIVAL_FINANCIAL` + `MARKET_GROWTH` → `MARKET_SHARE_ESTIMATE` | Quarterly |
| **Rival Share Δ** | `share_t − share_{t-1}` per rival per region | `MARKET_SHARE_ESTIMATE` | Quarterly |
| **Win/Loss Label** | `Gainer` if Δ > +0.5pp, `Loser` if Δ < −0.5pp, else `Stable` | Derived from Share Δ | Quarterly |
| Rival Take Rate | `revenue / gross_bookings` | `RIVAL_FINANCIAL` | Quarterly |
| Rival Operating Margin | `operating_income / revenue` | `RIVAL_FINANCIAL` | Quarterly |
| **AI Velocity** | `count(AI_FEATURE)` where `launch_date >= now-365d` per rival | `AI_FEATURE` | Daily |
| AI Investment Index (leading) | `ml_eng_count / total_open_roles` per rival | `JOB_POSTING_SNAPSHOT` | Weekly |
| Strategy Recency | `now − max(STRATEGY_EVENT.event_date)` per rival | `STRATEGY_EVENT` | Daily |

### 3. Market Health KPIs (Macro Context)

These set the **denominator** for share calculations and color the choropleth on the world map (FR-01).

| KPI | Formula | Source |
| --- | --- | --- |
| **Total Addressable Market (TAM)** per region | Sum of OTA-relevant tourism spend in USD | UNWTO + Phocuswright + Statista |
| Market Growth Rate (YoY) | `(market_size_t − market_size_{t-1}) / market_size_{t-1}` | `MARKET_GROWTH` |
| **Market Concentration (HHI)** | `Σ(share_i²)` over all tracked players in region | Derived from `MARKET_SHARE_ESTIMATE` |
| Inbound Tourist Arrivals | Annual visitor count per region | UNWTO / JNTO |
| Average Booking Value | Median per-transaction spend | `REGION_METRICS` |
| Seasonality Index | (peak month demand) / (trough month demand) | `REGION_METRICS.demand_index` |
| Top Routes | Most-booked origin-destination pairs | `REGION_METRICS.top_routes` |

The HHI tells employees whether a region is a contested battleground (low HHI) or a near-monopoly (high HHI), which dictates strategy shape.

### 4. Operational KPIs (Apples-to-Apples Comparison)

These let users compare us against rivals on the same yardsticks.

| KPI | Definition |
| --- | --- |
| Gross Bookings | Total transaction value flowing through the platform |
| Net Revenue | Revenue actually retained after supplier payouts |
| Take Rate | `net_revenue / gross_bookings` — monetization efficiency |
| Room Nights / Trips | Volume metric for accommodation OTAs |
| Active Customers | Unique users transacting in trailing 12 months |
| Operating Margin | `operating_income / revenue` |
| Customer Acquisition Cost (where derivable) | `marketing_spend / new_customers` |

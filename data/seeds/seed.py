"""
Seed script: loads 9 rival OTAs, 30 country regions, and KPI metrics into the database.
Run from /backend: python ../data/seeds/seed.py
"""
import json
import os
import random
import sys
import uuid
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import psycopg2
from psycopg2.extras import execute_values

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ota:ota_secret@localhost:5432/ota_worldmap",
)

RIVALS = [
    {
        "id": str(uuid.uuid4()),
        "name": "Booking.com",
        "hq_country": "Netherlands",
        "categories": ["B2C"],
        "business_model": "Online hotel and accommodation marketplace; merchant and agency models.",
        "ai_strategy": "AI-powered pricing, personalised search, and generative travel assistants.",
        "website": "https://www.booking.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Expedia",
        "hq_country": "United States",
        # Expedia Group serves consumers directly *and* runs Expedia Partner
        # Solutions (EPS) — its B2B affiliate-distribution arm.
        "categories": ["B2C", "B2B"],
        "business_model": "Full-service OTA (consumer) plus Expedia Partner Solutions (B2B affiliate distribution).",
        "ai_strategy": "Conversational AI trip-planning (Romie), dynamic packaging via ML.",
        "website": "https://www.expedia.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Trip.com",
        "hq_country": "China",
        "categories": ["B2C"],
        "business_model": "Asia-first full-service OTA; expanding globally through acquisitions.",
        "ai_strategy": "TripGenie AI assistant; demand-forecasting for flash sales.",
        "website": "https://www.trip.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Airbnb",
        "hq_country": "United States",
        "categories": ["B2C"],
        "business_model": "P2P short-term rental marketplace; host + guest fee model.",
        "ai_strategy": "AI-generated listings, smart pricing for hosts, experience recommendations.",
        "website": "https://www.airbnb.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Agoda",
        "hq_country": "Singapore",
        "categories": ["B2C"],
        "business_model": "Asia-Pacific hotel specialist; part of Booking Holdings.",
        "ai_strategy": "ML-driven competitive rate parity; personalised deal engine.",
        "website": "https://www.agoda.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "MakeMyTrip",
        "hq_country": "India",
        "categories": ["B2C"],
        "business_model": "Indian full-service OTA dominating domestic flights and hotels.",
        "ai_strategy": "AI chatbot for support; predictive fare alerts.",
        "website": "https://www.makemytrip.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Kiwi.com",
        "hq_country": "Czech Republic",
        "categories": ["B2C"],
        "business_model": "Virtual interlining — combining tickets across carriers into one booking.",
        "ai_strategy": "Graph-based route optimisation; AI disruption management.",
        "website": "https://www.kiwi.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Etraveli",
        "hq_country": "Sweden",
        # Consumer-flight brand (Mytrip, GoToGate) plus a substantial
        # white-label B2B distribution business.
        "categories": ["B2C", "B2B"],
        "business_model": "Flight-first OTA with strong European presence; white-label B2B distribution.",
        "ai_strategy": "Dynamic ancillary upsell using ML models.",
        "website": "https://www.etraveli.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "eDreams ODIGEO",
        "hq_country": "Spain",
        "categories": ["B2C"],
        "business_model": "Subscription-based OTA (Prime programme); flights & hotels.",
        "ai_strategy": "AI subscription churn prevention; personalised offer engine.",
        "website": "https://www.edreams.com",
    },
    # ----- B2B-only additions (Phase 4 small tweak) -----
    {
        "id": str(uuid.uuid4()),
        "name": "Amadeus",
        "hq_country": "Spain",
        "categories": ["B2B"],
        "business_model": "Global Distribution System (GDS) and travel-tech platform for airlines, hotels, and travel agencies.",
        "ai_strategy": "Travel intelligence APIs; ML-powered shopping/pricing for distribution partners.",
        "website": "https://amadeus.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Hotelbeds",
        "hq_country": "Spain",
        "categories": ["B2B"],
        "business_model": "Bedbank — wholesale hotel inventory sold exclusively to travel-trade buyers.",
        "ai_strategy": "ML-driven dynamic pricing and demand forecasting for B2B hotel distribution.",
        "website": "https://www.hotelbeds.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "TBO Tek",
        "hq_country": "India",
        "categories": ["B2B"],
        "business_model": "Global B2B travel-distribution platform connecting travel agents with hotel, flight, and ancillary suppliers.",
        "ai_strategy": "AI-driven content normalisation and booking-funnel personalisation for retail agents.",
        "website": "https://www.tbo.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "HRS",
        "hq_country": "Germany",
        "categories": ["B2B"],
        "business_model": "Corporate-travel and managed lodging platform for enterprises (TMC partnerships, programme management).",
        "ai_strategy": "AI rate auditing and continuous-sourcing engine for corporate hotel programmes.",
        "website": "https://www.hrs.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Riya Connect",
        "hq_country": "India",
        "categories": ["B2B"],
        "business_model": "B2B travel-agent platform from Riya Travel; flights, hotels, and packages for the retail-agent channel.",
        "ai_strategy": "Agent-assist tooling and predictive cross-sell for SME agents.",
        "website": "https://www.riyaconnect.com",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Traveloka",
        "hq_country": "Indonesia",
        # Consumer super-app *and* "Traveloka for Business" corporate / agent
        # tooling — fits the "both" category requirement.
        "categories": ["B2C", "B2B"],
        "business_model": "Southeast-Asian travel super-app (consumer) with a Traveloka for Business arm for corporate accounts.",
        "ai_strategy": "Personalised recommendations and dynamic-bundle pricing across SEA markets.",
        "website": "https://www.traveloka.com",
    },
]

COUNTRIES = [
    ("US", "United States", "Americas"),
    ("GB", "United Kingdom", "Europe"),
    ("DE", "Germany", "Europe"),
    ("FR", "France", "Europe"),
    ("JP", "Japan", "Asia"),
    ("CN", "China", "Asia"),
    ("IN", "India", "Asia"),
    ("AU", "Australia", "Oceania"),
    ("BR", "Brazil", "Americas"),
    ("CA", "Canada", "Americas"),
    ("MX", "Mexico", "Americas"),
    ("ES", "Spain", "Europe"),
    ("IT", "Italy", "Europe"),
    ("NL", "Netherlands", "Europe"),
    ("SE", "Sweden", "Europe"),
    ("CZ", "Czech Republic", "Europe"),
    ("SG", "Singapore", "Asia"),
    ("TH", "Thailand", "Asia"),
    ("ID", "Indonesia", "Asia"),
    ("KR", "South Korea", "Asia"),
    ("AE", "United Arab Emirates", "Asia"),
    ("SA", "Saudi Arabia", "Asia"),
    ("ZA", "South Africa", "Africa"),
    ("NG", "Nigeria", "Africa"),
    ("EG", "Egypt", "Africa"),
    ("AR", "Argentina", "Americas"),
    ("TR", "Turkey", "Europe"),
    ("PL", "Poland", "Europe"),
    ("PT", "Portugal", "Europe"),
    ("GR", "Greece", "Europe"),
]

# Phase-3 enrichment: top routes + demographics per region (seeded for a
# curated subset — unseeded regions still render a usable panel from the
# synthesized monthly_demand + rival_ranking).
REGION_TOP_ROUTES: dict[str, list[dict]] = {
    "US": [
        {"route": "New York → Los Angeles", "share_pct": 22.3},
        {"route": "Chicago → Miami", "share_pct": 14.1},
        {"route": "Seattle → Honolulu", "share_pct": 9.6},
    ],
    "GB": [
        {"route": "London → Edinburgh", "share_pct": 18.9},
        {"route": "London → Manchester", "share_pct": 15.4},
        {"route": "London → Dublin", "share_pct": 12.2},
    ],
    "JP": [
        {"route": "Tokyo → Osaka", "share_pct": 24.7},
        {"route": "Tokyo → Sapporo", "share_pct": 13.8},
        {"route": "Tokyo → Okinawa", "share_pct": 11.2},
    ],
    "FR": [
        {"route": "Paris → Nice", "share_pct": 19.4},
        {"route": "Paris → Marseille", "share_pct": 14.6},
        {"route": "Paris → Bordeaux", "share_pct": 10.8},
    ],
    "IN": [
        {"route": "Delhi → Mumbai", "share_pct": 21.1},
        {"route": "Delhi → Bangalore", "share_pct": 16.3},
        {"route": "Mumbai → Goa", "share_pct": 12.4},
    ],
    "DE": [
        {"route": "Frankfurt → Berlin", "share_pct": 17.5},
        {"route": "Munich → Hamburg", "share_pct": 13.1},
        {"route": "Frankfurt → Cologne", "share_pct": 10.9},
    ],
    "AU": [
        {"route": "Sydney → Melbourne", "share_pct": 23.8},
        {"route": "Sydney → Brisbane", "share_pct": 14.2},
        {"route": "Melbourne → Gold Coast", "share_pct": 10.5},
    ],
    "BR": [
        {"route": "São Paulo → Rio de Janeiro", "share_pct": 20.6},
        {"route": "São Paulo → Salvador", "share_pct": 12.9},
        {"route": "Rio → Florianópolis", "share_pct": 9.3},
    ],
    "AE": [
        {"route": "Dubai → London", "share_pct": 18.2},
        {"route": "Dubai → Mumbai", "share_pct": 15.7},
        {"route": "Dubai → Bangkok", "share_pct": 11.4},
    ],
    "SG": [
        {"route": "Singapore → Bangkok", "share_pct": 19.8},
        {"route": "Singapore → Bali", "share_pct": 16.1},
        {"route": "Singapore → Tokyo", "share_pct": 12.7},
    ],
}

# Traveler demographics per region as share percentages. Segments intentionally
# sum to 100 so the Phase-3 donut-logic unit test can assert the invariant.
REGION_DEMOGRAPHICS: dict[str, list[dict]] = {
    "US": [
        {"segment": "Leisure", "share_pct": 58},
        {"segment": "Business", "share_pct": 27},
        {"segment": "VFR", "share_pct": 10},
        {"segment": "Group", "share_pct": 5},
    ],
    "GB": [
        {"segment": "Leisure", "share_pct": 54},
        {"segment": "Business", "share_pct": 29},
        {"segment": "VFR", "share_pct": 12},
        {"segment": "Group", "share_pct": 5},
    ],
    "JP": [
        {"segment": "Leisure", "share_pct": 49},
        {"segment": "Business", "share_pct": 31},
        {"segment": "VFR", "share_pct": 8},
        {"segment": "Group", "share_pct": 12},
    ],
    "FR": [
        {"segment": "Leisure", "share_pct": 62},
        {"segment": "Business", "share_pct": 24},
        {"segment": "VFR", "share_pct": 9},
        {"segment": "Group", "share_pct": 5},
    ],
    "IN": [
        {"segment": "Leisure", "share_pct": 46},
        {"segment": "Business", "share_pct": 28},
        {"segment": "VFR", "share_pct": 19},
        {"segment": "Group", "share_pct": 7},
    ],
    "DE": [
        {"segment": "Leisure", "share_pct": 52},
        {"segment": "Business", "share_pct": 33},
        {"segment": "VFR", "share_pct": 10},
        {"segment": "Group", "share_pct": 5},
    ],
    "AU": [
        {"segment": "Leisure", "share_pct": 61},
        {"segment": "Business", "share_pct": 22},
        {"segment": "VFR", "share_pct": 13},
        {"segment": "Group", "share_pct": 4},
    ],
    "BR": [
        {"segment": "Leisure", "share_pct": 64},
        {"segment": "Business", "share_pct": 20},
        {"segment": "VFR", "share_pct": 12},
        {"segment": "Group", "share_pct": 4},
    ],
    "AE": [
        {"segment": "Leisure", "share_pct": 48},
        {"segment": "Business", "share_pct": 38},
        {"segment": "VFR", "share_pct": 8},
        {"segment": "Group", "share_pct": 6},
    ],
    "SG": [
        {"segment": "Leisure", "share_pct": 51},
        {"segment": "Business", "share_pct": 37},
        {"segment": "VFR", "share_pct": 7},
        {"segment": "Group", "share_pct": 5},
    ],
}

# Map rival HQ country → ISO-alpha-2 for the home-region market-share bonus.
RIVAL_HOME_ISO: dict[str, str] = {
    "Booking.com": "NL",
    "Expedia": "US",
    "Trip.com": "CN",
    "Airbnb": "US",
    "Agoda": "SG",
    "MakeMyTrip": "IN",
    "Kiwi.com": "CZ",
    "Etraveli": "SE",
    "eDreams ODIGEO": "ES",
    "Amadeus": "ES",
    "Hotelbeds": "ES",
    "TBO Tek": "IN",
    "HRS": "DE",
    "Riya Connect": "IN",
    "Traveloka": "ID",
}

# KPI snapshots — one per April between 2022 and 2026. Yearly granularity
# matches FR-06 ("yearly granularity minimum") and gives the time-period
# filter five distinct points to walk through. The latest snapshot remains
# the canonical "current" view for endpoints that don't pass a month.
SNAPSHOT_MONTHS = [date(year, 4, 1) for year in (2022, 2023, 2024, 2025, 2026)]
LATEST_SNAPSHOT_MONTH = SNAPSHOT_MONTHS[-1]
# Recovery-curve multiplier applied to demand_index, avg_booking_value, and
# rival booking_volume per year. 2022 sits at the post-COVID rebound trough,
# 2026 is "current". Values are deliberately monotonic so YoY differences
# are obvious in the slider; in production this would come from real data.
YEAR_MULTIPLIER: dict[int, float] = {
    2022: 0.78,
    2023: 0.86,
    2024: 0.92,
    2025: 0.97,
    2026: 1.00,
}
REGION_METRICS = [
    ("US", 92, 412.50),
    ("GB", 78, 298.10),
    ("DE", 71, 275.40),
    ("FR", 83, 320.75),
    ("JP", 81, 355.90),
    ("CN", 86, 240.60),
    ("IN", 74, 165.20),
    ("AU", 68, 390.00),
    ("BR", 62, 185.30),
    ("CA", 70, 342.80),
    ("MX", 65, 210.45),
    ("ES", 79, 268.90),
    ("IT", 77, 289.50),
    ("NL", 72, 305.60),
    ("SE", 64, 330.25),
    ("CZ", 58, 198.70),
    ("SG", 75, 405.10),
    ("TH", 82, 172.30),
    ("ID", 69, 148.90),
    ("KR", 73, 285.70),
    ("AE", 80, 450.20),
    ("SA", 55, 295.80),
    ("ZA", 52, 215.40),
    ("NG", 48, 158.90),
    ("EG", 60, 188.20),
    ("AR", 57, 175.60),
    ("TR", 66, 205.30),
    ("PL", 61, 190.80),
    ("PT", 72, 245.50),
    ("GR", 76, 260.40),
]


def seed():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Regions
    execute_values(
        cur,
        "INSERT INTO regions (iso_code, name, continent) VALUES %s ON CONFLICT DO NOTHING",
        COUNTRIES,
    )

    # Rivals — idempotent on (name): refresh categories + metadata if the row
    # already exists (e.g. running this seed after migration 0002 against a
    # database that already had the original 9 single-category rivals).
    execute_values(
        cur,
        """
        INSERT INTO rivals (id, name, hq_country, categories, business_model, ai_strategy, website)
        VALUES %s
        ON CONFLICT (name) DO UPDATE SET
            hq_country = EXCLUDED.hq_country,
            categories = EXCLUDED.categories,
            business_model = EXCLUDED.business_model,
            ai_strategy = EXCLUDED.ai_strategy,
            website = EXCLUDED.website
        """,
        [
            (
                r["id"], r["name"], r["hq_country"], r["categories"],
                r["business_model"], r["ai_strategy"], r["website"],
            )
            for r in RIVALS
        ],
    )

    cur.execute("SELECT id, name FROM rivals;")
    rival_by_name = {name: rid for rid, name in cur.fetchall()}

    # Region metrics + rival snapshots are seeded for every (year, region) pair.
    # Idempotent within a snapshot month: we DELETE-then-INSERT, so re-running
    # the seed always converges on the canonical curve.
    for snap in SNAPSHOT_MONTHS:
        mult = YEAR_MULTIPLIER[snap.year]

        cur.execute(
            "DELETE FROM region_metrics WHERE snapshot_month = %s",
            (snap,),
        )
        execute_values(
            cur,
            """
            INSERT INTO region_metrics
                (id, region_iso, snapshot_month, avg_booking_value, demand_index, top_routes, demographics)
            VALUES %s
            """,
            [
                (
                    str(uuid.uuid4()),
                    iso,
                    snap,
                    round(avg_booking_value * mult, 2),
                    int(round(demand_index * mult)),
                    json.dumps(REGION_TOP_ROUTES.get(iso, [])),
                    json.dumps(REGION_DEMOGRAPHICS.get(iso, [])),
                )
                for iso, demand_index, avg_booking_value in REGION_METRICS
            ],
        )

        # Rival region snapshots (idempotent per snapshot month). Each year
        # uses the same PRNG seed so a region keeps its same active rivals
        # and rank order over time — only volumes scale with `mult`. This
        # produces a believable historical trend per rival while leaving
        # the home-country dominance (Expedia/US, MakeMyTrip/IN, etc.) intact.
        cur.execute(
            "DELETE FROM rival_region_snapshots WHERE snapshot_month = %s",
            (snap,),
        )
        rng = random.Random(42)
        snapshot_rows: list[tuple] = []
        for iso, _, _ in REGION_METRICS:
            # Each region picks 5–7 rivals to "operate" in it
            active_rivals = rng.sample(list(RIVAL_HOME_ISO.keys()), k=rng.randint(5, 7))
            raw_scores = []
            for name in active_rivals:
                base = rng.uniform(3, 10)
                if RIVAL_HOME_ISO[name] == iso:
                    base *= 4.0  # strong home-country bias
                raw_scores.append(base)
            total = sum(raw_scores)
            # Normalize to sum to 80% of market; remaining 20% is unmodeled competition.
            for name, score in zip(active_rivals, raw_scores):
                share = round(score / total * 80.0, 2)
                booking_volume = int(share * 15_000 * mult)
                snapshot_rows.append(
                    (
                        str(uuid.uuid4()),
                        rival_by_name[name],
                        iso,
                        share,
                        booking_volume,
                        snap,
                    )
                )

        execute_values(
            cur,
            """
            INSERT INTO rival_region_snapshots
                (id, rival_id, region_iso, market_share_pct, booking_volume, snapshot_month)
            VALUES %s
            """,
            snapshot_rows,
        )

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM rivals;")
    rival_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM regions;")
    region_count = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM region_metrics WHERE snapshot_month = %s",
        (LATEST_SNAPSHOT_MONTH,),
    )
    metrics_count = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM rival_region_snapshots WHERE snapshot_month = %s",
        (LATEST_SNAPSHOT_MONTH,),
    )
    snapshot_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT snapshot_month) FROM region_metrics;")
    distinct_months = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(
        f"Seeded {rival_count} rivals, {region_count} regions, "
        f"{metrics_count} region_metrics @ {LATEST_SNAPSHOT_MONTH}, "
        f"{snapshot_count} rival_region_snapshots @ {LATEST_SNAPSHOT_MONTH}, "
        f"{distinct_months} distinct snapshot months."
    )
    assert rival_count == 15, f"Expected 15 rivals, got {rival_count}"
    assert region_count == 30, f"Expected 30 regions, got {region_count}"
    assert metrics_count == 30, f"Expected 30 region_metrics for latest month, got {metrics_count}"
    assert snapshot_count >= 150, f"Expected ≥150 rival_region_snapshots for latest, got {snapshot_count}"
    assert distinct_months == len(SNAPSHOT_MONTHS), (
        f"Expected {len(SNAPSHOT_MONTHS)} distinct snapshot months, got {distinct_months}"
    )
    print("PASS: seed counts verified.")


if __name__ == "__main__":
    seed()

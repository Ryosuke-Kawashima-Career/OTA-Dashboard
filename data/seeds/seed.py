"""
Seed script — loads the **real-world OTA dataset** from `data/*.csv` into the
warehouse. As of Phase 7b this replaces the prior synthetic mock data; every
row written to the database carries provenance via `data/sources.csv`.

Run from /backend:  python ../data/seeds/seed.py

Datasets loaded (counts per `data/README.md`):

  data/rivals/rivals.csv               → rivals               (21)
  data/rivals/rival_financials.csv     → rival_financial      (50)
  data/market/market_growth.csv        → market_growth        (139)
  data/regions/region_metrics.csv      → region_metrics       (60)
  data/regions/inbound_tourism.csv     → inbound_tourism      (90)
  data/strategy/ai_features.csv        → ai_feature           (58)
  data/strategy/strategy_events.csv    → strategy_event       (93)
  data/sources.csv                     → sources              (288)

Idempotency: every insert uses an ON-CONFLICT-aware upsert keyed on the
row's natural key, so re-running the script converges on the same state
without duplicates. Re-running after the curated CSVs change refreshes
the warehouse to the new values.

Conventions applied during load (cf. specs/implementation_plan.md § 7b):

  • fiscal_year (int)              → period_end = date(year, 12, 31)
                                     period_type = 'annual'
  • year (int) in region_metrics   → snapshot_month = date(year, 1, 1)
  • *_usd_millions                 → absolute USD via × 1e6
  • *_thousands / *_millions       → absolute via × 1e3 / × 1e6
  • source_url                     → resolved against the sources table
                                     (publisher = urlparse(url).netloc,
                                      source_type='curated', content_hash=sha256(url))

`rival_region_snapshots` is still populated as an **interim** synthetic
table so the Phase 1–5 endpoints (which query `rival_region_snapshots`
for the per-region rival ranking) keep working until Phase 8's
`market_share_estimate` derivation lands and the endpoints are migrated.
The synthetic rows now use the **real** rival IDs from `rivals.csv`,
real HQ ISO codes, and the same yearly snapshots as before
(2022→2026 on April 1st).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import psycopg2
from psycopg2.extras import Json, execute_values

DATA_ROOT = Path(__file__).resolve().parent.parent  # repo/data
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ota:ota_secret@localhost:5432/ota_worldmap",
)


# ─────────────────────────────────────────────────────────────────────────
# Reference data: 30 country regions
# ─────────────────────────────────────────────────────────────────────────
# Kept as a hard-coded list because it's geography metadata, not facts —
# every curated CSV references one of these ISO codes.

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


# ─────────────────────────────────────────────────────────────────────────
# CSV parsing helpers
# ─────────────────────────────────────────────────────────────────────────


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _opt_int(s: str | None) -> int | None:
    if s is None or s == "":
        return None
    return int(float(s))  # tolerates "1234.0"


def _opt_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    return float(s)


def _opt_text(s: str | None) -> str | None:
    if s is None or s == "":
        return None
    return s


def _bool(s: str | None) -> bool:
    return (s or "").strip().lower() in {"true", "1", "t", "yes"}


def _opt_json(s: str | None) -> Any:
    if s is None or s == "":
        return None
    return json.loads(s)


# ─────────────────────────────────────────────────────────────────────────
# Sources registry
# ─────────────────────────────────────────────────────────────────────────


def _content_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _publisher(url: str) -> str:
    return urlparse(url).netloc or "unknown"


def upsert_source(
    cur,
    url: str,
    *,
    source_type: str = "curated",
    cache: dict[str, str],
) -> str | None:
    """Insert-or-fetch a `sources` row keyed on (url, content_hash).

    Memoised per run so each unique URL incurs one DB round trip max.
    """
    if not url:
        return None
    if url in cache:
        return cache[url]
    ch = _content_hash(url)
    cur.execute(
        """
        INSERT INTO sources (url, publisher, source_type, retrieved_at, content_hash)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT uq_sources_url_content_hash DO UPDATE
            SET retrieved_at = EXCLUDED.retrieved_at
        RETURNING id
        """,
        (url, _publisher(url), source_type, datetime.now(timezone.utc), ch),
    )
    sid = cur.fetchone()[0]
    cache[url] = sid
    return sid


# ─────────────────────────────────────────────────────────────────────────
# Loaders — one per dataset
# ─────────────────────────────────────────────────────────────────────────


def load_regions(cur) -> int:
    execute_values(
        cur,
        "INSERT INTO regions (iso_code, name, continent) VALUES %s ON CONFLICT DO NOTHING",
        COUNTRIES,
    )
    cur.execute("SELECT COUNT(*) FROM regions")
    return cur.fetchone()[0]


def load_rivals(cur) -> int:
    rows = _read_csv(DATA_ROOT / "rivals" / "rivals.csv")
    # On switchover from the legacy synthetic seed: old rivals had random
    # UUIDs that don't match the CSV's UUID5-of-name IDs. Wiping first
    # avoids "two Booking.com rows with different UUIDs" — but only after
    # we've cleared the FK-referencing tables further down. So instead we
    # ON-CONFLICT on `name` (the existing unique constraint) and force-
    # overwrite the id when re-seeding into a previously-mocked DB.
    payload = [
        (
            r["id"],
            r["name"],
            r.get("parent") or None,
            r.get("ticker") or None,
            r.get("exchange") or None,
            r["hq_country"],
            r.get("hq_iso") or None,
            json.loads(r["categories"]),
            r["business_model"],
            r["ai_strategy"],
            r["website"],
        )
        for r in rows
    ]
    execute_values(
        cur,
        """
        INSERT INTO rivals (id, name, parent, ticker, exchange, hq_country, hq_iso,
                            categories, business_model, ai_strategy, website)
        VALUES %s
        ON CONFLICT (name) DO UPDATE SET
            id = EXCLUDED.id,
            parent = EXCLUDED.parent,
            ticker = EXCLUDED.ticker,
            exchange = EXCLUDED.exchange,
            hq_country = EXCLUDED.hq_country,
            hq_iso = EXCLUDED.hq_iso,
            categories = EXCLUDED.categories,
            business_model = EXCLUDED.business_model,
            ai_strategy = EXCLUDED.ai_strategy,
            website = EXCLUDED.website
        """,
        payload,
    )
    return len(rows)


def load_rival_financials(cur, source_cache: dict[str, str]) -> int:
    rows = _read_csv(DATA_ROOT / "rivals" / "rival_financials.csv")
    cur.execute("DELETE FROM rival_financial")
    payload = []
    for r in rows:
        sid = upsert_source(cur, r["source_url"], cache=source_cache)
        rev_m = _opt_float(r["revenue_usd_millions"])
        gb_m = _opt_float(r["gross_bookings_usd_millions"])
        ac_m = _opt_float(r["active_customers_millions"])
        rn_m = _opt_float(r["room_nights_millions"])
        payload.append(
            (
                r["id"],
                r["rival_id"],
                date(int(r["fiscal_year"]), 12, 31),
                "annual",
                rev_m * 1e6 if rev_m is not None else None,
                gb_m * 1e6 if gb_m is not None else None,
                _opt_float(r["take_rate_pct"]),
                _opt_float(r["operating_margin_pct"]),
                int(rn_m * 1e6) if rn_m is not None else None,
                int(ac_m * 1e6) if ac_m is not None else None,
                Json(_opt_json(r["segment_breakdown"])) if _opt_json(r["segment_breakdown"]) is not None else None,
                _bool(r["is_estimated"]),
                _opt_text(r.get("notes")),
                sid,
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO rival_financial
            (id, rival_id, period_end, period_type, revenue_usd, gross_bookings_usd,
             take_rate_pct, operating_margin_pct, room_nights, active_customers,
             segment_breakdown, is_estimated, notes, source_id)
        VALUES %s
        """,
        payload,
    )
    return len(rows)


def load_market_growth(cur, source_cache: dict[str, str]) -> int:
    rows = _read_csv(DATA_ROOT / "market" / "market_growth.csv")
    cur.execute("DELETE FROM market_growth")
    payload = []
    for r in rows:
        sid = upsert_source(cur, r["source_url"], cache=source_cache)
        size_m = _opt_float(r["market_size_usd_millions"])
        payload.append(
            (
                r["id"],
                r["region_iso"],
                int(r["year"]),
                size_m * 1e6 if size_m is not None else 0.0,
                _opt_float(r["growth_rate_pct"]),
                sid,
                _bool(r["is_estimated"]),
                _opt_text(r.get("notes")),
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO market_growth
            (id, region_iso, year, market_size_usd, growth_rate_pct,
             source_id, is_estimated, notes)
        VALUES %s
        """,
        payload,
    )
    return len(rows)


def load_region_metrics(cur, source_cache: dict[str, str]) -> int:
    rows = _read_csv(DATA_ROOT / "regions" / "region_metrics.csv")
    cur.execute("DELETE FROM region_metrics")
    payload = []
    for r in rows:
        sid = upsert_source(cur, r["source_url"], cache=source_cache)
        year = int(r["year"])
        payload.append(
            (
                r["id"],
                r["region_iso"],
                date(year, 1, 1),  # snapshot_month (legacy column)
                _opt_float(r["avg_booking_value_usd"]),
                _opt_int(r["demand_index"]),
                None,  # top_routes — not in curated data
                None,  # demographics — not in curated data
                year,
                _opt_float(r["seasonality_index"]),
                _bool(r["is_estimated"]),
                _opt_text(r.get("notes")),
                sid,
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO region_metrics
            (id, region_iso, snapshot_month, avg_booking_value, demand_index,
             top_routes, demographics, year, seasonality_index, is_estimated, notes, source_id)
        VALUES %s
        """,
        payload,
    )
    return len(rows)


def load_inbound_tourism(cur, source_cache: dict[str, str]) -> int:
    rows = _read_csv(DATA_ROOT / "regions" / "inbound_tourism.csv")
    cur.execute("DELETE FROM inbound_tourism")
    payload = []
    for r in rows:
        sid = upsert_source(cur, r["source_url"], cache=source_cache)
        payload.append(
            (
                r["id"],
                r["region_iso"],
                int(r["year"]),
                _opt_int(r["international_arrivals_thousands"]),
                _opt_float(r["tourism_receipts_usd_millions"]),
                _bool(r["is_estimated"]),
                _opt_text(r.get("notes")),
                sid,
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO inbound_tourism
            (id, region_iso, year, international_arrivals_thousands,
             tourism_receipts_usd_millions, is_estimated, notes, source_id)
        VALUES %s
        """,
        payload,
    )
    return len(rows)


def load_ai_features(cur, source_cache: dict[str, str]) -> int:
    rows = _read_csv(DATA_ROOT / "strategy" / "ai_features.csv")
    cur.execute("DELETE FROM ai_feature")
    payload = []
    for r in rows:
        sid = upsert_source(cur, r["source_url"], cache=source_cache)
        payload.append(
            (
                r["id"],
                r["rival_id"],
                date.fromisoformat(r["launch_date"]),
                r["feature_name"],
                _opt_text(r["description"]),
                r["category"],
                False,   # is_estimated — curated AI features are all factual launches
                None,    # notes
                sid,
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO ai_feature
            (id, rival_id, launch_date, feature_name, description,
             category, is_estimated, notes, source_id)
        VALUES %s
        """,
        payload,
    )
    return len(rows)


def load_strategy_events(cur, source_cache: dict[str, str]) -> int:
    rows = _read_csv(DATA_ROOT / "strategy" / "strategy_events.csv")
    cur.execute("DELETE FROM strategy_event")
    payload = []
    for r in rows:
        sid = upsert_source(cur, r["source_url"], cache=source_cache)
        payload.append(
            (
                r["id"],
                r["rival_id"],
                date.fromisoformat(r["event_date"]),
                r["category"],
                _opt_text(r["title"]),
                r["description"],  # summary column (longer form)
                sid,
            )
        )
    execute_values(
        cur,
        """
        INSERT INTO strategy_event
            (id, rival_id, event_date, category, title, summary, source_id)
        VALUES %s
        """,
        payload,
    )
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────
# Interim: rival_region_snapshots for Phase 1–5 endpoint compatibility
# ─────────────────────────────────────────────────────────────────────────
# The dashboard's existing /api/regions/{iso} endpoint reads from this
# table to produce the per-region rival ranking. The market-share values
# below remain SYNTHETIC pending the Phase 8 market_share_estimate
# derivation, but the rival_ids and home-country biases are drawn from
# the real rivals.csv data — so at least the cast is real, not the
# stock-photo set the prior mock used.

SNAPSHOT_MONTHS = [date(year, 4, 1) for year in (2022, 2023, 2024, 2025, 2026)]
LATEST_SNAPSHOT_MONTH = SNAPSHOT_MONTHS[-1]
YEAR_MULTIPLIER: dict[int, float] = {
    2022: 0.78, 2023: 0.86, 2024: 0.92, 2025: 0.97, 2026: 1.00,
}


def populate_rival_region_snapshots(cur) -> int:
    """Synthesise rival_region_snapshots using REAL rival IDs + HQ ISOs.

    The endpoint contract (Phase 1–5) still expects this table; once
    Phase 8 builds `market_share_estimate` from rival_financial × region
    weights, the endpoints will switch and this function can be deleted.
    """
    cur.execute("SELECT id, name, hq_iso FROM rivals WHERE hq_iso IS NOT NULL")
    rivals = cur.fetchall()
    if not rivals:
        return 0

    region_isos = [iso for iso, _, _ in COUNTRIES]

    cur.execute("DELETE FROM rival_region_snapshots")
    rows: list[tuple] = []
    for snap in SNAPSHOT_MONTHS:
        mult = YEAR_MULTIPLIER[snap.year]
        rng = random.Random(42)
        for iso in region_isos:
            active = rng.sample(rivals, k=rng.randint(5, 7))
            raw_scores: list[float] = []
            for _, _, rival_hq in active:
                base = rng.uniform(3, 10)
                if rival_hq == iso:
                    base *= 4.0  # home-country bias
                raw_scores.append(base)
            total = sum(raw_scores)
            for (rival_id, _name, _hq), score in zip(active, raw_scores):
                share = round(score / total * 80.0, 2)
                booking_volume = int(share * 15_000 * mult)
                rows.append(
                    (
                        str(uuid.uuid4()),
                        rival_id,
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
        rows,
    )
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────


def seed() -> None:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()
    source_cache: dict[str, str] = {}

    # Sanity: refuse to run against a schema older than migration 0008,
    # which is what introduces the columns the curated data needs.
    cur.execute("SELECT to_regclass('public.inbound_tourism') IS NOT NULL")
    (ready,) = cur.fetchone()
    if not ready:
        raise SystemExit(
            "Schema not at Phase 7b. Run `alembic upgrade head` before seeding."
        )

    # Clear FK-dependent tables BEFORE updating rivals. The previous
    # synthetic seed inserted random UUIDs for each Booking.com /
    # Expedia / etc.; the curated CSVs use stable UUID5 IDs. Without
    # this delete, ON CONFLICT (name) DO UPDATE id=... would violate
    # the FK from rival_region_snapshots.rival_id (and the same goes
    # for rival_financial, ai_feature, strategy_event — but those are
    # wiped inside their loaders).
    cur.execute("DELETE FROM rival_region_snapshots")
    cur.execute("DELETE FROM rival_financial")
    cur.execute("DELETE FROM ai_feature")
    cur.execute("DELETE FROM strategy_event")
    # Sources are NOT deleted here — the upsert_source() helper handles
    # ON CONFLICT, so the same source_url ends up at the same source_id
    # across reruns. Leaving them in place also means the validator
    # still passes mid-load (no orphan fact rows can exist because we
    # only deleted facts above).

    region_count = load_regions(cur)
    rival_count = load_rivals(cur)
    fin_count = load_rival_financials(cur, source_cache)
    mkt_count = load_market_growth(cur, source_cache)
    metric_count = load_region_metrics(cur, source_cache)
    tourism_count = load_inbound_tourism(cur, source_cache)
    ai_count = load_ai_features(cur, source_cache)
    strat_count = load_strategy_events(cur, source_cache)
    snap_count = populate_rival_region_snapshots(cur)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM sources")
    (source_count,) = cur.fetchone()
    cur.close()
    conn.close()

    print(
        "Loaded real-world OTA data:\n"
        f"  · {region_count:>4} regions\n"
        f"  · {rival_count:>4} rivals          (data/rivals/rivals.csv)\n"
        f"  · {fin_count:>4} rival_financial  (data/rivals/rival_financials.csv)\n"
        f"  · {mkt_count:>4} market_growth    (data/market/market_growth.csv)\n"
        f"  · {metric_count:>4} region_metrics   (data/regions/region_metrics.csv)\n"
        f"  · {tourism_count:>4} inbound_tourism  (data/regions/inbound_tourism.csv)\n"
        f"  · {ai_count:>4} ai_feature       (data/strategy/ai_features.csv)\n"
        f"  · {strat_count:>4} strategy_event   (data/strategy/strategy_events.csv)\n"
        f"  · {source_count:>4} sources (provenance registry)\n"
        f"  · {snap_count:>4} rival_region_snapshots (interim, Phase 1–5 compat)"
    )

    # Acceptance assertions — exact counts come from data/README.md.
    assert region_count == 30, region_count
    assert rival_count == 21, rival_count
    assert fin_count == 50, fin_count
    assert mkt_count == 139, mkt_count
    assert metric_count == 60, metric_count
    assert tourism_count == 90, tourism_count
    assert ai_count == 58, ai_count
    assert strat_count == 93, strat_count
    assert source_count >= 280, source_count  # ~288 unique URLs after dedup
    assert snap_count >= 150, snap_count
    print("PASS: curated-data seed counts verified.")


if __name__ == "__main__":
    seed()

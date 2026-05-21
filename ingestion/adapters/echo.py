"""Synthetic "echo" adapter (T-7.5).

The echo adapter exists solely to exercise the ingestion pipeline
end-to-end before any real-world source is wired in. It returns a fixed
fixture so:

* Every run produces identical bytes → identical raw-payload key →
  identical content hash → identical source row → identical fact rows.
  That's the cleanest possible idempotency test.

* The DOM-skeleton fingerprint of the fixture is stable, so the
  layout-change detector treats every re-run as "no drift".

The synthetic fact row is written to `market_growth(region_iso='US',
year=1900, source_type='echo')`. Year 1900 keeps the row visually
distinct from real data (which begins 2022) so future debugging knows
at a glance that the row is synthetic — and the FK to `regions(US)`
keeps referential integrity intact.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

ECHO_SOURCE_URL = "internal://echo/fixture-v1"
ECHO_PUBLISHER = "echo-adapter"
ECHO_SOURCE_TYPE = "echo"
ECHO_CONTENT_HASH_TAG = "echo-fixture-v1"

# A small but realistic HTML document — has enough DOM structure for the
# skeleton hash to be meaningful, but small enough to inspect by hand.
ECHO_FIXTURE_PAYLOAD: bytes = (
    b"<!doctype html>"
    b"<html><head><title>Echo Earnings</title></head>"
    b"<body>"
    b"<header><h1>Echo Inc.</h1></header>"
    b"<main>"
    b"<section data-period='1900'>"
    b"<table><thead><tr><th>Region</th><th>Market Size USD</th><th>Growth %</th></tr></thead>"
    b"<tbody><tr><td>US</td><td>12345</td><td>0.5</td></tr></tbody></table>"
    b"</section>"
    b"</main>"
    b"<footer>Synthetic fixture for pipeline tests.</footer>"
    b"</body></html>"
)


@dataclass(frozen=True)
class EchoFactRow:
    """Shape of a synthetic MarketGrowth row, sans source_id (set by the flow)."""

    region_iso: str
    year: int
    market_size_usd: float
    growth_rate_pct: float


@dataclass(frozen=True)
class EchoExtraction:
    payload: bytes
    retrieved_at: datetime
    fact_rows: tuple[EchoFactRow, ...]


def fetch() -> bytes:
    """Pretend to hit `ECHO_SOURCE_URL`. Returns the deterministic fixture."""
    return ECHO_FIXTURE_PAYLOAD


def extract() -> EchoExtraction:
    """Parse the fixture into structured rows.

    For a synthetic adapter the "parse" step is trivial — we just return
    the row encoded in the fixture's table. A real adapter would do
    XBRL/HTML parsing here.
    """
    return EchoExtraction(
        payload=ECHO_FIXTURE_PAYLOAD,
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=(
            EchoFactRow(
                region_iso="US",
                year=1900,
                market_size_usd=12345.0,
                growth_rate_pct=0.5,
            ),
        ),
    )

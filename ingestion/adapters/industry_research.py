"""Industry-research adapter (T-8.3).

Covers the open-content slice of FR-08.1 — the published market-size and
growth-rate figures from research firms (Statista, Phocuswright, Mordor
Intelligence, IMARC, Market Research Future, Ken Research, Euromonitor,
Deep Market Insights, WebInTravel, Skift). These publishers do not offer
APIs, so the production behaviour is straight HTML scraping; for Phase 8
the fixture mode reads ``data/market/market_growth.csv``, which already
carries the source URLs the live HTTP scraper will hit.

The adapter groups rows by ``urlparse(source_url).netloc`` — the same
publisher identity the seed loader uses — so each publisher ends up
with its own ``sources`` row and its own ``market_growth`` rows in the
warehouse. That matches the FR-08.1 acceptance criterion ("≥2 distinct
public sources per region") because the curated CSV intentionally
double-sources most regions.

Adapter entry points:

* ``iter_publishers()`` — yields ``(publisher, source_type, rows)``
  triples so the orchestrating flow can call ``run_adapter()`` once per
  publisher. This keeps each ``sources`` row scoped to a single
  publisher (mixing them would defeat provenance).

* ``build_fetch_result(publisher, source_type, rows)`` — encodes one
  publisher's slice as deterministic JSON bytes; ``extract()`` reads
  that JSON back into ``MarketGrowth`` ``FactRow``s.

* ``fetch_via_http(http_client, url)`` — production path; persists the
  live page bytes for re-extraction once the per-publisher HTML parser
  is wired up.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Optional
from urllib.parse import urlparse

from app.models import MarketGrowth
from ingestion.adapters._base import (
    AdapterExtraction,
    FactRow,
    FetchResult,
    build_csv_fixture_payload,
)

log = logging.getLogger(__name__)


_DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "market" / "market_growth.csv"
)


# ──────────────────────────────────────────────────────────────────────
# Publisher classification
# ──────────────────────────────────────────────────────────────────────


def publisher_for(url: str) -> str:
    """Return a stable human-readable publisher name for ``url``.

    The fallback is the bare hostname (matches what the curated seed
    loader records), so unknown domains stay traceable.
    """
    host = urlparse(url).netloc.lower()
    mapping = {
        "www.statista.com": "Statista",
        "www.phocuswright.com": "Phocuswright",
        "skift.com": "Skift",
        "www.mordorintelligence.com": "Mordor Intelligence",
        "www.imarcgroup.com": "IMARC Group",
        "www.marketresearchfuture.com": "Market Research Future",
        "www.kenresearch.com": "Ken Research",
        "www.euromonitor.com": "Euromonitor International",
        "deepmarketinsights.com": "Deep Market Insights",
        "www.webintravel.com": "WebInTravel",
        "www.marketdataforecast.com": "Market Data Forecast",
        "www.ibisworld.com": "IBISWorld",
        "tradingeconomics.com": "Trading Economics",
        "vocal.media": "Vocal Media",
        "www.hospitality.today": "Hospitality.today",
        "www.drv.de": "Deutscher Reiseverband",
        "www.futuremarketinsights.com": "Future Market Insights",
    }
    return mapping.get(host, host or "unknown")


_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def source_type_for(publisher: str) -> str:
    """Reduce a publisher name to a ``snake_case`` source_type tag."""
    return _NON_ALPHANUM.sub("_", publisher.lower()).strip("_") or "industry_research"


# ──────────────────────────────────────────────────────────────────────
# Fixture mode
# ──────────────────────────────────────────────────────────────────────


def _read_market_growth_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append(
                {
                    "region_iso": raw["region_iso"],
                    "year": int(raw["year"]),
                    "market_size_usd_millions": float(raw["market_size_usd_millions"]),
                    "growth_rate_pct": (
                        float(raw["growth_rate_pct"])
                        if raw["growth_rate_pct"]
                        else None
                    ),
                    "is_estimated": raw["is_estimated"].strip().lower() == "true",
                    "notes": raw["notes"] or None,
                    "source_url": raw["source_url"],
                }
            )
    return rows


def iter_publishers(
    fixture_path: Optional[Path] = None,
) -> Iterator[tuple[str, str, str, list[dict]]]:
    """Yield ``(publisher, source_type, url, rows)`` per upstream publisher.

    ``url`` is the most-frequently-referenced URL within the publisher's
    rows. That URL is what the live HTTP scraper would fetch first; in
    fixture mode it shows up as ``sources.url`` so the View Source modal
    can deep-link straight to the publisher.
    """
    fixture = fixture_path or _DEFAULT_FIXTURE_PATH
    rows = _read_market_growth_csv(fixture)
    by_publisher: dict[str, list[dict]] = {}
    for r in rows:
        pub = publisher_for(r["source_url"])
        by_publisher.setdefault(pub, []).append(r)
    for publisher, group in by_publisher.items():
        st = source_type_for(publisher)
        url_counts: dict[str, int] = {}
        for r in group:
            url_counts[r["source_url"]] = url_counts.get(r["source_url"], 0) + 1
        canonical_url = max(url_counts.items(), key=lambda kv: kv[1])[0]
        yield publisher, st, canonical_url, group


def build_fetch_result(
    *,
    publisher: str,
    canonical_url: str,
    rows: Iterable[Mapping],
    fixture_path: Optional[Path] = None,
) -> FetchResult:
    """Deterministic per-publisher payload — used by ``run_adapter``."""
    fixture = fixture_path or _DEFAULT_FIXTURE_PATH
    payload = build_csv_fixture_payload(
        publisher=publisher,
        fixture_path=str(fixture.relative_to(fixture.parents[2])),
        rows=list(rows),
    )
    return FetchResult(
        url=canonical_url,
        payload=payload,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# ──────────────────────────────────────────────────────────────────────
# HTTP mode (production)
# ──────────────────────────────────────────────────────────────────────


def fetch_via_http(http_client, url: str) -> FetchResult:
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


def extract(payload: bytes) -> AdapterExtraction:
    """Parse fixture-mode JSON into ``MarketGrowth`` rows.

    HTML parsing is stubbed (returns an empty extraction) so the live
    HTTP path can still persist raw payload + provenance until the
    per-publisher HTML adapter lands.
    """
    text = payload.decode("utf-8", errors="replace")
    if not text.lstrip().startswith("{"):
        return AdapterExtraction(
            payload=payload,
            retrieved_at=datetime.now(timezone.utc),
            fact_rows=(),
        )
    doc = json.loads(text)
    fact_rows: list[FactRow] = []
    for r in doc.get("rows", []):
        market_size_usd_m = r.get("market_size_usd_millions")
        if market_size_usd_m is None:
            continue
        fact_rows.append(
            FactRow(
                target=MarketGrowth,
                natural_key=("region_iso", "year", "source_id"),
                payload={
                    "region_iso": r["region_iso"],
                    "year": r["year"],
                    "market_size_usd": float(market_size_usd_m) * 1_000_000.0,
                    "growth_rate_pct": r.get("growth_rate_pct"),
                    "is_estimated": bool(r.get("is_estimated", False)),
                    "notes": r.get("notes"),
                },
            )
        )
    return AdapterExtraction(
        payload=payload,
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=tuple(fact_rows),
    )


__all__ = [
    "build_fetch_result",
    "extract",
    "fetch_via_http",
    "iter_publishers",
    "publisher_for",
    "source_type_for",
]

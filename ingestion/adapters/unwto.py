"""UNWTO adapter (T-8.1).

The UN World Tourism Organization publishes ``International Tourism
Highlights`` annually as PDFs and an XLSX dataset behind the public
``unwto.org/tourism-data`` portal. For the warehouse we need the
per-region figures we already store in ``inbound_tourism``:

* ``international_arrivals_thousands`` — inbound arrivals
* ``tourism_receipts_usd_millions`` — total inbound spend

Because UNWTO does not yet expose a stable JSON API for these
figures, the adapter supports two modes:

* **HTTP mode** (``fetch_via_http``) hits a configurable per-region
  URL (default: the public country-profile page on ``unwto.org``)
  and persists the bytes through the standard pipeline. The parser
  is deliberately stubbed pending a layout audit — when production
  adopts this adapter the parsing step is the only thing that
  changes; the orchestration around it is already proven.

* **Fixture mode** (``fetch_from_curated``) reads
  ``data/regions/inbound_tourism.csv`` and emits one row per
  ``(region_iso, year)``. This is the regression-baseline path the
  test suite uses, and it is also what the ``monthly_market`` flow
  exercises until the live HTTP parser lands.

In both modes the adapter ultimately writes the same warehouse rows
through the same ``run_adapter()`` helper, so the contract Phase 8
must guarantee — every row carries a ``source_id``, every re-run is
idempotent — is satisfied uniformly.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.models import InboundTourism, MarketGrowth
from ingestion.adapters._base import (
    AdapterExtraction,
    FactRow,
    FetchResult,
    build_csv_fixture_payload,
)

log = logging.getLogger(__name__)


UNWTO_PUBLISHER = "UNWTO"
UNWTO_SOURCE_TYPE = "unwto"

# Production URL pattern. The adapter accepts an explicit override so a
# Phase 10 ops change (e.g. a new public dataset URL) does not require
# a code change.
UNWTO_DEFAULT_URL_TEMPLATE = (
    "https://www.unwto.org/tourism-data/global-and-regional-tourism-performance"
)


# ──────────────────────────────────────────────────────────────────────
# Fixture-mode (regression baseline against the curated CSV)
# ──────────────────────────────────────────────────────────────────────


_DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "regions" / "inbound_tourism.csv"


def _read_inbound_tourism_csv(path: Path, *, region_isos: Optional[Iterable[str]] = None) -> list[dict]:
    """Filter ``inbound_tourism.csv`` rows; preserves CSV ordering for stable hashes."""
    wanted = set(region_isos) if region_isos else None
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            if wanted is not None and raw["region_iso"] not in wanted:
                continue
            rows.append(
                {
                    "region_iso": raw["region_iso"],
                    "year": int(raw["year"]),
                    "international_arrivals_thousands": (
                        int(raw["international_arrivals_thousands"])
                        if raw["international_arrivals_thousands"]
                        else None
                    ),
                    "tourism_receipts_usd_millions": (
                        float(raw["tourism_receipts_usd_millions"])
                        if raw["tourism_receipts_usd_millions"]
                        else None
                    ),
                    "is_estimated": raw["is_estimated"].strip().lower() == "true",
                    "notes": raw["notes"] or None,
                    "source_url": raw["source_url"],
                }
            )
    return rows


def fetch_from_curated(
    *,
    region_isos: Optional[Iterable[str]] = None,
    fixture_path: Optional[Path] = None,
) -> FetchResult:
    """Build a deterministic payload from the curated CSV."""
    fixture = fixture_path or _DEFAULT_FIXTURE_PATH
    rows = _read_inbound_tourism_csv(fixture, region_isos=region_isos)
    payload = build_csv_fixture_payload(
        publisher=UNWTO_PUBLISHER,
        fixture_path=str(fixture.relative_to(fixture.parents[2])),
        rows=rows,
    )
    return FetchResult(
        url=UNWTO_DEFAULT_URL_TEMPLATE,
        payload=payload,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        # Pinned retrieved_at so fixture-mode runs are byte-identical
        # across invocations and the raw-store key stays stable.
    )


# ──────────────────────────────────────────────────────────────────────
# HTTP mode (production path — covered by adapter framework tests; real
# parser to be wired in Phase 10 once a stable upstream is available).
# ──────────────────────────────────────────────────────────────────────


def fetch_via_http(http_client, url: str = UNWTO_DEFAULT_URL_TEMPLATE) -> FetchResult:
    """Fetch the live UNWTO page through the rate-limited HTTP client."""
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


def extract(payload: bytes) -> AdapterExtraction:
    """Turn the fixture-mode JSON into typed ``InboundTourism`` rows.

    The parser is split into ``extract_curated`` and ``extract_html``
    so a Phase 10 swap of the upstream format only changes one branch.
    """
    text = payload.decode("utf-8", errors="replace")
    if text.lstrip().startswith("{"):
        return _extract_curated(text)
    return _extract_html(payload)


def _extract_curated(text: str) -> AdapterExtraction:
    doc = json.loads(text)
    rows = []
    for r in doc["rows"]:
        rows.append(
            FactRow(
                target=InboundTourism,
                natural_key=("region_iso", "year", "source_id"),
                payload={
                    "region_iso": r["region_iso"],
                    "year": r["year"],
                    "international_arrivals_thousands": r[
                        "international_arrivals_thousands"
                    ],
                    "tourism_receipts_usd_millions": r["tourism_receipts_usd_millions"],
                    "is_estimated": r["is_estimated"],
                    "notes": r["notes"],
                },
            )
        )
    return AdapterExtraction(
        payload=text.encode("utf-8"),
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=tuple(rows),
    )


def _extract_html(_payload: bytes) -> AdapterExtraction:
    """Placeholder HTML parser — wired up alongside the layout audit."""
    return AdapterExtraction(
        payload=_payload,
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=(),
    )


__all__ = [
    "UNWTO_PUBLISHER",
    "UNWTO_SOURCE_TYPE",
    "UNWTO_DEFAULT_URL_TEMPLATE",
    "extract",
    "fetch_from_curated",
    "fetch_via_http",
]

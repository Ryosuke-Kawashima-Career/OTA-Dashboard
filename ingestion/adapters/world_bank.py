"""World Bank adapter (T-8.2).

The World Bank publishes a stable JSON API at
``https://api.worldbank.org/v2/country/{iso}/indicator/{indicator}?format=json``.
For Phase 8 we pull two indicators per region:

* ``NY.GDP.MKTP.CD`` — GDP (current USD)
* ``ST.INT.RCPT.CD`` — Tourism receipts, current USD (overlaps UNWTO
  but provides a second publisher per region per year, satisfying the
  FR-08.1 requirement of ≥2 publishers).

Tourism receipts are written into ``inbound_tourism`` exactly the
way UNWTO writes them, which means the per-row uniqueness constraint
``(region_iso, year, source_id)`` naturally keeps both publishers'
figures around. GDP is parsed into the raw payload and surfaced via
the source row but not yet upserted because the warehouse does not
ship a dedicated ``country_macro`` table — adding one is a Phase 10
follow-up and is intentionally scoped out per the "no features beyond
what the task requires" rule.

The adapter has no HTML; it speaks JSON end-to-end so the
``layout_check`` flag should be ``False`` when calling
``run_adapter()``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.models import InboundTourism
from ingestion.adapters._base import AdapterExtraction, FactRow, FetchResult

log = logging.getLogger(__name__)


WORLD_BANK_PUBLISHER = "World Bank"
WORLD_BANK_SOURCE_TYPE = "world_bank"
WORLD_BANK_URL_TEMPLATE = (
    "https://api.worldbank.org/v2/country/{iso}/indicator/{indicator}"
    "?format=json&per_page=100"
)

INDICATOR_TOURISM_RECEIPTS = "ST.INT.RCPT.CD"
INDICATOR_GDP = "NY.GDP.MKTP.CD"


# ──────────────────────────────────────────────────────────────────────
# HTTP mode
# ──────────────────────────────────────────────────────────────────────


def fetch_via_http(
    http_client,
    *,
    region_iso: str,
    indicator: str = INDICATOR_TOURISM_RECEIPTS,
) -> FetchResult:
    url = WORLD_BANK_URL_TEMPLATE.format(iso=region_iso.lower(), indicator=indicator)
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


# ──────────────────────────────────────────────────────────────────────
# Fixture mode (offline regression baseline)
# ──────────────────────────────────────────────────────────────────────


def fetch_from_fixture(
    *,
    region_iso: str,
    indicator: str = INDICATOR_TOURISM_RECEIPTS,
    rows: Optional[Iterable[tuple[int, float]]] = None,
) -> FetchResult:
    """Build a deterministic payload mimicking the World Bank wire shape.

    Args:
        region_iso: ISO-2 code.
        indicator: full World Bank indicator code (so the fixture URL
            matches what the production HTTP call would produce).
        rows: iterable of ``(year, value)`` tuples. If ``None``, a
            small empty payload is returned (lets tests cover the
            "no data" branch).
    """
    rows = list(rows or [])
    # World Bank wire shape: [metadata_obj, [observations]] at top-level.
    fake = [
        {"page": 1, "pages": 1, "per_page": 100, "total": len(rows)},
        [
            {
                "indicator": {"id": indicator, "value": indicator},
                "country": {"id": region_iso, "value": region_iso},
                "countryiso3code": region_iso,
                "date": str(year),
                "value": value,
                "unit": "",
                "obs_status": "",
                "decimal": 0,
            }
            for year, value in rows
        ],
    ]
    url = WORLD_BANK_URL_TEMPLATE.format(iso=region_iso.lower(), indicator=indicator)
    return FetchResult(
        url=url,
        payload=json.dumps(fake, sort_keys=True).encode("utf-8"),
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


def extract(payload: bytes) -> AdapterExtraction:
    """Parse the World Bank response.

    The wire shape is ``[metadata, [observations]]``. Only tourism-
    receipts rows are upserted right now — see module docstring for
    the GDP rationale.
    """
    doc = json.loads(payload.decode("utf-8"))
    if not isinstance(doc, list) or len(doc) < 2 or not isinstance(doc[1], list):
        log.warning("world_bank: unexpected wire shape — emitting 0 rows")
        return AdapterExtraction(
            payload=payload, retrieved_at=datetime.now(timezone.utc), fact_rows=()
        )

    rows: list[FactRow] = []
    for obs in doc[1]:
        if obs.get("value") is None:
            continue
        indicator_id = (obs.get("indicator") or {}).get("id", "")
        if indicator_id != INDICATOR_TOURISM_RECEIPTS:
            # GDP and other indicators are stored in the raw payload
            # but not yet promoted to a fact table.
            continue
        rows.append(
            FactRow(
                target=InboundTourism,
                natural_key=("region_iso", "year", "source_id"),
                payload={
                    "region_iso": obs["country"]["id"],
                    "year": int(obs["date"]),
                    # World Bank reports USD; the table stores millions.
                    "international_arrivals_thousands": None,
                    "tourism_receipts_usd_millions": float(obs["value"]) / 1_000_000.0,
                    "is_estimated": False,
                    "notes": "World Bank API (ST.INT.RCPT.CD)",
                },
            )
        )
    return AdapterExtraction(
        payload=payload,
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=tuple(rows),
    )


__all__ = [
    "INDICATOR_GDP",
    "INDICATOR_TOURISM_RECEIPTS",
    "WORLD_BANK_PUBLISHER",
    "WORLD_BANK_SOURCE_TYPE",
    "WORLD_BANK_URL_TEMPLATE",
    "extract",
    "fetch_from_fixture",
    "fetch_via_http",
]

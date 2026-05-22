"""JNTO adapter (T-8.2).

JNTO (Japan National Tourism Organization) publishes monthly inbound
arrival statistics at ``statistics.jnto.go.jp``. The same five-step
adapter contract used by ``unwto.py`` applies here:

* HTTP mode hits ``JNTO_DEFAULT_URL`` and persists the bytes — the
  HTML parser is stubbed because JNTO publishes the figures inside a
  JavaScript-rendered data view, and the production solution will go
  through their downloadable CSV behind the same URL.

* Fixture mode reads the JP slice of ``inbound_tourism.csv`` so the
  warehouse can be refreshed deterministically (and the test suite
  can run with no network).

The adapter writes into ``inbound_tourism`` keyed on
``(region_iso, year, source_id)`` so two consecutive runs produce
zero duplicate rows even if JNTO republishes a corrected figure under
the same URL — the publisher's content_hash would change and a new
``sources`` row would be minted (carrying its own ``source_id``).
"""
from __future__ import annotations

from ingestion.adapters.unwto import (
    _read_inbound_tourism_csv,
    extract as _extract_inbound_tourism,
)
from ingestion.adapters._base import FetchResult, build_csv_fixture_payload
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


JNTO_PUBLISHER = "JNTO"
JNTO_SOURCE_TYPE = "jnto"
JNTO_DEFAULT_URL = "https://statistics.jnto.go.jp/en/graph/"


_DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "regions" / "inbound_tourism.csv"


def fetch_from_curated(
    *,
    fixture_path: Optional[Path] = None,
) -> FetchResult:
    """Return the JP slice of ``inbound_tourism.csv`` as a deterministic payload."""
    fixture = fixture_path or _DEFAULT_FIXTURE_PATH
    rows = _read_inbound_tourism_csv(fixture, region_isos=["JP"])
    payload = build_csv_fixture_payload(
        publisher=JNTO_PUBLISHER,
        fixture_path=str(fixture.relative_to(fixture.parents[2])),
        rows=rows,
    )
    return FetchResult(
        url=JNTO_DEFAULT_URL,
        payload=payload,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def fetch_via_http(http_client, url: str = JNTO_DEFAULT_URL) -> FetchResult:
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


# Re-export ``extract`` from unwto so the parser definition stays in
# one place — JNTO uses the same fixture schema.
extract = _extract_inbound_tourism


__all__ = [
    "JNTO_PUBLISHER",
    "JNTO_SOURCE_TYPE",
    "JNTO_DEFAULT_URL",
    "extract",
    "fetch_from_curated",
    "fetch_via_http",
]

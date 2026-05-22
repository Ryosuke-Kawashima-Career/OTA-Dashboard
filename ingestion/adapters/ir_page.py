"""Generic IR-page adapter (T-8.6).

Catches every listed rival whose filings are not on SEC EDGAR (T-8.4)
or HKEX (T-8.5):

* MakeMyTrip (NASDAQ → SEC), Trip.com (HKEX) — handled elsewhere.
* Yatra (NSE), EaseMyTrip (BSE), Cleartrip (privately held by Flipkart),
  Skyscanner (private, Trip.com-owned), eDreams ODIGEO (BME),
  Despegar (NYSE — SEC), Yanolja (private)…

Whatever the host exchange, the *production* path is the same: fetch
the HTML or PDF earnings document from the rival's IR site, parse the
financial-data table, emit one ``RivalFinancial`` row per period.

Phase 8 ships the framework only — the HTML parser is stubbed, and
fixture mode reads the slice of ``rival_financials.csv`` that is *not*
covered by SEC EDGAR or HKEX. That guarantees the warehouse converges
to the same row set whether the rival's filings come through
``sec_edgar``, ``hkex``, or ``ir_page``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Optional

from ingestion.adapters._base import FetchResult
from ingestion.adapters._financials_fixture import (
    build_fetch_result,
    extract_financials,
    iter_filings,
)
from ingestion.adapters.hkex import _is_hkex_url
from ingestion.adapters.sec_edgar import _is_sec_url

log = logging.getLogger(__name__)


IR_PAGE_PUBLISHER = "Rival IR page"
IR_PAGE_SOURCE_TYPE = "ir_page"


def _is_other_ir_url(url: str) -> bool:
    return not (_is_sec_url(url) or _is_hkex_url(url))


def iter_ir_filings(
    fixture_path: Optional[Path] = None,
) -> Iterator[tuple[str, list[dict]]]:
    return iter_filings(url_predicate=_is_other_ir_url, fixture_path=fixture_path)


def build_ir_fetch_result(*, url: str, rows: list[dict]) -> FetchResult:
    return build_fetch_result(publisher=IR_PAGE_PUBLISHER, url=url, rows=rows)


def fetch_via_http(http_client, url: str) -> FetchResult:
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


extract = extract_financials


__all__ = [
    "IR_PAGE_PUBLISHER",
    "IR_PAGE_SOURCE_TYPE",
    "build_ir_fetch_result",
    "extract",
    "fetch_via_http",
    "iter_ir_filings",
]

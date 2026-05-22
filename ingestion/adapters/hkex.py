"""HKEX adapter (T-8.5).

Trip.com Group (ticker ``9961``) files its semi-annual reports +
interim disclosures on the Hong Kong Exchange (HKEX). Filings are
downloadable as PDFs from
``https://www1.hkexnews.hk/listedco/listconews/sehk/{yyyy}/{mm}/{filename}``.

Production behaviour (Phase 10):

* ``fetch_via_http`` retrieves the PDF.
* ``pdf_report.extract_financials`` parses the table of selected
  financial data into ``RivalFinancial`` rows.

Phase 8 behaviour (this file):

* Slice ``rival_financials.csv`` on hosts that look HKEX-shaped — both
  ``hkexnews.hk`` (filing repository) and ``ir.trip.com`` (where
  Trip.com's own IR mirror hosts the same numbers). Each filing URL
  produces one ``sources`` row + the corresponding ``RivalFinancial``
  rows.
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

log = logging.getLogger(__name__)


HKEX_PUBLISHER = "HKEX"
HKEX_SOURCE_TYPE = "hkex"
HKEX_BASE_URL = "https://www1.hkexnews.hk/"


def _is_hkex_url(url: str) -> bool:
    low = url.lower()
    return "hkex" in low or "hkexnews" in low or "ir.trip.com" in low


def iter_hkex_filings(
    fixture_path: Optional[Path] = None,
) -> Iterator[tuple[str, list[dict]]]:
    return iter_filings(url_predicate=_is_hkex_url, fixture_path=fixture_path)


def build_hkex_fetch_result(*, url: str, rows: list[dict]) -> FetchResult:
    return build_fetch_result(publisher=HKEX_PUBLISHER, url=url, rows=rows)


def fetch_via_http(http_client, url: str) -> FetchResult:
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


extract = extract_financials


__all__ = [
    "HKEX_BASE_URL",
    "HKEX_PUBLISHER",
    "HKEX_SOURCE_TYPE",
    "build_hkex_fetch_result",
    "extract",
    "fetch_via_http",
    "iter_hkex_filings",
]

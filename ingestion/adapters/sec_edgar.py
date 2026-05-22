"""SEC EDGAR adapter (T-8.4).

The US-listed rivals (Booking Holdings — BKNG, Expedia Group — EXPE,
Airbnb — ABNB) file 10-K (annual) and 10-Q (quarterly) reports via SEC
EDGAR. The filings expose financials as XBRL inside an iXBRL-wrapped
HTML document, addressable via stable URLs of the form
``https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}``.

Production behaviour (Phase 10):

* ``fetch_via_http`` retrieves the iXBRL document.
* The XBRL fact extractor (``ingestion/extractors/financial_extractor.py``,
  scoped to Phase 9 alongside the other LLM/regex fallback chains)
  parses ``us-gaap:Revenues`` / ``us-gaap:OperatingIncomeLoss`` / segment
  facts into the ``RivalFinancial`` shape.

Phase 8 behaviour (this file):

* ``iter_filings`` walks ``data/rivals/rival_financials.csv`` and slices
  out the rows whose ``source_url`` is on ``sec.gov``. Each filing URL
  becomes one ``sources`` row, and the corresponding ``RivalFinancial``
  rows upsert under their natural key.

The acceptance check is the latest filing per rival appears in the
warehouse with non-null ``revenue_usd`` and ``take_rate_pct``, which is
exactly what the curated CSV guarantees for the four US-listed names.
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


SEC_EDGAR_PUBLISHER = "SEC EDGAR"
SEC_EDGAR_SOURCE_TYPE = "sec_edgar"
SEC_EDGAR_BASE_URL = "https://www.sec.gov/Archives/edgar/"


def _is_sec_url(url: str) -> bool:
    return "sec.gov" in url.lower()


def iter_sec_filings(
    fixture_path: Optional[Path] = None,
) -> Iterator[tuple[str, list[dict]]]:
    return iter_filings(url_predicate=_is_sec_url, fixture_path=fixture_path)


def build_sec_fetch_result(*, url: str, rows: list[dict]) -> FetchResult:
    return build_fetch_result(publisher=SEC_EDGAR_PUBLISHER, url=url, rows=rows)


def fetch_via_http(http_client, url: str) -> FetchResult:
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


extract = extract_financials


__all__ = [
    "SEC_EDGAR_BASE_URL",
    "SEC_EDGAR_PUBLISHER",
    "SEC_EDGAR_SOURCE_TYPE",
    "build_sec_fetch_result",
    "extract",
    "fetch_via_http",
    "iter_sec_filings",
]

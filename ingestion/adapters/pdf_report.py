"""PDF earnings-report adapter (T-8.6 companion to ``ir_page.py``).

Most rivals publish PDFs alongside (or instead of) HTML earnings pages.
The PDF route is functionally identical to the HTML route — same
``RivalFinancial`` natural key, same source-row contract — but the
extraction step uses ``pdfplumber`` to walk the financial-data table.

Phase 8 ships the framework: an HTTP fetcher that persists the raw
PDF bytes, a fixture helper that decodes a curated row through the
shared ``extract_financials`` parser, and a ``pdf_to_text`` stub the
Phase 9 LLM extractor will plug into when XBRL/regex aren't enough.
"""
from __future__ import annotations

import logging
from typing import Optional

from ingestion.adapters._base import FetchResult
from ingestion.adapters._financials_fixture import (
    build_fetch_result as _build_fixture_fetch_result,
    extract_financials,
)

log = logging.getLogger(__name__)


PDF_REPORT_PUBLISHER = "Rival PDF report"
PDF_REPORT_SOURCE_TYPE = "pdf_report"


def fetch_via_http(http_client, url: str) -> FetchResult:
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


def build_pdf_fetch_result(*, url: str, rows: list[dict]) -> FetchResult:
    return _build_fixture_fetch_result(
        publisher=PDF_REPORT_PUBLISHER, url=url, rows=rows
    )


def pdf_to_text(pdf_bytes: bytes, *, max_pages: Optional[int] = None) -> str:
    """Best-effort PDF → text extraction.

    Returns an empty string if ``pdfplumber`` is not installed or if the
    bytes do not look like a PDF — that keeps the Phase 8 test surface
    runnable on a barebones interpreter. The Phase 9 LLM extractor
    will inject pdfplumber via the ingestion requirements file.
    """
    if not pdf_bytes.startswith(b"%PDF"):
        return ""
    try:
        import io

        import pdfplumber
    except ImportError:
        log.info("pdfplumber not installed; pdf_to_text returning empty string")
        return ""
    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for page in pages:
            text = page.extract_text() or ""
            chunks.append(text)
    return "\n".join(chunks)


extract = extract_financials


__all__ = [
    "PDF_REPORT_PUBLISHER",
    "PDF_REPORT_SOURCE_TYPE",
    "build_pdf_fetch_result",
    "extract",
    "fetch_via_http",
    "pdf_to_text",
]

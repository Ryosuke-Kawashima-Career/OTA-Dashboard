"""daily_filings flow (T-8.9, NFR-01 24-hour SLA on filings).

Orchestrates the three rival-financial adapters (SEC EDGAR, HKEX,
generic IR/PDF) plus the market-share estimator service. Filings have
a stricter cadence than market data (24-hour SLA per NFR-01), so this
flow is scheduled every 6 hours in production — well under the SLA so
we can absorb an isolated upstream outage without breaching it.

Pipeline shape:

  per-filing-URL  ──► run_adapter (raw → layout → record → upsert)
                              │
                              ▼
                       rival_financial
                              │
                              ▼
                  share_estimator.run  (T-8.7)
                              │
                              ▼
                    market_share_estimate

The estimator runs at the *end* of the flow, after every adapter has
written its ``rival_financial`` rows for the period, so the share
calculation sees the freshest revenue numbers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

from app.services import share_estimator
from ingestion.adapters import run_adapter
from ingestion.adapters._base import AdapterRunSummary
from ingestion.adapters.hkex import (
    HKEX_PUBLISHER,
    HKEX_SOURCE_TYPE,
    build_hkex_fetch_result,
    extract as extract_hkex,
    iter_hkex_filings,
)
from ingestion.adapters.ir_page import (
    IR_PAGE_PUBLISHER,
    IR_PAGE_SOURCE_TYPE,
    build_ir_fetch_result,
    extract as extract_ir,
    iter_ir_filings,
)
from ingestion.adapters.sec_edgar import (
    SEC_EDGAR_PUBLISHER,
    SEC_EDGAR_SOURCE_TYPE,
    build_sec_fetch_result,
    extract as extract_sec,
    iter_sec_filings,
)
from ingestion.db import session_scope
from ingestion.monitor import LayoutChangeDetector
from ingestion.raw_store import RawPayloadStore, default_raw_store

log = logging.getLogger(__name__)


DEFAULT_LAYOUT_STATE_DIR = Path("raw_store_data/_layout_fingerprints")


@dataclass(frozen=True)
class DailyFilingsRunSummary:
    total_financial_rows: int
    derived_share_rows: int
    per_adapter: tuple[AdapterRunSummary, ...] = field(default_factory=tuple)


@task(name="daily_filings.sec_edgar", cache_policy=NO_CACHE)
def _run_sec(*, session, raw_store, detector) -> list[AdapterRunSummary]:
    summaries: list[AdapterRunSummary] = []
    for url, rows in iter_sec_filings():
        fetch_result = build_sec_fetch_result(url=url, rows=rows)
        summary = run_adapter(
            adapter_name=f"sec_edgar:{url[-40:]}",
            fetch_result=fetch_result,
            extract_fn=extract_sec,
            session=session,
            raw_store=raw_store,
            detector=detector,
            publisher=SEC_EDGAR_PUBLISHER,
            source_type=SEC_EDGAR_SOURCE_TYPE,
            layout_check=False,  # JSON fixture (HTML/XBRL in production gets layout_check=True)
        )
        summaries.append(summary)
    return summaries


@task(name="daily_filings.hkex", cache_policy=NO_CACHE)
def _run_hkex(*, session, raw_store, detector) -> list[AdapterRunSummary]:
    summaries: list[AdapterRunSummary] = []
    for url, rows in iter_hkex_filings():
        fetch_result = build_hkex_fetch_result(url=url, rows=rows)
        summary = run_adapter(
            adapter_name=f"hkex:{url[-40:]}",
            fetch_result=fetch_result,
            extract_fn=extract_hkex,
            session=session,
            raw_store=raw_store,
            detector=detector,
            publisher=HKEX_PUBLISHER,
            source_type=HKEX_SOURCE_TYPE,
            layout_check=False,
        )
        summaries.append(summary)
    return summaries


@task(name="daily_filings.ir_page", cache_policy=NO_CACHE)
def _run_ir(*, session, raw_store, detector) -> list[AdapterRunSummary]:
    summaries: list[AdapterRunSummary] = []
    for url, rows in iter_ir_filings():
        fetch_result = build_ir_fetch_result(url=url, rows=rows)
        summary = run_adapter(
            adapter_name=f"ir_page:{url[-40:]}",
            fetch_result=fetch_result,
            extract_fn=extract_ir,
            session=session,
            raw_store=raw_store,
            detector=detector,
            publisher=IR_PAGE_PUBLISHER,
            source_type=IR_PAGE_SOURCE_TYPE,
            layout_check=False,
        )
        summaries.append(summary)
    return summaries


@task(name="daily_filings.share_estimator", cache_policy=NO_CACHE)
def _run_share_estimator(*, session) -> int:
    return share_estimator.run(session)


@flow(name="daily_filings")
def daily_filings_flow(
    *,
    raw_store: Optional[RawPayloadStore] = None,
    detector: Optional[LayoutChangeDetector] = None,
    run_estimator: bool = True,
) -> DailyFilingsRunSummary:
    raw_store = raw_store or default_raw_store()
    detector = detector or LayoutChangeDetector(DEFAULT_LAYOUT_STATE_DIR)

    per_adapter: list[AdapterRunSummary] = []
    derived_rows = 0
    with session_scope() as session:
        per_adapter.extend(_run_sec(session=session, raw_store=raw_store, detector=detector))
        per_adapter.extend(_run_hkex(session=session, raw_store=raw_store, detector=detector))
        per_adapter.extend(_run_ir(session=session, raw_store=raw_store, detector=detector))
        # Estimator reads what we just wrote — flush so the session sees
        # the rows from this same transaction.
        session.flush()
        if run_estimator:
            derived_rows = _run_share_estimator(session=session)

    total = sum(s.fact_rows_upserted for s in per_adapter)
    log.info(
        "daily_filings: upserted %d financial rows across %d filings; estimated %d share rows",
        total, len(per_adapter), derived_rows,
    )
    return DailyFilingsRunSummary(
        total_financial_rows=total,
        derived_share_rows=derived_rows,
        per_adapter=tuple(per_adapter),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    summary = daily_filings_flow()
    print(summary)

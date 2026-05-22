"""monthly_market flow (T-8.8, NFR-01 monthly cadence).

Orchestrates the three market-data adapters (UNWTO, JNTO, World Bank,
IMF, industry research) into a single Prefect flow that runs every
month. Each adapter's output flows through the standard
``run_adapter()`` pipeline so every fact row carries a ``source_id``
and re-runs are idempotent.

Why one flow and not five separate ones:

* The five adapters write to overlapping fact tables
  (``inbound_tourism``, ``market_growth``), so running them together
  inside a single transaction surfaces consistency issues
  immediately — e.g. a UNWTO outage that leaves only the World Bank
  side populated for a year would be caught by the per-flow
  acceptance test.

* Prefect lets us still observe each adapter as its own task within
  the flow, so the operator's view is identical to running five
  separate flows.

The flow is the **production** entry point but is also re-runnable in
fixture mode — the default behaviour for ``run()``, used by the test
suite and by anyone wanting to refresh the warehouse from the
curated CSVs without hitting upstream sources.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

from ingestion.adapters import run_adapter
from ingestion.adapters._base import AdapterRunSummary
from ingestion.adapters.industry_research import (
    build_fetch_result as build_industry_fetch_result,
    extract as extract_industry,
    iter_publishers,
)
from ingestion.adapters.jnto import (
    JNTO_PUBLISHER,
    JNTO_SOURCE_TYPE,
    extract as extract_jnto,
    fetch_from_curated as fetch_jnto,
)
from ingestion.adapters.unwto import (
    UNWTO_PUBLISHER,
    UNWTO_SOURCE_TYPE,
    extract as extract_unwto,
    fetch_from_curated as fetch_unwto,
)
from ingestion.db import session_scope
from ingestion.monitor import LayoutChangeDetector
from ingestion.raw_store import RawPayloadStore, default_raw_store

log = logging.getLogger(__name__)


DEFAULT_LAYOUT_STATE_DIR = Path("raw_store_data/_layout_fingerprints")


@dataclass(frozen=True)
class MonthlyMarketRunSummary:
    """Returned by the flow for tests and operators to assert on."""

    total_fact_rows: int
    per_adapter: tuple[AdapterRunSummary, ...] = field(default_factory=tuple)


@task(name="monthly_market.unwto", cache_policy=NO_CACHE)
def _run_unwto(
    *, session, raw_store: RawPayloadStore, detector: LayoutChangeDetector
) -> AdapterRunSummary:
    return run_adapter(
        adapter_name="unwto",
        fetch_result=fetch_unwto(),
        extract_fn=extract_unwto,
        session=session,
        raw_store=raw_store,
        detector=detector,
        publisher=UNWTO_PUBLISHER,
        source_type=UNWTO_SOURCE_TYPE,
        layout_check=False,  # JSON fixture, not HTML
    )


@task(name="monthly_market.jnto", cache_policy=NO_CACHE)
def _run_jnto(
    *, session, raw_store: RawPayloadStore, detector: LayoutChangeDetector
) -> AdapterRunSummary:
    return run_adapter(
        adapter_name="jnto",
        fetch_result=fetch_jnto(),
        extract_fn=extract_jnto,
        session=session,
        raw_store=raw_store,
        detector=detector,
        publisher=JNTO_PUBLISHER,
        source_type=JNTO_SOURCE_TYPE,
        layout_check=False,
    )


@task(name="monthly_market.industry_research", cache_policy=NO_CACHE)
def _run_industry_research(
    *,
    session,
    raw_store: RawPayloadStore,
    detector: LayoutChangeDetector,
) -> list[AdapterRunSummary]:
    summaries: list[AdapterRunSummary] = []
    for publisher, source_type, canonical_url, rows in iter_publishers():
        fetch_result = build_industry_fetch_result(
            publisher=publisher, canonical_url=canonical_url, rows=rows
        )
        summary = run_adapter(
            adapter_name=f"industry_research:{source_type}",
            fetch_result=fetch_result,
            extract_fn=extract_industry,
            session=session,
            raw_store=raw_store,
            detector=detector,
            publisher=publisher,
            source_type=source_type,
            layout_check=False,
        )
        summaries.append(summary)
    return summaries


@flow(name="monthly_market")
def monthly_market_flow(
    *,
    raw_store: Optional[RawPayloadStore] = None,
    detector: Optional[LayoutChangeDetector] = None,
) -> MonthlyMarketRunSummary:
    raw_store = raw_store or default_raw_store()
    detector = detector or LayoutChangeDetector(DEFAULT_LAYOUT_STATE_DIR)

    per_adapter: list[AdapterRunSummary] = []
    with session_scope() as session:
        per_adapter.append(_run_unwto(session=session, raw_store=raw_store, detector=detector))
        per_adapter.append(_run_jnto(session=session, raw_store=raw_store, detector=detector))
        per_adapter.extend(
            _run_industry_research(session=session, raw_store=raw_store, detector=detector)
        )

    total = sum(s.fact_rows_upserted for s in per_adapter)
    log.info("monthly_market: upserted %d fact rows across %d adapters", total, len(per_adapter))
    return MonthlyMarketRunSummary(
        total_fact_rows=total,
        per_adapter=tuple(per_adapter),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    summary = monthly_market_flow()
    print(summary)

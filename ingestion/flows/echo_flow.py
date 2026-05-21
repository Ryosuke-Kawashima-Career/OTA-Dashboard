"""Echo flow (T-7.5) — proves the Phase 7 pipeline runs end-to-end.

Steps, in order:

  1. `fetch()` the synthetic fixture (bytes).
  2. Persist the raw payload to the configured `RawPayloadStore`.
  3. Compute the DOM-skeleton fingerprint and consult the
     `LayoutChangeDetector`. If it reports drift, alert and *skip the
     upsert* — exactly the production failure mode we want to enforce.
  4. Record (or fetch) the `Source` row via the provenance recorder.
  5. `extract()` synthetic fact rows and `upsert(...)` them into
     `market_growth` keyed on the migration's `(region_iso, year,
     source_id)` unique constraint, so re-runs converge instead of
     duplicating.

The flow function is decorated with `@prefect.flow` so it can be
scheduled and observed via Prefect, but it remains a normal Python
callable — `echo_flow()` works fine in a unit test or `python -m`
invocation, with no Prefect server required.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from prefect import flow

from app.models import MarketGrowth
from ingestion.adapters.echo import (
    ECHO_CONTENT_HASH_TAG,
    ECHO_PUBLISHER,
    ECHO_SOURCE_TYPE,
    ECHO_SOURCE_URL,
    extract,
    fetch,
)
from ingestion.db import session_scope
from ingestion.monitor import LayoutChangeDetector, dom_skeleton_hash, post_alert
from ingestion.normalizer import upsert
from ingestion.provenance import record
from ingestion.raw_store import RawPayloadStore, default_raw_store

log = logging.getLogger(__name__)

# Layout-fingerprint state lives next to the raw-payload store by default
# so dev + test runs are self-contained.
DEFAULT_LAYOUT_STATE_DIR = Path("raw_store_data/_layout_fingerprints")


@dataclass(frozen=True)
class EchoRunSummary:
    """Return value of `echo_flow()` — the values a test or operator
    would want to assert on without re-querying the database."""

    status: str  # "ok" | "skipped_layout_drift"
    source_id: Optional[str]
    raw_payload_ref: Optional[str]
    fact_rows_upserted: int


@flow(name="echo")
def echo_flow(
    *,
    raw_store: RawPayloadStore | None = None,
    detector: LayoutChangeDetector | None = None,
) -> EchoRunSummary:
    raw_store = raw_store or default_raw_store()
    detector = detector or LayoutChangeDetector(DEFAULT_LAYOUT_STATE_DIR)

    extraction = extract()
    payload = extraction.payload

    # (2) Raw-first: persist bytes before any parsing.
    raw_ref = raw_store.write(
        payload, source_type=ECHO_SOURCE_TYPE, retrieved_at=extraction.retrieved_at
    )

    # (3) Layout-change guard — silently corrupt data is the failure mode
    # we're protecting against, so on novel fingerprints we alert AND
    # short-circuit before touching the warehouse.
    fingerprint = dom_skeleton_hash(payload.decode("utf-8"))
    check = detector.check(ECHO_SOURCE_URL, fingerprint)
    if check.changed:
        post_alert(
            f"Layout drift detected on {ECHO_SOURCE_URL}: "
            f"new fingerprint={fingerprint[:12]}…, "
            f"prior window={[h[:12] + '…' for h in check.prior_window]}",
            level="warning",
        )
        return EchoRunSummary(
            status="skipped_layout_drift",
            source_id=None,
            raw_payload_ref=raw_ref,
            fact_rows_upserted=0,
        )

    # (4) + (5) Record provenance and upsert the synthetic fact row.
    # Tying the content hash to the payload bytes (not the tag) means a
    # changed fixture would naturally produce a new Source row — same
    # contract every real adapter will use.
    content_hash = hashlib.sha256(payload).hexdigest()
    with session_scope() as session:
        source_id = record(
            session,
            url=ECHO_SOURCE_URL,
            publisher=ECHO_PUBLISHER,
            source_type=ECHO_SOURCE_TYPE,
            content_hash=content_hash,
            retrieved_at=extraction.retrieved_at,
            raw_payload_ref=raw_ref,
        )
        for row in extraction.fact_rows:
            upsert(
                session,
                MarketGrowth,
                natural_key=("region_iso", "year", "source_id"),
                payload={
                    "region_iso": row.region_iso,
                    "year": row.year,
                    "market_size_usd": row.market_size_usd,
                    "growth_rate_pct": row.growth_rate_pct,
                    "source_id": source_id,
                },
            )

    return EchoRunSummary(
        status="ok",
        source_id=str(source_id),
        raw_payload_ref=raw_ref,
        fact_rows_upserted=len(extraction.fact_rows),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    summary = echo_flow()
    print(summary)

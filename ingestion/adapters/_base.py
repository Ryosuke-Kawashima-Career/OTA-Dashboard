"""Common adapter scaffolding (Phase 8).

Every production adapter follows the same five-step shape that the
Phase 7 echo adapter introduced:

    fetch → persist raw → layout-change check → record source → upsert facts

`AdapterExtraction` standardises the structured output every adapter
hands to the orchestrating flow. `run_adapter()` performs the five
steps so individual adapters can stay focused on their HTML / XBRL /
JSON parsing.

Adapters expose two callables:

* ``fetch(http_client, **params) -> FetchResult`` — returns the raw
  bytes (and the URL that produced them). May return ``skipped=True``
  when robots.txt or a fixture sentinel blocks the call; the flow
  decides whether that's fatal.
* ``extract(payload, **context) -> AdapterExtraction`` — pure function
  over the fetched bytes; never touches the network.

Keeping `fetch` and `extract` separate lets unit tests bypass the
network entirely (feed `extract` a fixture from ``data/``) and lets
production flows route every byte through the same raw-payload store
without reparsing.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from sqlalchemy.orm import DeclarativeBase, Session

from ingestion.monitor import LayoutChangeDetector, dom_skeleton_hash, post_alert
from ingestion.normalizer import upsert
from ingestion.provenance import record
from ingestion.raw_store import RawPayloadStore

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Shared dataclasses
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FetchResult:
    """Adapter-agnostic shape returned by every ``fetch()``.

    ``skipped`` mirrors ``HttpResult.skipped`` so flows treat a
    voluntary skip the same way regardless of whether the adapter
    used the HTTP client directly or its own fallback.
    """

    url: str
    payload: bytes = b""
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    skipped: bool = False
    skip_reason: str = ""


@dataclass(frozen=True)
class FactRow:
    """Output of ``extract()``.

    A row is the natural-key payload mapping for one DB upsert. We keep
    the model class on the row itself so a single ``extract()`` call
    can emit rows for multiple tables (e.g. SEC EDGAR yields one
    ``RivalFinancial`` per filing period).
    """

    target: type[DeclarativeBase]
    natural_key: tuple[str, ...]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AdapterExtraction:
    """Structured output of one adapter run, prior to source binding."""

    payload: bytes
    retrieved_at: datetime
    fact_rows: tuple[FactRow, ...]


@dataclass(frozen=True)
class AdapterRunSummary:
    """Returned by ``run_adapter()`` — the values a flow asserts on."""

    adapter: str
    status: str  # "ok" | "skipped_layout_drift" | "skipped_fetch" | "no_rows"
    source_id: Optional[str]
    raw_payload_ref: Optional[str]
    fact_rows_upserted: int


# ──────────────────────────────────────────────────────────────────────
# Orchestration helper
# ──────────────────────────────────────────────────────────────────────


def run_adapter(
    *,
    adapter_name: str,
    fetch_result: FetchResult,
    extract_fn: Callable[[bytes], AdapterExtraction],
    session: Session,
    raw_store: RawPayloadStore,
    detector: LayoutChangeDetector,
    publisher: str,
    source_type: str,
    layout_check: bool = True,
) -> AdapterRunSummary:
    """Execute the standard five-step pipeline for one adapter run.

    Args:
        adapter_name: short identifier (e.g. ``"unwto"``) used in
            log messages and the returned summary.
        fetch_result: bytes + URL produced by the adapter's ``fetch()``.
        extract_fn: callable taking ``payload: bytes`` and returning
            an ``AdapterExtraction``. Kept as a callable rather than
            an ``AdapterExtraction`` directly so the layout-change guard
            can short-circuit *before* paying the parse cost when the
            page has drifted.
        session: live SQLAlchemy session (caller commits via the
            session_scope context manager).
        raw_store: backend for raw payload persistence.
        detector: layout-change watcher; per-URL state lives in the
            detector's on-disk JSON file.
        publisher: domain or organisation that owns the source URL.
        source_type: short tag (``"sec_edgar"``, ``"unwto"``, …) used
            in the ``sources.source_type`` column and the raw_store
            key layout.
        layout_check: set ``False`` for JSON APIs / structured feeds
            where DOM-skeleton hashing is nonsense (the structure
            literally is the data). Defaults to ``True`` for HTML/XBRL.

    Returns an ``AdapterRunSummary``.
    """
    if fetch_result.skipped:
        log.info(
            "[%s] fetch skipped (%s); short-circuiting",
            adapter_name,
            fetch_result.skip_reason,
        )
        return AdapterRunSummary(
            adapter=adapter_name,
            status="skipped_fetch",
            source_id=None,
            raw_payload_ref=None,
            fact_rows_upserted=0,
        )

    payload = fetch_result.payload
    if not payload:
        return AdapterRunSummary(
            adapter=adapter_name,
            status="no_rows",
            source_id=None,
            raw_payload_ref=None,
            fact_rows_upserted=0,
        )

    # (1) Raw-first.
    raw_ref = raw_store.write(
        payload, source_type=source_type, retrieved_at=fetch_result.retrieved_at
    )

    # (2) Layout drift guard — only for HTML-ish payloads.
    if layout_check:
        try:
            fingerprint = dom_skeleton_hash(payload.decode("utf-8", errors="replace"))
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("[%s] fingerprint failed: %s — skipping detector", adapter_name, exc)
            fingerprint = None
        if fingerprint is not None:
            check = detector.check(fetch_result.url, fingerprint)
            if check.changed:
                post_alert(
                    f"[{adapter_name}] layout drift on {fetch_result.url}: "
                    f"new={fingerprint[:12]}…, "
                    f"prior={[h[:12] + '…' for h in check.prior_window]}",
                    level="warning",
                )
                return AdapterRunSummary(
                    adapter=adapter_name,
                    status="skipped_layout_drift",
                    source_id=None,
                    raw_payload_ref=raw_ref,
                    fact_rows_upserted=0,
                )

    # (3) Parse — payload is now safe to consume.
    extraction = extract_fn(payload)

    # (4) Record provenance.
    content_hash = hashlib.sha256(payload).hexdigest()
    source_id = record(
        session,
        url=fetch_result.url,
        publisher=publisher,
        source_type=source_type,
        content_hash=content_hash,
        retrieved_at=fetch_result.retrieved_at,
        raw_payload_ref=raw_ref,
    )

    # (5) Upsert every fact row, attaching the freshly-minted source_id.
    for row in extraction.fact_rows:
        payload_with_source = dict(row.payload)
        payload_with_source.setdefault("source_id", source_id)
        upsert(
            session,
            row.target,
            natural_key=row.natural_key,
            payload=payload_with_source,
        )

    return AdapterRunSummary(
        adapter=adapter_name,
        status="ok",
        source_id=str(source_id),
        raw_payload_ref=raw_ref,
        fact_rows_upserted=len(extraction.fact_rows),
    )


# ──────────────────────────────────────────────────────────────────────
# Fixture-mode helper
# ──────────────────────────────────────────────────────────────────────


def build_csv_fixture_payload(
    *,
    publisher: str,
    fixture_path: str,
    rows: Sequence[Mapping[str, Any]],
) -> bytes:
    """Encode a list of dict rows as deterministic JSON bytes.

    Used by adapter fixture-mode runners so the raw-payload store key
    (which is content-addressed on sha256) is stable across runs of the
    same fixture. Adapters that prefer their own native format (XBRL
    XML, IXBRL HTML, …) can implement their own encoder; this helper
    just covers the common case where the upstream "real" payload is
    a tabular JSON or CSV doc.
    """
    import json

    return json.dumps(
        {
            "publisher": publisher,
            "fixture_path": fixture_path,
            "rows": list(rows),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


__all__ = [
    "AdapterExtraction",
    "AdapterRunSummary",
    "FactRow",
    "FetchResult",
    "build_csv_fixture_payload",
    "run_adapter",
]

"""Provenance recorder (T-7.3, FR-08.6).

The single entry point for every adapter that needs to attach a fact row
to a public source. Calling `record(...)` twice with the same
`(url, content_hash)` returns the same `source_id` — the warehouse's
unique constraint `uq_sources_url_content_hash` makes the operation
idempotent at the database level, and this function turns that into an
ergonomic Python API.

Adapters never construct `Source` objects directly; they always go
through `record()` so the contract stays in one place.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Source


def record(
    session: Session,
    *,
    url: str,
    publisher: str,
    source_type: str,
    content_hash: str,
    retrieved_at: datetime | None = None,
    raw_payload_ref: str | None = None,
) -> uuid.UUID:
    """Insert-or-fetch a `Source` row keyed by `(url, content_hash)`.

    Returns the row's UUID. Safe to call concurrently from multiple
    workers — the ON CONFLICT clause makes the insert race-free, and a
    follow-up SELECT picks up whichever row "won" the race.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)

    stmt = (
        pg_insert(Source.__table__)
        .values(
            url=url,
            publisher=publisher,
            source_type=source_type,
            retrieved_at=retrieved_at,
            raw_payload_ref=raw_payload_ref,
            content_hash=content_hash,
        )
        .on_conflict_do_nothing(constraint="uq_sources_url_content_hash")
        .returning(Source.id)
    )
    inserted = session.execute(stmt).scalar_one_or_none()
    if inserted is not None:
        return inserted

    # Either ON CONFLICT DO NOTHING fired, or a concurrent writer beat us
    # to it — either way the canonical row already exists, so fetch its id.
    existing = session.execute(
        select(Source.id).where(
            Source.url == url, Source.content_hash == content_hash
        )
    ).scalar_one()
    return existing

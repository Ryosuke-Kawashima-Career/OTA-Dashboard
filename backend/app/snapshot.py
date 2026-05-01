"""Shared helpers for the time-period filter (Phase 5, FR-06)."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegionMetrics


def parse_snapshot_month(value: str | None) -> date | None:
    """Parse an ISO-format ``YYYY-MM-DD`` query param into a ``date``.

    ``None`` → ``None`` (caller will resolve the default). Anything else
    must be a valid ISO date or we raise 400 — silently swallowing typos
    leads to subtle "why is the dashboard empty?" bugs.
    """
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid snapshot_month {value!r}; expected YYYY-MM-DD.",
        ) from exc


async def latest_snapshot_month(db: AsyncSession) -> date | None:
    """Return the most recent ``snapshot_month`` present in ``region_metrics``."""
    return (await db.execute(select(func.max(RegionMetrics.snapshot_month)))).scalar_one_or_none()


async def resolve_snapshot_month(db: AsyncSession, requested: date | None) -> date | None:
    """Resolve a request to an actual snapshot date.

    Order: explicit request → DB latest → ``None`` (no data seeded yet).
    Returning ``None`` lets endpoints render an empty-but-valid response
    rather than 500ing on a fresh database.
    """
    if requested is not None:
        return requested
    return await latest_snapshot_month(db)

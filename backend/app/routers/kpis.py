"""KPIs router — serves global summary KPIs for the dashboard header (FR-04)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Region, RegionMetrics, Rival
from app.snapshot import parse_snapshot_month, resolve_snapshot_month

router = APIRouter(prefix="/api", tags=["kpis"])


@router.get("/kpis/global")
async def get_global_kpis(
    db: AsyncSession = Depends(get_db),
    snapshot_month: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return the three global summary KPIs for the dashboard header.

    Shape:
        {
          markets_covered: int,         # countries with a metrics row at the requested snapshot
          tracked_rivals: int,          # total rivals in the roster
          hottest_growth_region: {      # highest demand_index in the requested month, or null
            iso_code, name, demand_index
          } | null,
          snapshot_month: str | null    # the snapshot month the figures refer to
        }

    Notes:
    - "Markets covered" counts distinct region ISOs that have a metrics row in
      the requested snapshot, so historical years correctly reflect coverage
      growth as we ingest more countries.
    - The hottest-growth region is computed against that same snapshot.
    """
    snap = await resolve_snapshot_month(db, parse_snapshot_month(snapshot_month))

    markets_covered = 0
    if snap is not None:
        markets_covered = (
            await db.execute(
                select(func.count(distinct(RegionMetrics.region_iso))).where(
                    RegionMetrics.snapshot_month == snap
                )
            )
        ).scalar_one()

    tracked_rivals = (await db.execute(select(func.count(Rival.id)))).scalar_one()

    hottest: dict[str, Any] | None = None
    if snap is not None:
        row = (
            await db.execute(
                select(
                    RegionMetrics.region_iso,
                    Region.name,
                    RegionMetrics.demand_index,
                )
                .join(Region, Region.iso_code == RegionMetrics.region_iso)
                .where(RegionMetrics.snapshot_month == snap)
                .where(RegionMetrics.demand_index.is_not(None))
                .order_by(RegionMetrics.demand_index.desc())
                .limit(1)
            )
        ).first()
        if row is not None:
            iso, name, demand_index = row
            hottest = {
                "iso_code": iso,
                "name": name,
                "demand_index": demand_index,
            }

    return {
        "markets_covered": int(markets_covered or 0),
        "tracked_rivals": int(tracked_rivals or 0),
        "hottest_growth_region": hottest,
        "snapshot_month": snap.isoformat() if snap else None,
    }

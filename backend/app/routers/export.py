"""Export router — serves the dashboard data as CSV (Phase 5, FR-06)."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Region, RegionMetrics, Rival, RivalRegionSnapshot
from app.snapshot import parse_snapshot_month, resolve_snapshot_month

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    snapshot_month: str | None = Query(default=None),
) -> Response:
    """Return the per-region snapshot as CSV.

    Columns: ``snapshot_month, iso_code, name, continent, demand_index,
    avg_booking_value, top_rival, top_rival_share_pct``. The "top rival"
    is the rival with the highest market share in that region for the
    requested month — handy for spreadsheet pivots without having to join
    the snapshot table manually.

    Empty body (just the header) is returned when the DB has no metrics
    for the requested month — a valid CSV is preferable to a 500 here.
    """
    snap = await resolve_snapshot_month(db, parse_snapshot_month(snapshot_month))

    metric_rows: list[tuple] = []
    top_rival_by_iso: dict[str, tuple[str, float]] = {}
    if snap is not None:
        metric_rows = (
            await db.execute(
                select(
                    RegionMetrics.snapshot_month,
                    RegionMetrics.region_iso,
                    Region.name,
                    Region.continent,
                    RegionMetrics.demand_index,
                    RegionMetrics.avg_booking_value,
                )
                .join(Region, Region.iso_code == RegionMetrics.region_iso)
                .where(RegionMetrics.snapshot_month == snap)
                .order_by(RegionMetrics.region_iso)
            )
        ).all()

        # Highest-share rival per region for the same snapshot
        rival_rows = (
            await db.execute(
                select(
                    RivalRegionSnapshot.region_iso,
                    Rival.name,
                    RivalRegionSnapshot.market_share_pct,
                )
                .join(Rival, Rival.id == RivalRegionSnapshot.rival_id)
                .where(RivalRegionSnapshot.snapshot_month == snap)
                .order_by(
                    RivalRegionSnapshot.region_iso,
                    RivalRegionSnapshot.market_share_pct.desc(),
                )
            )
        ).all()
        for iso, rival_name, share in rival_rows:
            # First row per ISO wins thanks to the DESC ordering above.
            top_rival_by_iso.setdefault(iso, (rival_name, share))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "snapshot_month",
            "iso_code",
            "name",
            "continent",
            "demand_index",
            "avg_booking_value",
            "top_rival",
            "top_rival_share_pct",
        ]
    )
    for snap_month, iso, name, continent, demand_index, avg_value in metric_rows:
        top_name, top_share = top_rival_by_iso.get(iso, ("", ""))
        writer.writerow(
            [
                snap_month.isoformat() if snap_month else "",
                iso,
                name,
                continent or "",
                demand_index if demand_index is not None else "",
                f"{avg_value:.2f}" if avg_value is not None else "",
                top_name,
                f"{top_share:.2f}" if isinstance(top_share, (int, float)) else "",
            ]
        )

    filename = f"ota-export-{snap.isoformat() if snap else 'empty'}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

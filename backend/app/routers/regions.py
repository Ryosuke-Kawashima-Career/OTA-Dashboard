"""Regions router — serves country boundaries merged with the latest KPI snapshot."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Region, RegionMetrics, Rival, RivalRegionSnapshot
from app.snapshot import parse_snapshot_month, resolve_snapshot_month

# Continents whose summer peaks in Jan/Feb (Southern hemisphere). Anything else
# peaks in Jul/Aug. Used to synthesize a plausible 12-month demand curve from
# the single demand_index figure we currently seed per region.
SOUTHERN_CONTINENTS = {"Oceania", "South America"}

router = APIRouter(prefix="/api", tags=["regions"])

# Repo root → /data/geo/countries.simplified.geo.json
_GEOJSON_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "geo" / "countries.simplified.geo.json"
)


@lru_cache(maxsize=1)
def _load_boundaries() -> dict[str, Any]:
    """Load the country-boundaries GeoJSON once per process."""
    with _GEOJSON_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/snapshots")
async def list_snapshots(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return all distinct snapshot months in ``region_metrics``.

    Drives the time-period slider — the frontend uses ``months`` to know
    which years are available and ``latest`` for its default selection.
    """
    rows = (
        await db.execute(
            select(distinct(RegionMetrics.snapshot_month)).order_by(
                RegionMetrics.snapshot_month
            )
        )
    ).all()
    months = [row[0].isoformat() for row in rows if row[0] is not None]
    return {
        "months": months,
        "latest": months[-1] if months else None,
    }


@router.get("/regions")
async def list_regions(
    db: AsyncSession = Depends(get_db),
    snapshot_month: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection of country boundaries enriched with
    the requested KPI snapshot (or the latest if ``snapshot_month`` is omitted)
    and continent metadata.

    Countries without seeded metrics still appear in the collection with null
    KPI values, so the frontend can render the full base map and only
    color-code the subset that has data.
    """
    boundaries = _load_boundaries()
    snap = await resolve_snapshot_month(db, parse_snapshot_month(snapshot_month))

    # Region metadata keyed by iso_code
    region_rows = (await db.execute(select(Region.iso_code, Region.name, Region.continent))).all()
    region_meta: dict[str, dict[str, str | None]] = {
        iso: {"name": name, "continent": continent} for iso, name, continent in region_rows
    }

    kpi_by_iso: dict[str, dict[str, Any]] = {}
    if snap is not None:
        metrics_rows = (
            await db.execute(
                select(
                    RegionMetrics.region_iso,
                    RegionMetrics.demand_index,
                    RegionMetrics.avg_booking_value,
                    RegionMetrics.snapshot_month,
                ).where(RegionMetrics.snapshot_month == snap)
            )
        ).all()
        kpi_by_iso = {
            iso: {
                "demand_index": demand_index,
                "avg_booking_value": avg_booking_value,
                "snapshot_month": snapshot_month.isoformat() if snapshot_month else None,
            }
            for iso, demand_index, avg_booking_value, snapshot_month in metrics_rows
        }

    features: list[dict[str, Any]] = []
    for feat in boundaries["features"]:
        iso = feat["properties"].get("iso_code")
        if not iso:
            continue
        db_meta = region_meta.get(iso, {})
        kpis = kpi_by_iso.get(iso, {})
        properties = {
            "iso_code": iso,
            "name": db_meta.get("name") or feat["properties"].get("name"),
            "continent": db_meta.get("continent"),
            "demand_index": kpis.get("demand_index"),
            "avg_booking_value": kpis.get("avg_booking_value"),
            "snapshot_month": kpis.get("snapshot_month"),
        }
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": feat["geometry"],
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "snapshot_month": snap.isoformat() if snap else None,
    }


def _synthesize_monthly_demand(demand_index: int | None, continent: str | None) -> list[dict[str, Any]]:
    """Synthesize a 12-month seasonal demand curve from a single `demand_index`.

    Formula: `value = demand_index * (1 + 0.3 * cos(2π (month - peak) / 12))`.
    `cos` peaks at 1 when `month == peak_month`. Northern-hemisphere regions
    peak in July; Southern-hemisphere regions peak in January. This gives a
    plausible seasonality for the Phase-3 chart without requiring us to
    ingest a real monthly series yet.
    """
    if demand_index is None:
        return []
    peak_month = 1 if (continent or "") in SOUTHERN_CONTINENTS else 7
    series: list[dict[str, Any]] = []
    for month in range(1, 13):
        seasonality = math.cos(2 * math.pi * (month - peak_month) / 12)
        value = round(demand_index * (1 + 0.3 * seasonality), 1)
        series.append({"month": month, "value": value})
    return series


@router.get("/regions/{iso_code}")
async def get_region_detail(
    iso_code: str,
    db: AsyncSession = Depends(get_db),
    snapshot_month: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return the detailed regional characteristics for a single country.

    Accepts an optional ``?snapshot_month=YYYY-MM-DD`` query param. When
    omitted the latest snapshot present in the DB is used. Each rival in
    the ranking is annotated with its **global rank** for the same month
    so the panel can show "Local #2 / Global #1" without a second request.

    Shape:
        {
          iso_code, name, continent,
          demand_index, avg_booking_value, snapshot_month,
          monthly_demand: [{month: 1..12, value: float}, ...],
          top_routes:     [{route, share_pct}, ...],
          demographics:   [{segment, share_pct}, ...],
          rival_ranking:  [{rival_id, name, categories, market_share_pct,
                            booking_volume, global_rank}, ...]
        }
    """
    iso = iso_code.upper()
    snap = await resolve_snapshot_month(db, parse_snapshot_month(snapshot_month))

    region = (
        await db.execute(select(Region).where(Region.iso_code == iso))
    ).scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail=f"Region {iso!r} not found")

    # region_metrics row for this region at the requested snapshot
    metrics = None
    if snap is not None:
        metrics = (
            await db.execute(
                select(RegionMetrics)
                .where(RegionMetrics.region_iso == iso)
                .where(RegionMetrics.snapshot_month == snap)
                .limit(1)
            )
        ).scalar_one_or_none()

    demand_index = metrics.demand_index if metrics else None
    avg_booking_value = metrics.avg_booking_value if metrics else None
    snapshot_month_iso = (
        metrics.snapshot_month.isoformat() if metrics and metrics.snapshot_month
        else (snap.isoformat() if snap else None)
    )
    top_routes = list(metrics.top_routes) if (metrics and metrics.top_routes) else []
    demographics = list(metrics.demographics) if (metrics and metrics.demographics) else []

    # Global ranking for the requested snapshot — rank rivals worldwide by
    # total booking_volume across all regions. Used to annotate each row of
    # the regional ranking with a `global_rank` field.
    global_rank_by_id: dict[str, int] = {}
    if snap is not None:
        global_rows = (
            await db.execute(
                select(
                    Rival.id,
                    func.sum(RivalRegionSnapshot.booking_volume).label("total_volume"),
                )
                .join(RivalRegionSnapshot, RivalRegionSnapshot.rival_id == Rival.id)
                .where(RivalRegionSnapshot.snapshot_month == snap)
                .group_by(Rival.id)
                .order_by(func.sum(RivalRegionSnapshot.booking_volume).desc())
            )
        ).all()
        global_rank_by_id = {str(rid): idx + 1 for idx, (rid, _) in enumerate(global_rows)}

    # Rival ranking by market share for this region at the requested snapshot
    ranking_rows = []
    if snap is not None:
        ranking_rows = (
            await db.execute(
                select(
                    Rival.id,
                    Rival.name,
                    Rival.categories,
                    RivalRegionSnapshot.market_share_pct,
                    RivalRegionSnapshot.booking_volume,
                )
                .join(RivalRegionSnapshot, RivalRegionSnapshot.rival_id == Rival.id)
                .where(RivalRegionSnapshot.region_iso == iso)
                .where(RivalRegionSnapshot.snapshot_month == snap)
                .order_by(RivalRegionSnapshot.market_share_pct.desc())
            )
        ).all()
    rival_ranking = [
        {
            "rival_id": str(rid),
            "name": name,
            "categories": list(categories or []),
            "market_share_pct": share,
            "booking_volume": volume,
            "global_rank": global_rank_by_id.get(str(rid)),
        }
        for rid, name, categories, share, volume in ranking_rows
    ]

    return {
        "iso_code": region.iso_code,
        "name": region.name,
        "continent": region.continent,
        "demand_index": demand_index,
        "avg_booking_value": avg_booking_value,
        "snapshot_month": snapshot_month_iso,
        "monthly_demand": _synthesize_monthly_demand(demand_index, region.continent),
        "top_routes": top_routes,
        "demographics": demographics,
        "rival_ranking": rival_ranking,
    }

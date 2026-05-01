"""Rivals router — serves the rival OTA roster with HQ coordinates and optional category filter."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Rival

router = APIRouter(prefix="/api", tags=["rivals"])

# HQ coordinates for the seeded rivals. Hardcoded here (rather than a DB
# migration) because the roster is small and the values are stable facts
# about each company's headquarter city.
HQ_COORDINATES: dict[str, tuple[float, float]] = {
    "Netherlands": (52.3676, 4.9041),       # Amsterdam
    "United States": (47.6062, -122.3321),  # Seattle (Expedia HQ)
    "China": (31.2304, 121.4737),           # Shanghai (Trip.com)
    "Singapore": (1.3521, 103.8198),
    "India": (28.4595, 77.0266),            # Gurugram (MakeMyTrip)
    "Czech Republic": (49.1951, 16.6068),   # Brno (Kiwi.com)
    "Sweden": (59.3293, 18.0686),           # Stockholm (Etraveli)
    "Spain": (41.3874, 2.1686),             # Barcelona (eDreams)
    "Germany": (50.9375, 6.9603),           # Cologne (HRS)
    "Indonesia": (-6.2088, 106.8456),       # Jakarta (Traveloka)
}

# Per-rival overrides for cases where multiple rivals share an HQ country and
# would otherwise stack on the same pin (e.g. three Spanish OTAs).
PER_RIVAL_COORDINATES: dict[str, tuple[float, float]] = {
    "Airbnb": (37.7749, -122.4194),       # San Francisco (vs Expedia/Seattle)
    "Amadeus": (40.4168, -3.7038),        # Madrid (vs eDreams/Barcelona)
    "Hotelbeds": (39.5696, 2.6502),       # Palma de Mallorca
    "TBO Tek": (28.5355, 77.3910),        # Noida (vs MakeMyTrip/Gurugram)
    "Riya Connect": (19.0760, 72.8777),   # Mumbai (vs MakeMyTrip)
}


@router.get("/rivals")
async def list_rivals(
    db: AsyncSession = Depends(get_db),
    category: list[str] | None = Query(default=None),
) -> dict[str, Any]:
    """Return the rival roster with HQ coordinates.

    Optionally filter by one or more `category` query params (e.g.
    `?category=B2C&category=B2B`). The match is an *array overlap*, so a
    rival categorised as `["B2C", "B2B"]` matches either query value.
    Unknown categories simply match nothing.
    """
    stmt = select(Rival).order_by(Rival.name)
    if category:
        stmt = stmt.where(Rival.categories.overlap(category))

    rows = (await db.execute(stmt)).scalars().all()

    rivals: list[dict[str, Any]] = []
    for r in rows:
        lat_lng = PER_RIVAL_COORDINATES.get(r.name) or HQ_COORDINATES.get(r.hq_country)
        if lat_lng is None:
            # Skip rivals whose HQ country has no mapped coordinates rather than
            # emitting a null point that would break the map layer.
            continue
        rivals.append(
            {
                "id": str(r.id),
                "name": r.name,
                "hq_country": r.hq_country,
                "categories": list(r.categories or []),
                "business_model": r.business_model,
                "ai_strategy": r.ai_strategy,
                "website": r.website,
                "lat": lat_lng[0],
                "lng": lat_lng[1],
            }
        )

    return {"rivals": rivals, "count": len(rivals)}

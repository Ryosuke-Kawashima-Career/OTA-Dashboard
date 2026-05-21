import uuid
from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class Region(Base):
    __tablename__ = "regions"

    iso_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    boundary: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    continent: Mapped[str] = mapped_column(String(50), nullable=True)


class RegionMetrics(Base):
    __tablename__ = "region_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_iso: Mapped[str] = mapped_column(String(10), nullable=False)
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False)
    avg_booking_value: Mapped[float] = mapped_column(Float, nullable=True)
    demand_index: Mapped[int] = mapped_column(Integer, nullable=True)
    top_routes: Mapped[object] = mapped_column(JSONB, nullable=True)
    demographics: Mapped[object] = mapped_column(JSONB, nullable=True)
    # Phase 7b — curated-data fields (migration 0008). `year` is the
    # native granularity of the curated data; `snapshot_month` stays
    # populated as date(year, 1, 1) so existing endpoints don't break.
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seasonality_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True
    )

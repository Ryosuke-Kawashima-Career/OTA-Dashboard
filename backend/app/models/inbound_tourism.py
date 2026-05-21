import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class InboundTourism(Base):
    """Per-region annual inbound tourism statistics (FR-08.1 macro context).

    Feeds the "Inbound Tourist Arrivals" KPI from the Market Health tier
    of the KPI Catalog. Sourced from national tourism boards (NTTO,
    JNTO, INE, ISTAT, ABS, BPS, KTO, etc.) with World Bank / UNWTO as
    fallback for smaller markets.

    Separated from `market_growth` because tourism receipts measure
    total visitor spend (across hotels, flights, retail, food) while
    `market_growth` measures the OTA-addressable slice of that spend.
    """

    __tablename__ = "inbound_tourism"
    __table_args__ = (
        UniqueConstraint(
            "region_iso",
            "year",
            "source_id",
            name="uq_inbound_tourism_region_year_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_iso: Mapped[str] = mapped_column(
        String(10), ForeignKey("regions.iso_code"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    international_arrivals_thousands: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tourism_receipts_usd_millions: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )

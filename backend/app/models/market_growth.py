import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class MarketGrowth(Base):
    """Regional Total Addressable Market (TAM) + growth rate per year.

    Feeds the Market Growth Rate, TAM, and the denominator for
    MarketShareEstimate (FR-08.1). Multiple rows per (region, year) are
    permitted because two publishers may disagree — the dashboard chooses
    the highest-trust source per region at query time, but every row is
    retained for the View Source modal.
    """

    __tablename__ = "market_growth"
    __table_args__ = (
        UniqueConstraint(
            "region_iso", "year", "source_id", name="uq_market_growth_region_year_source"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_iso: Mapped[str] = mapped_column(
        String(10), ForeignKey("regions.iso_code"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    market_size_usd: Mapped[float] = mapped_column(Float, nullable=False)
    growth_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )

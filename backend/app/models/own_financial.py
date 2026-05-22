import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class OwnRegionalFinancial(Base):
    """Our company's per-region financials.

    Feeds the Self vs. Market Benchmark (FR-04b) on the "know yourself"
    side. Source rows typically come from internal IR filings, board
    decks, or finance system exports — each one still requires a
    `source_id` for consistency with the provenance contract.
    """

    __tablename__ = "own_regional_financial"
    __table_args__ = (
        UniqueConstraint(
            "region_iso",
            "period_end",
            "source_id",
            name="uq_own_regional_financial_region_period_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_iso: Mapped[str] = mapped_column(
        String(10), ForeignKey("regions.iso_code"), nullable=False, index=True
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    revenue_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_bookings_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )

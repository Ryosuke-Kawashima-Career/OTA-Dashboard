import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class MarketShareEstimate(Base):
    """Per-rival per-region market share, disclosed or derived (FR-08.4).

    When a rival publicly reports its regional share we store the
    disclosed value with `is_estimated=False`. When the share has to be
    derived (rival_total_revenue × regional_revenue_weight ÷ regional
    market size), we store the result with `is_estimated=True` and
    record the formula in `calculation_method` so the View Source modal
    can show the user exactly how the number was computed.
    """

    __tablename__ = "market_share_estimate"
    __table_args__ = (
        UniqueConstraint(
            "rival_id",
            "region_iso",
            "period_end",
            "source_id",
            name="uq_market_share_estimate_rival_region_period_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rival_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rivals.id"), nullable=False, index=True
    )
    region_iso: Mapped[str] = mapped_column(
        String(10), ForeignKey("regions.iso_code"), nullable=False, index=True
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    share_pct: Mapped[float] = mapped_column(Float, nullable=False)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    calculation_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )

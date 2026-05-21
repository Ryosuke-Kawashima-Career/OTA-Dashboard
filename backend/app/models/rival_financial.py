import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class RivalFinancial(Base):
    """Rival financial fact row — one per (rival, period_end, period_type, source).

    Sourced from SEC EDGAR, HKEX, IR pages, and PDF reports via the
    ingestion adapters (FR-08.2). `segment_breakdown` holds the rival's
    region or product split when disclosed — used by the market share
    estimator (FR-08.4) to derive per-region shares when a rival does not
    disclose them directly.
    """

    __tablename__ = "rival_financial"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rival_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rivals.id"), nullable=False, index=True
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    revenue_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_bookings_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    room_nights: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_customers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_breakdown: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )
    # Phase 7b — curated-data audit pair (migration 0008).
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

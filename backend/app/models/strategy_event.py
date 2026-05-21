import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class StrategyEvent(Base):
    """A material strategic event published by a rival (FR-08.3).

    Examples: M&A announcements, AI partnership news, pricing strategy
    shifts, region launches. Populated by the daily_press flow which
    runs an LLM extractor over RSS, blog, and press release feeds. The
    `category` discriminates the chart-grouping (AI, pricing, M&A,
    partnership, region-launch, etc.).
    """

    __tablename__ = "strategy_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rival_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rivals.id"), nullable=False
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # `title` is the curated CSV's short headline; `summary` carries the
    # longer description. Either field can be displayed depending on
    # the surface (Rival Strategy Card vs. timeline tooltip).
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )


class AIFeature(Base):
    """A single AI-driven feature launch by a rival.

    Powers the AI Velocity KPI (count of launches in trailing 12 months
    per rival) and the AI Capability Gap analysis in the Strategy
    Synthesis layer (Phase 14). Each row must cite the public source
    that announced the launch.
    """

    __tablename__ = "ai_feature"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rival_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rivals.id"), nullable=False
    )
    launch_date: Mapped[date] = mapped_column(Date, nullable=False)
    feature_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 7b — feature category (migration 0008). Used by the Phase 14
    # AI Capability Gap synthesis to compare our coverage against rivals'.
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="Other AI")
    # Phase 7b — curated-data audit pair (migration 0008).
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )

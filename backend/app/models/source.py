import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class Source(Base):
    """Central provenance registry per FR-08.6.

    Every v2 fact-table row (market_growth, rival_financial,
    own_regional_financial, market_share_estimate, strategy_event,
    ai_feature, job_posting_snapshot) carries a source_id FK into this
    table, so any figure shown on the dashboard can be traced back to a
    public source.

    `source_type` discriminates the adapter that produced the row, e.g.
    "sec_edgar", "hkex", "ir_page", "rss", "career_site", "unwto",
    "world_bank", "industry_research", or "seed" for the internal seed
    data carried over from Phases 0–5.
    """

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("url", "content_hash", name="uq_sources_url_content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

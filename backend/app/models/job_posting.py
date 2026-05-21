import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class JobPostingSnapshot(Base):
    """Weekly rival career-site snapshot — leading indicator (FR-08.3).

    `ml_eng_count / total_open_roles` becomes the AI Investment Index in
    the Competitive Intelligence KPI tier. A sustained rise here usually
    precedes an AI-feature launch (caught by the AI Velocity KPI) by
    several quarters.
    """

    __tablename__ = "job_posting_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rival_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rivals.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    ml_eng_count: Mapped[int] = mapped_column(Integer, nullable=False)
    data_eng_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_open_roles: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )

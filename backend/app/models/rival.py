import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.base import Base


class Rival(Base):
    __tablename__ = "rivals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    hq_country: Mapped[str] = mapped_column(String(100), nullable=True)
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default="{}"
    )
    business_model: Mapped[str] = mapped_column(Text, nullable=True)
    ai_strategy: Mapped[str] = mapped_column(Text, nullable=True)
    website: Mapped[str] = mapped_column(String(255), nullable=True)


class RivalRegionSnapshot(Base):
    __tablename__ = "rival_region_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rival_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rivals.id"), nullable=False)
    region_iso: Mapped[str] = mapped_column(String(10), ForeignKey("regions.iso_code"), nullable=False)
    market_share_pct: Mapped[float] = mapped_column(Float, nullable=True)
    booking_volume: Mapped[int] = mapped_column(Integer, nullable=True)
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False)

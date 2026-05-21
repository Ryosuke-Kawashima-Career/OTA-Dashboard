"""Market share estimate table (FR-08.4).

Stores per-rival per-region per-period market share, distinguishing
disclosed values (is_estimated=False) from derived ones
(is_estimated=True with the formula in calculation_method). The partial
index on is_estimated=true keeps the View Source modal fast when it
filters for rows that need the "estimated" badge.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_share_estimate",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "rival_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rivals.id"),
            nullable=False,
        ),
        sa.Column(
            "region_iso", sa.String(10), sa.ForeignKey("regions.iso_code"), nullable=False
        ),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("share_pct", sa.Float, nullable=False),
        sa.Column("is_estimated", sa.Boolean, nullable=False),
        sa.Column("calculation_method", sa.Text, nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "rival_id",
            "region_iso",
            "period_end",
            "source_id",
            name="uq_market_share_estimate_rival_region_period_source",
        ),
    )
    op.create_index(
        "ix_market_share_estimate_rival_region_period",
        "market_share_estimate",
        ["rival_id", "region_iso", "period_end"],
    )
    op.create_index(
        "ix_market_share_estimate_is_estimated",
        "market_share_estimate",
        ["is_estimated"],
        postgresql_where=sa.text("is_estimated = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_share_estimate_is_estimated", table_name="market_share_estimate"
    )
    op.drop_index(
        "ix_market_share_estimate_rival_region_period", table_name="market_share_estimate"
    )
    op.drop_table("market_share_estimate")

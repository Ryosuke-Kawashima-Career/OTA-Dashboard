"""Market growth + rival/own financial fact tables (FR-08.1, FR-08.2).

Adds the three provenance-backed fact tables that feed the v2 KPIs:

- market_growth: regional TAM + growth rate (one row per region/year/source)
- rival_financial: per-period rival financials extracted from IR filings
- own_regional_financial: our company's per-region financials for the
  "know yourself" side of the Self vs. Market Benchmark.

Every row carries a NOT NULL source_id FK into the sources table created
in 0003. Deleting a source is blocked by the FK (default RESTRICT) so the
warehouse can never silently lose its provenance trail.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_growth",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "region_iso", sa.String(10), sa.ForeignKey("regions.iso_code"), nullable=False
        ),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("market_size_usd", sa.Float, nullable=False),
        sa.Column("growth_rate_pct", sa.Float, nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "region_iso", "year", "source_id", name="uq_market_growth_region_year_source"
        ),
    )
    op.create_index("ix_market_growth_region_year", "market_growth", ["region_iso", "year"])

    op.create_table(
        "rival_financial",
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
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("revenue_usd", sa.Float, nullable=True),
        sa.Column("gross_bookings_usd", sa.Float, nullable=True),
        sa.Column("take_rate_pct", sa.Float, nullable=True),
        sa.Column("operating_margin_pct", sa.Float, nullable=True),
        sa.Column("room_nights", sa.Integer, nullable=True),
        sa.Column("active_customers", sa.Integer, nullable=True),
        sa.Column("segment_breakdown", postgresql.JSONB, nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_rival_financial_rival_period",
        "rival_financial",
        ["rival_id", "period_end"],
    )

    op.create_table(
        "own_regional_financial",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "region_iso", sa.String(10), sa.ForeignKey("regions.iso_code"), nullable=False
        ),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("revenue_usd", sa.Float, nullable=True),
        sa.Column("gross_bookings_usd", sa.Float, nullable=True),
        sa.Column("take_rate_pct", sa.Float, nullable=True),
        sa.Column("operating_margin_pct", sa.Float, nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_own_regional_financial_region_period",
        "own_regional_financial",
        ["region_iso", "period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_own_regional_financial_region_period", table_name="own_regional_financial"
    )
    op.drop_table("own_regional_financial")
    op.drop_index("ix_rival_financial_rival_period", table_name="rival_financial")
    op.drop_table("rival_financial")
    op.drop_index("ix_market_growth_region_year", table_name="market_growth")
    op.drop_table("market_growth")

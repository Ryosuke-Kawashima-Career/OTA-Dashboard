"""Schema reconciliation for curated real-world data (T-7b.1, FR-08).

The hand-curated datasets under data/*.csv carry fields the Phase 6 schema
didn't anticipate: rival HQ ISO codes + parent companies, per-row
is_estimated flags + free-text notes, region seasonality, AI-feature
categories, separate inbound-tourism arrivals/receipts, and event titles.
This migration closes those gaps so seed.py (and future ingestion adapters)
can write the curated rows verbatim without lossy conversion.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that gain (is_estimated, notes) — the curated-data audit pair.
_FACT_TABLES = ("market_growth", "rival_financial", "ai_feature")


def upgrade() -> None:
    # ── rivals: real metadata (parent + hq_iso) ──────────────────────
    op.add_column("rivals", sa.Column("parent", sa.String(100), nullable=True))
    op.add_column("rivals", sa.Column("hq_iso", sa.String(10), nullable=True))

    # ── (is_estimated, notes) pair on every curated fact table ───────
    # NOT NULL with DEFAULT false so existing Phase 6 rows backfill cleanly.
    for table in _FACT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "is_estimated",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        op.add_column(table, sa.Column("notes", sa.Text, nullable=True))

    # ── region_metrics: bring it into the v2 provenance contract ─────
    # The legacy table was monthly seed-only and carried no source_id.
    # Curated data is yearly with per-row attribution + seasonality.
    op.add_column("region_metrics", sa.Column("year", sa.Integer, nullable=True))
    op.add_column(
        "region_metrics", sa.Column("seasonality_index", sa.Float, nullable=True)
    )
    op.add_column(
        "region_metrics",
        sa.Column(
            "is_estimated",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("region_metrics", sa.Column("notes", sa.Text, nullable=True))
    op.add_column(
        "region_metrics",
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=True,  # nullable because legacy seed rows pre-date Source rows
        ),
    )

    # ── ai_feature: category drives the Phase 14 AI Capability Gap ───
    # Default 'Other AI' so backfilled Phase 6 rows (none exist yet, but
    # the migration must work even if any do) are still classifiable.
    op.add_column(
        "ai_feature",
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'Other AI'"),
        ),
    )

    # ── strategy_event: curated CSV has separate title + description ─
    # Phase 6 only had `summary`; we keep it and add `title` rather than
    # rename, so downstream readers can choose either field.
    op.add_column(
        "strategy_event",
        sa.Column("title", sa.String(255), nullable=True),
    )

    # ── New table: inbound_tourism (FR-08.1 macro context) ───────────
    op.create_table(
        "inbound_tourism",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "region_iso",
            sa.String(10),
            sa.ForeignKey("regions.iso_code"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("international_arrivals_thousands", sa.Integer, nullable=True),
        sa.Column("tourism_receipts_usd_millions", sa.Float, nullable=True),
        sa.Column(
            "is_estimated",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "region_iso", "year", "source_id", name="uq_inbound_tourism_region_year_source"
        ),
    )
    op.create_index(
        "ix_inbound_tourism_region_year", "inbound_tourism", ["region_iso", "year"]
    )


def downgrade() -> None:
    op.drop_index("ix_inbound_tourism_region_year", table_name="inbound_tourism")
    op.drop_table("inbound_tourism")

    op.drop_column("strategy_event", "title")
    op.drop_column("ai_feature", "category")

    op.drop_column("region_metrics", "source_id")
    op.drop_column("region_metrics", "notes")
    op.drop_column("region_metrics", "is_estimated")
    op.drop_column("region_metrics", "seasonality_index")
    op.drop_column("region_metrics", "year")

    for table in _FACT_TABLES:
        op.drop_column(table, "notes")
        op.drop_column(table, "is_estimated")

    op.drop_column("rivals", "hq_iso")
    op.drop_column("rivals", "parent")

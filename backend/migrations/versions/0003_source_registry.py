"""Source registry — central provenance table (FR-08.6).

Every v2 fact row (market_growth, rival_financial, own_regional_financial,
market_share_estimate, strategy_event, ai_feature, job_posting_snapshot)
will FK into this table so any number shown on the dashboard can be traced
back to its public source. The Phase 0–5 legacy tables (region_metrics,
rival_region_snapshots) remain untouched — they represent seed/transitional
data and are not required to carry source_ids.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload_ref", sa.String(1024), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("url", "content_hash", name="uq_sources_url_content_hash"),
    )
    op.create_index("ix_sources_source_type", "sources", ["source_type"])
    op.create_index("ix_sources_retrieved_at", "sources", ["retrieved_at"])


def downgrade() -> None:
    op.drop_index("ix_sources_retrieved_at", table_name="sources")
    op.drop_index("ix_sources_source_type", table_name="sources")
    op.drop_table("sources")

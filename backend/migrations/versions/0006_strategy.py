"""Strategy event, AI feature, and job posting snapshot tables (FR-08.3).

These three tables hold the LLM-extracted competitive intelligence
ingested by the daily_press and weekly_jobs flows. They share the same
provenance contract as the financial fact tables — every row carries a
source_id FK so each surfaced insight links back to its underlying
press release, blog post, or career page.

The composite indexes on (rival_id, event_date), (rival_id, launch_date),
and (rival_id, snapshot_date) keep the per-rival "recent items" queries
under the latency budget for the Rival Strategy Card.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_event",
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
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_strategy_event_rival_date", "strategy_event", ["rival_id", "event_date"]
    )

    op.create_table(
        "ai_feature",
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
        sa.Column("launch_date", sa.Date, nullable=False),
        sa.Column("feature_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ai_feature_rival_launch", "ai_feature", ["rival_id", "launch_date"]
    )

    op.create_table(
        "job_posting_snapshot",
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
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("ml_eng_count", sa.Integer, nullable=False),
        sa.Column("data_eng_count", sa.Integer, nullable=False),
        sa.Column("total_open_roles", sa.Integer, nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_job_posting_snapshot_rival_date",
        "job_posting_snapshot",
        ["rival_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_job_posting_snapshot_rival_date", table_name="job_posting_snapshot"
    )
    op.drop_table("job_posting_snapshot")
    op.drop_index("ix_ai_feature_rival_launch", table_name="ai_feature")
    op.drop_table("ai_feature")
    op.drop_index("ix_strategy_event_rival_date", table_name="strategy_event")
    op.drop_table("strategy_event")

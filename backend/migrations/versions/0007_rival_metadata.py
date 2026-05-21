"""Rival metadata expansion — ticker, exchange, strategy_summary, summary_updated_at.

Adds the v2 metadata columns to the rivals table. All four columns are
nullable so the existing 15 seed rows remain valid until the Phase 8
SEC EDGAR / HKEX / IR adapters and the Phase 9 LLM strategy summarizer
backfill them.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rivals", sa.Column("ticker", sa.String(length=20), nullable=True))
    op.add_column("rivals", sa.Column("exchange", sa.String(length=20), nullable=True))
    op.add_column("rivals", sa.Column("strategy_summary", sa.Text, nullable=True))
    op.add_column(
        "rivals",
        sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rivals", "summary_updated_at")
    op.drop_column("rivals", "strategy_summary")
    op.drop_column("rivals", "exchange")
    op.drop_column("rivals", "ticker")

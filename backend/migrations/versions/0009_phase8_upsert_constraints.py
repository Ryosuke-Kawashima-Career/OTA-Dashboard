"""Phase 8 — upsert-enabling unique constraints on financial fact tables.

The ingestion `upsert()` helper relies on Postgres `INSERT ... ON CONFLICT
(natural_key)` semantics, which only work when the natural key is backed
by a unique index. The Phase 6 schema declared a unique constraint on
``market_growth`` and ``market_share_estimate`` but left ``rival_financial``
and ``own_regional_financial`` without one, so adapter re-runs would
silently insert duplicate rows.

This migration adds the missing constraints so SEC EDGAR / HKEX / IR
adapters in Phase 8 can be safely re-run on the same period.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_rival_financial_rival_period_type_source",
        "rival_financial",
        ["rival_id", "period_end", "period_type", "source_id"],
    )
    op.create_unique_constraint(
        "uq_own_regional_financial_region_period_source",
        "own_regional_financial",
        ["region_iso", "period_end", "source_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_own_regional_financial_region_period_source",
        "own_regional_financial",
        type_="unique",
    )
    op.drop_constraint(
        "uq_rival_financial_rival_period_type_source",
        "rival_financial",
        type_="unique",
    )

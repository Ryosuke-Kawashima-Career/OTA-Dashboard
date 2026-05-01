"""Rival multi-category — replace single `category` VARCHAR with `categories` VARCHAR[].

Some OTAs operate as both B2C and B2B (e.g. Expedia / Expedia Partner Solutions,
Etraveli with its white-label arm, Traveloka with Traveloka for Business). A
single-value column can't represent that, so we promote it to a Postgres array.

Backfill rule: each existing row's prior `category` becomes the sole element of
its new `categories` array. NULL categories become an empty array.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rivals",
        sa.Column(
            "categories",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    op.execute(
        "UPDATE rivals SET categories = ARRAY[category] "
        "WHERE category IS NOT NULL AND category <> ''"
    )
    op.drop_column("rivals", "category")


def downgrade() -> None:
    op.add_column(
        "rivals",
        sa.Column("category", sa.String(length=50), nullable=True),
    )
    # Project the first array element back into the scalar column.
    op.execute("UPDATE rivals SET category = categories[1] WHERE array_length(categories, 1) >= 1")
    op.drop_column("rivals", "categories")

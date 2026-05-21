"""Idempotent upsert helper (T-7.6).

Every adapter eventually does the same thing: produce structured rows
keyed by some natural key (e.g. `(rival_id, period_end, source_id)`) and
ask the warehouse to insert-or-update. Centralising that into one helper
means:

  * Re-running a flow never produces duplicate fact rows.
  * The natural key shows up in code right next to the upsert call, so
    reviewers can sanity-check it against the migration's unique
    constraint.

The helper is built on Postgres `INSERT ... ON CONFLICT (...) DO UPDATE`
because that's the only correct concurrent-safe upsert primitive in
Postgres; emulating it in Python racing two workers would silently
double-insert.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import DeclarativeBase, Session


def _table_of(target: Table | type[DeclarativeBase]) -> Table:
    if isinstance(target, Table):
        return target
    # Mapped class — pull its underlying Table.
    return target.__table__  # type: ignore[attr-defined]


def upsert(
    session: Session,
    target: Table | type[DeclarativeBase],
    *,
    natural_key: Sequence[str],
    payload: Mapping[str, Any],
    update_on_conflict: bool = True,
) -> None:
    """Insert `payload` into `target`; on conflict over `natural_key`
    columns, either update the non-key columns (default) or do nothing.

    Args:
        session: live SQLAlchemy session — caller commits.
        target: a Table or a mapped model class.
        natural_key: column names forming the unique constraint.
        payload: column → value mapping; must include every column in
            `natural_key`.
        update_on_conflict: if True, non-key columns are refreshed on
            conflict (typical for fact rows that may be re-fetched with
            corrected values). If False, only the first insert wins
            (typical for `Source` rows where the canonical row should
            never be mutated by a later run).

    Returns nothing; raises if `payload` is missing a key column or if
    the database rejects the row.
    """
    natural_key = tuple(natural_key)
    missing = [k for k in natural_key if k not in payload]
    if missing:
        raise ValueError(
            f"upsert payload missing natural-key columns: {missing!r}"
        )

    table = _table_of(target)
    stmt = pg_insert(table).values(**payload)

    if update_on_conflict:
        # Refresh every non-key column with the new payload.
        non_key = [k for k in payload.keys() if k not in natural_key]
        if non_key:
            set_clause = {col: stmt.excluded[col] for col in non_key}
            stmt = stmt.on_conflict_do_update(
                index_elements=list(natural_key), set_=set_clause
            )
        else:
            # Payload was only the natural key — nothing to update.
            stmt = stmt.on_conflict_do_nothing(index_elements=list(natural_key))
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=list(natural_key))

    session.execute(stmt)

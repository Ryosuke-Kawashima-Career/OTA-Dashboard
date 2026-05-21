"""Provenance contract validator (T-6.6, FR-08.6).

Every v2 fact table must have NOT NULL source_id columns; this script
double-checks that constraint at runtime by counting rows with NULL
source_ids across each provenance-backed table. Even though the
migrations enforce NOT NULL at the database level, running this on
backend startup catches:

  * fact tables created with a missing source_id column entirely
  * data inserted via a path that bypasses the ORM constraint
  * seed scripts that forgot to attach the internal-seed source row

Exit codes:
  0 — every fact table is fully sourced (or empty)
  1 — at least one unsourced row exists; details printed to stderr

Run with:
    python -m scripts.validate_provenance
or:
    python backend/scripts/validate_provenance.py
"""
from __future__ import annotations

import os
import sys
from typing import Iterable

import psycopg2

# Tables that must carry a NOT NULL source_id under the v2 contract.
# Order matters only for readable output.
PROVENANCE_BACKED_TABLES: tuple[str, ...] = (
    "market_growth",
    "rival_financial",
    "own_regional_financial",
    "market_share_estimate",
    "strategy_event",
    "ai_feature",
    "job_posting_snapshot",
)


def _db_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://ota:ota_secret@localhost:5432/ota_worldmap",
    )


def _violations(cur, tables: Iterable[str]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for table in tables:
        # Defensive: a table that hasn't been migrated yet is allowed —
        # the validator should only flag rows that *exist* and are
        # missing a source_id, not refuse to run before Phase 6 lands.
        cur.execute(
            "SELECT to_regclass(%s) IS NOT NULL",
            (f"public.{table}",),
        )
        (exists,) = cur.fetchone()
        if not exists:
            continue
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE source_id IS NULL")
        (count,) = cur.fetchone()
        if count:
            out.append((table, count))
    return out


def main() -> int:
    conn = psycopg2.connect(_db_url())
    try:
        cur = conn.cursor()
        violations = _violations(cur, PROVENANCE_BACKED_TABLES)
        cur.close()
    finally:
        conn.close()

    if violations:
        print(
            "FAIL: provenance contract violated — rows exist without a source_id:",
            file=sys.stderr,
        )
        for table, count in violations:
            print(f"  - {table}: {count} unsourced row(s)", file=sys.stderr)
        print(
            "\nFix: backfill the missing source_ids or delete the offending rows.",
            file=sys.stderr,
        )
        return 1

    print("OK: every provenance-backed table is fully sourced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

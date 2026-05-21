"""T-7.3, T-7.5, T-7.6 acceptance: echo flow end-to-end against the live DB.

These tests require the `backend/` schema to be at head (Phase 6) and a
running Postgres reachable via `DATABASE_URL` (defaults to the
docker-compose `ota_db`). They write to `market_growth(region_iso='US',
year=1900, source_type='echo')` — a sentinel row that's easy to clean
up between tests.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import MarketGrowth, Source
from ingestion.adapters.echo import (
    ECHO_CONTENT_HASH_TAG,  # noqa: F401  used for documentation only
    ECHO_SOURCE_URL,
)
from ingestion.db import session_scope
from ingestion.flows.echo_flow import echo_flow
from ingestion.monitor.layout_change_detector import LayoutChangeDetector
from ingestion.raw_store import LocalRawPayloadStore


# Skip the whole module if the DB isn't reachable (e.g. CI without
# Postgres). Importing psycopg2 + connecting on-demand is cheaper than
# wiring a custom marker.
def _db_reachable() -> bool:
    try:
        with session_scope() as s:
            s.execute(select(1))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(), reason="No reachable Postgres for echo flow integration"
)


def _cleanup_echo_rows() -> None:
    """Wipe any echo-source rows + their derived facts so each test
    starts from a known baseline."""
    with session_scope() as s:
        s.execute(
            MarketGrowth.__table__.delete().where(
                MarketGrowth.year == 1900, MarketGrowth.region_iso == "US"
            )
        )
        s.execute(Source.__table__.delete().where(Source.source_type == "echo"))


@pytest.fixture(autouse=True)
def _cleanup_before_each():
    _cleanup_echo_rows()
    yield
    _cleanup_echo_rows()


def test_echo_flow_writes_one_source_and_one_fact(tmp_path):
    store = LocalRawPayloadStore(tmp_path / "raw")
    detector = LayoutChangeDetector(tmp_path / "fp")

    summary = echo_flow(raw_store=store, detector=detector)

    assert summary.status == "ok"
    assert summary.fact_rows_upserted == 1

    with session_scope() as s:
        sources = s.execute(select(Source).where(Source.source_type == "echo")).scalars().all()
        facts = s.execute(
            select(MarketGrowth).where(
                MarketGrowth.region_iso == "US", MarketGrowth.year == 1900
            )
        ).scalars().all()

    assert len(sources) == 1, "Exactly one SOURCE row from one echo run"
    assert len(facts) == 1, "Exactly one fact row, keyed on (region_iso, year, source_id)"
    assert facts[0].source_id == sources[0].id

    # Raw payload was actually written to the store.
    assert store.read(summary.raw_payload_ref).startswith(b"<!doctype html>")


def test_echo_flow_is_idempotent(tmp_path):
    """Re-running the flow must NOT duplicate rows — that's the whole
    point of the upsert helper + content-addressed source recorder.
    """
    store = LocalRawPayloadStore(tmp_path / "raw")
    detector = LayoutChangeDetector(tmp_path / "fp")

    first = echo_flow(raw_store=store, detector=detector)
    second = echo_flow(raw_store=store, detector=detector)

    assert first.source_id == second.source_id, "Same SOURCE row on re-run"

    with session_scope() as s:
        source_count = s.execute(
            select(Source).where(Source.source_type == "echo")
        ).scalars().all()
        fact_count = s.execute(
            select(MarketGrowth).where(
                MarketGrowth.region_iso == "US", MarketGrowth.year == 1900
            )
        ).scalars().all()

    assert len(source_count) == 1
    assert len(fact_count) == 1


def test_echo_flow_skips_upsert_on_layout_drift(tmp_path):
    """Pre-seed the detector with a 5-fingerprint window that does NOT
    contain the fixture's real fingerprint, so the next run looks like
    drift and must short-circuit.
    """
    store = LocalRawPayloadStore(tmp_path / "raw")
    detector = LayoutChangeDetector(tmp_path / "fp")
    for fp in ("fake-1", "fake-2", "fake-3", "fake-4", "fake-5"):
        detector.accept(ECHO_SOURCE_URL, fp)

    summary = echo_flow(raw_store=store, detector=detector)

    assert summary.status == "skipped_layout_drift"
    assert summary.fact_rows_upserted == 0
    # Raw payload is still persisted (FR-08.5 retention) so a human can
    # diff the new bytes against the prior accepted run.
    assert summary.raw_payload_ref is not None

    with session_scope() as s:
        sources = s.execute(select(Source).where(Source.source_type == "echo")).scalars().all()
        facts = s.execute(
            select(MarketGrowth).where(
                MarketGrowth.region_iso == "US", MarketGrowth.year == 1900
            )
        ).scalars().all()

    assert sources == [], "Drift must skip the SOURCE upsert"
    assert facts == [], "Drift must skip the fact upsert"

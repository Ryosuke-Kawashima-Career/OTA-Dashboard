"""T-7.2 acceptance: round-trip a payload, verify key layout, verify idempotency."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ingestion.raw_store import LocalRawPayloadStore


def test_write_then_read_round_trip(tmp_path):
    store = LocalRawPayloadStore(tmp_path)
    payload = b"<html>hello</html>"
    when = datetime(2026, 5, 21, tzinfo=timezone.utc)

    ref = store.write(payload, source_type="echo", retrieved_at=when)

    assert store.read(ref) == payload


def test_key_layout_matches_spec(tmp_path):
    store = LocalRawPayloadStore(tmp_path)
    when = datetime(2026, 5, 21, tzinfo=timezone.utc)

    ref = store.write(b"hi", source_type="sec_edgar", retrieved_at=when)

    # spec: <source_type>/<yyyy>/<mm>/<sha256>.bin
    assert re.fullmatch(r"sec_edgar/2026/05/[0-9a-f]{64}\.bin", ref)


def test_write_is_content_addressed_and_idempotent(tmp_path):
    store = LocalRawPayloadStore(tmp_path)
    when = datetime(2026, 5, 21, tzinfo=timezone.utc)

    ref_a = store.write(b"same", source_type="echo", retrieved_at=when)
    ref_b = store.write(b"same", source_type="echo", retrieved_at=when)

    # Identical payload + month bucket → identical key, no duplicate file.
    assert ref_a == ref_b
    assert len(list((tmp_path / "echo").rglob("*.bin"))) == 1


def test_different_payloads_get_different_keys(tmp_path):
    store = LocalRawPayloadStore(tmp_path)
    when = datetime(2026, 5, 21, tzinfo=timezone.utc)

    ref_a = store.write(b"alpha", source_type="echo", retrieved_at=when)
    ref_b = store.write(b"beta", source_type="echo", retrieved_at=when)

    assert ref_a != ref_b

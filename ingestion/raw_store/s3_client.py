"""Raw payload store (T-7.2, FR-08.5).

Every fetched HTML/PDF/XBRL payload is persisted *before* any parsing so
the pipeline can:

  1. Reprocess after an extractor bug fix without re-fetching the source.
  2. Audit "why does the warehouse think Booking earned $X?" by pulling up
     the exact bytes the extractor saw.

The key layout — `<source_type>/<yyyy>/<mm>/<sha256>.bin` — buckets by
source class and year-month so S3 lifecycle rules can be scoped per
source if retention requirements ever diverge. Content-addressed naming
(SHA-256) makes the store idempotent for free: writing the same payload
twice produces the same key, so no duplicate object is created.

Two backends are provided:

* `LocalRawPayloadStore` — dev/test default, writes to the local filesystem.
* `S3RawPayloadStore` — production, wraps boto3 with a 24-month lifecycle
  policy (configured out-of-band on the bucket).

Both share the `RawPayloadStore` contract so flows can be written against
the interface and the backend chosen via `default_raw_store()`.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


def _content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _key_for(source_type: str, retrieved_at: datetime, payload: bytes) -> str:
    return f"{source_type}/{retrieved_at:%Y/%m}/{_content_hash(payload)}.bin"


@runtime_checkable
class RawPayloadStore(Protocol):
    """Minimal interface every backend must implement."""

    def write(self, payload: bytes, *, source_type: str, retrieved_at: datetime) -> str:
        """Persist `payload`; return the storage reference (key/path)."""
        ...

    def read(self, ref: str) -> bytes:
        """Read back a payload previously written under `ref`."""
        ...


class LocalRawPayloadStore:
    """Filesystem-backed store for development and tests.

    Layout under `root` mirrors the production S3 layout exactly so a
    flow's behaviour is identical whether it runs against local disk or
    real S3 — only the `default_raw_store()` factory differs.
    """

    def __init__(self, root: str | Path):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def write(self, payload: bytes, *, source_type: str, retrieved_at: datetime) -> str:
        key = _key_for(source_type, retrieved_at, payload)
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        # Content-addressed → identical payload yields identical key, so
        # this is idempotent. Re-write is harmless.
        path.write_bytes(payload)
        return key

    def read(self, ref: str) -> bytes:
        return (self._root / ref).read_bytes()

    def exists(self, ref: str) -> bool:
        return (self._root / ref).is_file()


class S3RawPayloadStore:
    """Production-bound store. Lifecycle (24 months) is configured on the
    bucket — this class is intentionally minimal so it has nothing to
    mock in unit tests beyond a fake boto3 client.
    """

    def __init__(self, bucket: str, *, client=None):
        self._bucket = bucket
        if client is None:
            import boto3  # imported lazily so dev/test doesn't need boto3

            client = boto3.client("s3")
        self._client = client

    def write(self, payload: bytes, *, source_type: str, retrieved_at: datetime) -> str:
        key = _key_for(source_type, retrieved_at, payload)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=payload)
        return key

    def read(self, ref: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=ref)
        return resp["Body"].read()


def default_raw_store() -> RawPayloadStore:
    """Pick a backend based on env vars.

    `RAW_STORE_BACKEND=s3 RAW_STORE_BUCKET=ota-raw` → S3.
    Anything else (the dev default) → local filesystem rooted at
    `RAW_STORE_LOCAL_ROOT` or `./raw_store_data`.
    """
    backend = os.getenv("RAW_STORE_BACKEND", "local").lower()
    if backend == "s3":
        bucket = os.environ["RAW_STORE_BUCKET"]
        return S3RawPayloadStore(bucket)
    root = os.getenv("RAW_STORE_LOCAL_ROOT", "raw_store_data")
    return LocalRawPayloadStore(root)

"""Sync SQLAlchemy session factory for ingestion flows.

The backend exposes an async engine for the FastAPI request path. Ingestion
flows are batch jobs running under Prefect — a sync engine is simpler, plays
well with the seed script's psycopg2 driver, and avoids dragging asyncio
machinery into every adapter.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_DEFAULT_URL = "postgresql+psycopg2://ota:ota_secret@localhost:5432/ota_worldmap"


def _sync_database_url() -> str:
    url = os.getenv("DATABASE_URL", _DEFAULT_URL)
    # `psycopg2.connect()`-style URLs ("postgresql://...") work with
    # SQLAlchemy's default psycopg2 driver too, so we normalise rather
    # than reject them.
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(_sync_database_url(), future=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """`with session_scope() as s:` — commits on success, rolls back on error."""
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

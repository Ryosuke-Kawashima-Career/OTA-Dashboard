"""Shared fixture-mode helpers for rival-financial adapters.

SEC EDGAR (``sec_edgar.py``), HKEX (``hkex.py``), and the generic IR-page
adapter (``ir_page.py`` / ``pdf_report.py``) all share the same offline
regression baseline: ``data/rivals/rival_financials.csv``. Each adapter
just owns a different *slice* of that CSV — SEC EDGAR claims the rows
where ``source_url`` is on ``sec.gov``, HKEX the ``hkexnews.hk`` rows,
and so on.

Centralising the CSV reader + the ``FactRow`` shape keeps the per-source
adapter modules thin: they pick a filter, hand it to ``iter_filings()``,
and let ``run_adapter()`` do the rest.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Optional

from app.models import RivalFinancial
from ingestion.adapters._base import (
    AdapterExtraction,
    FactRow,
    FetchResult,
    build_csv_fixture_payload,
)


_DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "rivals" / "rival_financials.csv"
)


def _read_financials_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append(
                {
                    "rival_id": raw["rival_id"],
                    "rival_name": raw["rival_name"],
                    "fiscal_year": int(raw["fiscal_year"]),
                    "revenue_usd_millions": _opt_float(raw["revenue_usd_millions"]),
                    "gross_bookings_usd_millions": _opt_float(
                        raw["gross_bookings_usd_millions"]
                    ),
                    "take_rate_pct": _opt_float(raw["take_rate_pct"]),
                    "operating_margin_pct": _opt_float(raw["operating_margin_pct"]),
                    "active_customers_millions": _opt_float(
                        raw["active_customers_millions"]
                    ),
                    "room_nights_millions": _opt_float(raw["room_nights_millions"]),
                    "segment_breakdown": (
                        json.loads(raw["segment_breakdown"])
                        if raw["segment_breakdown"]
                        else None
                    ),
                    "is_estimated": raw["is_estimated"].strip().lower() == "true",
                    "notes": raw["notes"] or None,
                    "source_url": raw["source_url"],
                }
            )
    return rows


def _opt_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    return float(s)


def iter_filings(
    *,
    url_predicate: Callable[[str], bool],
    fixture_path: Optional[Path] = None,
) -> Iterator[tuple[str, list[dict]]]:
    """Yield ``(canonical_url, rows)`` per distinct source URL passing ``url_predicate``.

    Grouping per URL — instead of per rival — means each
    SEC filing / earnings PDF produces exactly one ``sources`` row, which
    is the granularity the View Source modal needs to deep-link the user
    to the underlying filing.
    """
    fixture = fixture_path or _DEFAULT_FIXTURE_PATH
    rows = _read_financials_csv(fixture)
    by_url: dict[str, list[dict]] = {}
    for r in rows:
        if not url_predicate(r["source_url"]):
            continue
        by_url.setdefault(r["source_url"], []).append(r)
    for url, group in by_url.items():
        yield url, group


def build_fetch_result(
    *,
    publisher: str,
    url: str,
    rows: Iterable[Mapping],
    fixture_path: Optional[Path] = None,
) -> FetchResult:
    fixture = fixture_path or _DEFAULT_FIXTURE_PATH
    payload = build_csv_fixture_payload(
        publisher=publisher,
        fixture_path=str(fixture.relative_to(fixture.parents[2])),
        rows=list(rows),
    )
    return FetchResult(
        url=url,
        payload=payload,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def extract_financials(payload: bytes) -> AdapterExtraction:
    """Decode fixture-mode JSON into ``RivalFinancial`` rows."""
    text = payload.decode("utf-8", errors="replace")
    if not text.lstrip().startswith("{"):
        return AdapterExtraction(
            payload=payload,
            retrieved_at=datetime.now(timezone.utc),
            fact_rows=(),
        )
    doc = json.loads(text)
    fact_rows: list[FactRow] = []
    for r in doc.get("rows", []):
        rev_m = r.get("revenue_usd_millions")
        gb_m = r.get("gross_bookings_usd_millions")
        ac_m = r.get("active_customers_millions")
        rn_m = r.get("room_nights_millions")
        fact_rows.append(
            FactRow(
                target=RivalFinancial,
                natural_key=("rival_id", "period_end", "period_type", "source_id"),
                payload={
                    "rival_id": r["rival_id"],
                    "period_end": date(int(r["fiscal_year"]), 12, 31),
                    "period_type": "annual",
                    "revenue_usd": (rev_m * 1_000_000.0) if rev_m is not None else None,
                    "gross_bookings_usd": (
                        (gb_m * 1_000_000.0) if gb_m is not None else None
                    ),
                    "take_rate_pct": r.get("take_rate_pct"),
                    "operating_margin_pct": r.get("operating_margin_pct"),
                    "active_customers": (
                        int(ac_m * 1_000_000) if ac_m is not None else None
                    ),
                    "room_nights": (
                        int(rn_m * 1_000_000) if rn_m is not None else None
                    ),
                    "segment_breakdown": r.get("segment_breakdown"),
                    "is_estimated": bool(r.get("is_estimated", False)),
                    "notes": r.get("notes"),
                },
            )
        )
    return AdapterExtraction(
        payload=payload,
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=tuple(fact_rows),
    )


__all__ = [
    "build_fetch_result",
    "extract_financials",
    "iter_filings",
]

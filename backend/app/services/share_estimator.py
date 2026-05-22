"""Market-share estimator (T-8.7, FR-08.4).

Most rivals do not disclose per-region market share. The dashboard
needs one anyway — every Win/Loss panel, every Share Trajectory chart,
and every Investor View KPI ultimately reads off
``MARKET_SHARE_ESTIMATE``. This service derives those rows from data
that *is* publicly available:

  * ``RivalFinancial`` — total revenue per rival per fiscal year
    (populated by SEC EDGAR, HKEX, IR-page adapters in Phase 8).
  * ``MarketGrowth`` — regional TAM per year (UNWTO + research firms).
  * ``Rival.hq_iso`` and ``RivalFinancial.segment_breakdown`` — the
    geographic weights used to allocate the rival's revenue across
    regions when no per-region disclosure exists.

The estimator runs as a backend service rather than as an ingestion
adapter for one reason: its inputs are *internal* fact tables, not
external sources. Persisting it as a derived fact (with its own
``sources`` row whose ``source_type='derived'`` and ``url`` is a
``derived://`` synthetic identifier) keeps the FR-08.6 provenance
contract intact without inventing a fake publisher.

The function is deliberately small and pure: every transformation is
captured in ``ShareCalculation``, so the View Source modal can show
the user the exact formula that produced any estimate ("we took
$11.1B Airbnb FY2024 revenue × 22% North America weight ÷ $240B US
TAM 2024 = 1.02% share").

Disclosed rows pass through verbatim with ``is_estimated=False`` and
``calculation_method='disclosed'``; derived rows carry the formula
string plus ``is_estimated=True``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models import MarketGrowth, MarketShareEstimate, Rival, RivalFinancial, Source
from ingestion.normalizer import upsert
from ingestion.provenance import record

log = logging.getLogger(__name__)


DERIVED_SOURCE_TYPE = "derived"
DERIVED_SOURCE_URL = "derived://services/share_estimator"
DERIVED_SOURCE_PUBLISHER = "OTA-Worldmap internal"


# ──────────────────────────────────────────────────────────────────────
# Pure calculation
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ShareCalculation:
    """One per (rival, region, period) — emitted by ``derive()``."""

    rival_id: str
    region_iso: str
    period_end: date
    share_pct: float
    is_estimated: bool
    calculation_method: str


def _region_weight(
    rival: Rival, region_iso: str, segment_breakdown: dict | None
) -> tuple[float, str]:
    """Return ``(weight, explanation)`` ∈ [0, 1] for ``region_iso``.

    Priority chain:

    1. Explicit per-region weight from ``segment_breakdown`` (e.g.
       ``{"North America": 38, "EMEA": 22}``) — most trusted, since the
       rival itself published it.
    2. ``Rival.hq_iso`` match — when no breakdown exists, attribute
       100% to the rival's home region. This is the same simplifying
       assumption the Phase 7b synthetic snapshots used; the
       comment in [data/seeds/seed.py](data/seeds/seed.py) calls it
       out explicitly.
    3. Otherwise 0 (the rival has no detectable footprint in that
       region, so it does not appear in the estimate).

    The explanation string is what surfaces in the View Source modal
    so the user can audit every estimated share.
    """
    if segment_breakdown:
        # CSV stores percentages as numbers (sum may be < 100 if some
        # regions are omitted from the disclosure). Find a region whose
        # name token appears in our region_iso.
        region_synonyms = {
            "US": ("United States", "USA", "North America"),
            "CA": ("Canada", "North America"),
            "MX": ("Mexico", "Latin America"),
            "BR": ("Brazil", "Latin America", "LatAm"),
            "AR": ("Argentina", "Latin America"),
            "GB": ("United Kingdom", "UK", "Europe", "EMEA"),
            "DE": ("Germany", "Europe", "EMEA"),
            "FR": ("France", "Europe", "EMEA"),
            "ES": ("Spain", "Europe", "EMEA"),
            "IT": ("Italy", "Europe", "EMEA"),
            "NL": ("Netherlands", "Europe", "EMEA"),
            "SE": ("Sweden", "Europe", "EMEA"),
            "CZ": ("Czech Republic", "Europe", "EMEA"),
            "PL": ("Poland", "Europe", "EMEA"),
            "PT": ("Portugal", "Europe", "EMEA"),
            "GR": ("Greece", "Europe", "EMEA"),
            "TR": ("Turkey", "Europe", "EMEA"),
            "JP": ("Japan", "Asia-Pacific", "Asia"),
            "CN": ("China", "Asia-Pacific", "Asia"),
            "IN": ("India", "Asia-Pacific", "Asia"),
            "KR": ("South Korea", "Korea", "Asia-Pacific", "Asia"),
            "SG": ("Singapore", "Asia-Pacific", "Asia"),
            "TH": ("Thailand", "Asia-Pacific", "Asia"),
            "ID": ("Indonesia", "Asia-Pacific", "Asia"),
            "AE": ("UAE", "United Arab Emirates", "Middle East"),
            "SA": ("Saudi Arabia", "Middle East"),
            "EG": ("Egypt", "Middle East", "Africa"),
            "ZA": ("South Africa", "Africa"),
            "NG": ("Nigeria", "Africa"),
            "AU": ("Australia", "Asia-Pacific", "Oceania"),
        }
        synonyms = region_synonyms.get(region_iso, (region_iso,))
        for key, value in segment_breakdown.items():
            if any(s.lower() in key.lower() for s in synonyms):
                pct = float(value)
                explanation = (
                    f"segment_breakdown[{key!r}]={pct}% applied to {region_iso}"
                )
                return pct / 100.0, explanation
    if rival.hq_iso == region_iso:
        return 1.0, f"HQ fallback: rival HQ is {region_iso}, 100% attributed"
    return 0.0, ""


def derive(
    *,
    rivals: Iterable[Rival],
    financials: Iterable[RivalFinancial],
    market_growth: Iterable[MarketGrowth],
) -> list[ShareCalculation]:
    """Pure transformation — no DB writes.

    Splitting the math out lets unit tests exercise the estimator with
    in-memory data and zero Postgres.
    """
    rivals_by_id = {str(r.id): r for r in rivals}
    market_by_region_year: dict[tuple[str, int], float] = {}
    for mg in market_growth:
        key = (mg.region_iso, mg.year)
        # If multiple publishers reported the same (region, year), prefer
        # the largest one — research firms typically agree within a
        # narrow band and the high-end number defines the denominator
        # for share. The View Source modal still lists every source row.
        prior = market_by_region_year.get(key)
        if prior is None or mg.market_size_usd > prior:
            market_by_region_year[key] = float(mg.market_size_usd)

    results: list[ShareCalculation] = []
    for fin in financials:
        if fin.revenue_usd is None:
            continue
        rival = rivals_by_id.get(str(fin.rival_id))
        if rival is None:
            continue
        year = fin.period_end.year
        segment = fin.segment_breakdown if isinstance(fin.segment_breakdown, dict) else None
        for (region_iso, region_year), tam in market_by_region_year.items():
            if region_year != year or tam <= 0:
                continue
            weight, explanation = _region_weight(rival, region_iso, segment)
            if weight <= 0:
                continue
            share_pct = (float(fin.revenue_usd) * weight) / tam * 100.0
            # HQ-fallback and pct-weighting are both approximations, so
            # every derived row is an estimate. A future Phase 10
            # fact table may carry rival-disclosed regional revenue;
            # those rows will land with is_estimated=False directly,
            # not through this service.
            is_estimated = True
            method = (
                f"share = revenue_usd({fin.revenue_usd:.0f}) "
                f"× weight({weight:.4f} — {explanation}) "
                f"÷ tam({tam:.0f}) × 100"
            )
            results.append(
                ShareCalculation(
                    rival_id=str(fin.rival_id),
                    region_iso=region_iso,
                    period_end=fin.period_end,
                    share_pct=round(share_pct, 4),
                    is_estimated=is_estimated,
                    calculation_method=method,
                )
            )
    return results


# ──────────────────────────────────────────────────────────────────────
# DB orchestration
# ──────────────────────────────────────────────────────────────────────


def _ensure_derived_source(session: Session, retrieved_at: datetime) -> str:
    """Insert-or-fetch the synthetic ``derived`` ``sources`` row."""
    return record(
        session,
        url=DERIVED_SOURCE_URL,
        publisher=DERIVED_SOURCE_PUBLISHER,
        source_type=DERIVED_SOURCE_TYPE,
        content_hash="derived-v1",
        retrieved_at=retrieved_at,
        raw_payload_ref=None,
    )


def run(session: Session, *, retrieved_at: Optional[datetime] = None) -> int:
    """End-to-end: read warehouse → derive shares → upsert.

    Returns the number of rows upserted (one per rival × region × period
    that successfully derived a non-zero share).
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)

    rivals = list(session.query(Rival).all())
    financials = list(session.query(RivalFinancial).all())
    market_growth = list(session.query(MarketGrowth).all())

    calcs = derive(rivals=rivals, financials=financials, market_growth=market_growth)
    log.info("share_estimator: derived %d share rows", len(calcs))
    if not calcs:
        return 0

    source_id = _ensure_derived_source(session, retrieved_at)

    for calc in calcs:
        upsert(
            session,
            MarketShareEstimate,
            natural_key=("rival_id", "region_iso", "period_end", "source_id"),
            payload={
                "rival_id": calc.rival_id,
                "region_iso": calc.region_iso,
                "period_end": calc.period_end,
                "share_pct": calc.share_pct,
                "is_estimated": calc.is_estimated,
                "calculation_method": calc.calculation_method,
                "source_id": source_id,
            },
        )
    return len(calcs)


__all__ = [
    "DERIVED_SOURCE_PUBLISHER",
    "DERIVED_SOURCE_TYPE",
    "DERIVED_SOURCE_URL",
    "ShareCalculation",
    "derive",
    "run",
]

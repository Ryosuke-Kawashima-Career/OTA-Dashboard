"""Phase 8 share-estimator unit tests — pure-Python, no DB / network required.

Exercises the ``derive()`` calculation in isolation using small fakes
instead of SQLAlchemy entities, so the math is locked in regardless of
warehouse state.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.services import share_estimator


@dataclass
class FakeRival:
    id: uuid.UUID
    hq_iso: str | None
    name: str = "Test Rival"


@dataclass
class FakeFinancial:
    rival_id: uuid.UUID
    period_end: date
    revenue_usd: float | None
    segment_breakdown: dict | None = None


@dataclass
class FakeMarketGrowth:
    region_iso: str
    year: int
    market_size_usd: float


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def test_hq_fallback_when_no_segment_breakdown():
    """A rival with no segment data attributes 100% of revenue to its HQ region."""
    rival_id = _uid()
    rival = FakeRival(id=rival_id, hq_iso="JP")
    fin = FakeFinancial(
        rival_id=rival_id,
        period_end=date(2024, 12, 31),
        revenue_usd=1_000_000_000.0,  # $1B
        segment_breakdown=None,
    )
    tam = FakeMarketGrowth(region_iso="JP", year=2024, market_size_usd=14_500_000_000.0)
    other = FakeMarketGrowth(region_iso="US", year=2024, market_size_usd=240_000_000_000.0)

    calcs = share_estimator.derive(
        rivals=[rival], financials=[fin], market_growth=[tam, other]
    )
    # HQ-fallback assigns 0% to non-HQ regions, so only the JP row is returned.
    assert len(calcs) == 1
    assert calcs[0].region_iso == "JP"
    assert calcs[0].is_estimated is True
    expected = 1_000_000_000.0 / 14_500_000_000.0 * 100.0
    assert abs(calcs[0].share_pct - round(expected, 4)) < 1e-3
    assert "HQ fallback" in calcs[0].calculation_method


def test_segment_breakdown_takes_precedence_over_hq():
    """When a rival publishes regional weights, the estimator uses them."""
    rival_id = _uid()
    rival = FakeRival(id=rival_id, hq_iso="US")
    fin = FakeFinancial(
        rival_id=rival_id,
        period_end=date(2024, 12, 31),
        revenue_usd=10_000_000_000.0,  # $10B
        segment_breakdown={"North America": 38, "EMEA": 22, "Asia-Pacific": 40},
    )
    us_tam = FakeMarketGrowth(region_iso="US", year=2024, market_size_usd=240_000_000_000.0)
    de_tam = FakeMarketGrowth(region_iso="DE", year=2024, market_size_usd=44_000_000_000.0)
    jp_tam = FakeMarketGrowth(region_iso="JP", year=2024, market_size_usd=14_500_000_000.0)

    calcs = {c.region_iso: c for c in share_estimator.derive(
        rivals=[rival], financials=[fin], market_growth=[us_tam, de_tam, jp_tam]
    )}
    # 38% × $10B = $3.8B over $240B TAM ≈ 1.583%
    assert abs(calcs["US"].share_pct - round(3_800_000_000 / 240_000_000_000 * 100.0, 4)) < 1e-3
    # 22% × $10B = $2.2B over $44B ≈ 5.0%
    assert abs(calcs["DE"].share_pct - round(2_200_000_000 / 44_000_000_000 * 100.0, 4)) < 1e-3
    # 40% × $10B = $4B over $14.5B ≈ 27.586%
    assert abs(calcs["JP"].share_pct - round(4_000_000_000 / 14_500_000_000 * 100.0, 4)) < 1e-3
    for c in calcs.values():
        assert c.calculation_method.startswith("share = revenue_usd(")


def test_skips_rivals_with_no_revenue():
    rival_id = _uid()
    rival = FakeRival(id=rival_id, hq_iso="JP")
    fin = FakeFinancial(
        rival_id=rival_id,
        period_end=date(2024, 12, 31),
        revenue_usd=None,
    )
    tam = FakeMarketGrowth(region_iso="JP", year=2024, market_size_usd=14_500_000_000.0)
    calcs = share_estimator.derive(
        rivals=[rival], financials=[fin], market_growth=[tam]
    )
    assert calcs == []


def test_uses_largest_tam_when_publishers_disagree():
    """When two publishers report different TAMs, prefer the larger one."""
    rival_id = _uid()
    rival = FakeRival(id=rival_id, hq_iso="JP")
    fin = FakeFinancial(
        rival_id=rival_id,
        period_end=date(2024, 12, 31),
        revenue_usd=1_000_000_000.0,
    )
    small = FakeMarketGrowth(region_iso="JP", year=2024, market_size_usd=10_000_000_000.0)
    big = FakeMarketGrowth(region_iso="JP", year=2024, market_size_usd=14_500_000_000.0)
    calcs = share_estimator.derive(
        rivals=[rival], financials=[fin], market_growth=[small, big]
    )
    expected = 1_000_000_000.0 / 14_500_000_000.0 * 100.0
    assert abs(calcs[0].share_pct - round(expected, 4)) < 1e-3

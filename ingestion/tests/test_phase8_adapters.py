"""Phase 8 adapter unit tests — pure-Python, no DB / network required.

Covers the parser branch of every Phase 8 adapter:

  * UNWTO / JNTO fixture mode → InboundTourism FactRows
  * World Bank JSON wire shape → InboundTourism FactRows
  * IMF SDMX-JSON → parse_rates() returns {year: rate}
  * Industry research → MarketGrowth FactRows, grouped by publisher
  * Financials fixture (SEC / HKEX / IR) → RivalFinancial FactRows
  * SEC / HKEX / IR url-predicate filters partition rival_financials.csv
    into disjoint, covering slices.
"""
from __future__ import annotations

from app.models import InboundTourism, MarketGrowth, RivalFinancial
from ingestion.adapters import hkex, imf, industry_research, ir_page, jnto, sec_edgar
from ingestion.adapters import unwto, world_bank
from ingestion.adapters._financials_fixture import iter_filings


# ── UNWTO / JNTO ──────────────────────────────────────────────────────


def test_unwto_curated_fixture_yields_inbound_tourism_rows():
    fetch = unwto.fetch_from_curated(region_isos=["JP"])
    extraction = unwto.extract(fetch.payload)
    assert len(extraction.fact_rows) > 0
    for row in extraction.fact_rows:
        assert row.target is InboundTourism
        assert row.payload["region_iso"] == "JP"
        assert "source_id" not in row.payload  # set by run_adapter
    years = sorted(r.payload["year"] for r in extraction.fact_rows)
    assert years == sorted(set(years))


def test_jnto_only_returns_jp_rows():
    fetch = jnto.fetch_from_curated()
    extraction = jnto.extract(fetch.payload)
    assert all(row.payload["region_iso"] == "JP" for row in extraction.fact_rows)


# ── World Bank ────────────────────────────────────────────────────────


def test_world_bank_fixture_round_trip():
    fetch = world_bank.fetch_from_fixture(
        region_iso="JP",
        rows=[(2022, 38_000_000_000.0), (2023, 42_000_000_000.0)],
    )
    extraction = world_bank.extract(fetch.payload)
    assert len(extraction.fact_rows) == 2
    payload_2022 = next(
        r.payload for r in extraction.fact_rows if r.payload["year"] == 2022
    )
    # 38B USD ÷ 1e6 = 38_000 millions
    assert abs(payload_2022["tourism_receipts_usd_millions"] - 38_000.0) < 1e-6
    assert payload_2022["region_iso"] == "JP"
    assert payload_2022["is_estimated"] is False


def test_world_bank_ignores_non_tourism_indicators():
    """GDP rows must be skipped — they have no fact table yet."""
    fetch = world_bank.fetch_from_fixture(
        region_iso="JP",
        indicator=world_bank.INDICATOR_GDP,
        rows=[(2024, 4_000_000_000_000.0)],
    )
    extraction = world_bank.extract(fetch.payload)
    assert extraction.fact_rows == ()


# ── IMF ───────────────────────────────────────────────────────────────


def test_imf_parse_rates_round_trip():
    fetch = imf.fetch_from_fixture(
        region_iso3="JPN",
        rates=[(2023, 140.5), (2024, 150.1)],
    )
    rates = imf.parse_rates(fetch.payload)
    assert rates == {2023: 140.5, 2024: 150.1}


def test_imf_extract_emits_no_fact_rows_but_keeps_payload():
    """IMF has no fact table yet — extract must still preserve payload."""
    fetch = imf.fetch_from_fixture(region_iso3="JPN", rates=[(2024, 150.1)])
    extraction = imf.extract(fetch.payload)
    assert extraction.fact_rows == ()
    assert extraction.payload == fetch.payload


# ── Industry research ────────────────────────────────────────────────


def test_industry_research_groups_by_publisher_and_yields_market_growth():
    publishers = list(industry_research.iter_publishers())
    assert publishers, "Curated CSV must yield at least one publisher group"
    # Statista is heavily used in market_growth.csv, so it must be present.
    publisher_names = {p[0] for p in publishers}
    assert "Statista" in publisher_names
    assert "Phocuswright" in publisher_names

    # Round-trip a single publisher through build_fetch_result + extract.
    publisher, source_type, url, rows = publishers[0]
    fetch = industry_research.build_fetch_result(
        publisher=publisher, canonical_url=url, rows=rows
    )
    extraction = industry_research.extract(fetch.payload)
    assert len(extraction.fact_rows) == len(rows)
    for row in extraction.fact_rows:
        assert row.target is MarketGrowth
        assert row.payload["market_size_usd"] > 0
        assert row.payload["region_iso"]


def test_industry_research_covers_two_publishers_for_japan():
    """FR-08.1 acceptance: ≥ 2 publishers per region."""
    publishers_for_jp: set[str] = set()
    for publisher, _, _, rows in industry_research.iter_publishers():
        if any(r["region_iso"] == "JP" for r in rows):
            publishers_for_jp.add(publisher)
    assert len(publishers_for_jp) >= 2, publishers_for_jp


# ── Financials fixture / SEC / HKEX / IR ─────────────────────────────


def test_financials_fixture_round_trip():
    # Any one URL → one set of RivalFinancial rows
    sec_iter = list(sec_edgar.iter_sec_filings())
    assert sec_iter, "Expect at least one SEC filing URL in rival_financials.csv"
    url, rows = sec_iter[0]
    fetch = sec_edgar.build_sec_fetch_result(url=url, rows=rows)
    extraction = sec_edgar.extract(fetch.payload)
    assert len(extraction.fact_rows) == len(rows)
    for fr in extraction.fact_rows:
        assert fr.target is RivalFinancial
        assert fr.payload["period_type"] == "annual"
        assert fr.payload["period_end"].month == 12


def test_sec_hkex_ir_partitions_are_disjoint_and_covering():
    """Every rival_financial row lands in exactly one of the three adapters."""
    seen: list[str] = []
    for url, rows in iter_filings(url_predicate=lambda u: True):
        seen.append(url)
    total_urls = set(seen)
    assert total_urls

    sec_urls = {u for u, _ in sec_edgar.iter_sec_filings()}
    hkex_urls = {u for u, _ in hkex.iter_hkex_filings()}
    ir_urls = {u for u, _ in ir_page.iter_ir_filings()}

    # Disjoint.
    assert sec_urls.isdisjoint(hkex_urls)
    assert sec_urls.isdisjoint(ir_urls)
    assert hkex_urls.isdisjoint(ir_urls)

    # Covering.
    assert sec_urls | hkex_urls | ir_urls == total_urls

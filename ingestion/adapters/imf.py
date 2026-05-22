"""IMF adapter (T-8.2).

The IMF publishes the ``IFS`` (International Financial Statistics) dataset
via its SDMX-JSON API at
``https://www.imf.org/external/datamapper/api/v1/{indicator}/{iso}``.
For Phase 8 we pull a single indicator per region — ``ENDA_XDC_USD_RATE``,
the period-average exchange rate — so the normalizer has authoritative
FX figures to convert non-USD financials into USD before they hit the
warehouse.

Why ship the adapter even though there is no ``fx_rate`` fact table yet:

* The provenance contract (FR-08.6) demands that every figure ever
  rendered in the dashboard is traceable to a public source. Once the
  normalizer starts converting EUR/GBP/JPY into USD using IMF rates,
  the rate **itself** has to carry a ``source_id`` — same way every
  ``MarketGrowth`` row does. The cheapest way to get that is to land the
  IMF adapter now and let it persist a ``sources`` row + raw payload
  the moment any rate is consumed.

* A dedicated ``fx_rate`` table is a Phase 10 follow-up
  (``services/share_estimator.py`` does not need it — it operates on
  already-USD-denominated rivals' financials). Until that table lands,
  this adapter writes nothing into a fact table; ``run_adapter()``
  reports ``status="no_rows"`` and the source row + raw payload still
  give us audit-trail coverage.

Same five-step contract as ``unwto.py``: ``fetch`` returns bytes,
``extract`` returns an ``AdapterExtraction`` (with an empty
``fact_rows`` tuple for now), and the flow runs both through
``run_adapter()`` so layout drift and idempotency are handled
uniformly.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from ingestion.adapters._base import AdapterExtraction, FetchResult

log = logging.getLogger(__name__)


IMF_PUBLISHER = "IMF"
IMF_SOURCE_TYPE = "imf"

# Period-average bilateral exchange rate vs. USD. The IMF SDMX-JSON
# endpoint accepts an ISO-3 country code; callers pass ISO-2 and we
# leave the mapping to the orchestrating flow (mapping all 30 regions
# is a Phase 10 concern — Phase 8's tests pin on JP and EUR).
IMF_INDICATOR_FX_USD = "ENDA_XDC_USD_RATE"
IMF_URL_TEMPLATE = "https://www.imf.org/external/datamapper/api/v1/{indicator}/{iso}"


# ──────────────────────────────────────────────────────────────────────
# HTTP mode
# ──────────────────────────────────────────────────────────────────────


def fetch_via_http(
    http_client,
    *,
    region_iso3: str,
    indicator: str = IMF_INDICATOR_FX_USD,
) -> FetchResult:
    url = IMF_URL_TEMPLATE.format(indicator=indicator, iso=region_iso3.upper())
    result = http_client.fetch(url)
    if result.skipped:
        return FetchResult(url=url, skipped=True, skip_reason=result.skip_reason)
    return FetchResult(url=url, payload=result.body)


# ──────────────────────────────────────────────────────────────────────
# Fixture mode (offline regression baseline)
# ──────────────────────────────────────────────────────────────────────


def fetch_from_fixture(
    *,
    region_iso3: str,
    indicator: str = IMF_INDICATOR_FX_USD,
    rates: Optional[Iterable[tuple[int, float]]] = None,
) -> FetchResult:
    """Build a deterministic payload mimicking the IMF SDMX-JSON shape.

    Args:
        region_iso3: ISO-3 country code (``JPN``, ``GBR``, …).
        indicator: full IMF indicator code; defaults to FX rate vs. USD.
        rates: iterable of ``(year, value)`` tuples — value is the
            local-currency-per-USD rate. ``None`` → empty values dict so
            tests can cover the "no data" branch.
    """
    rates_list = list(rates or [])
    payload = {
        "values": {
            indicator: {
                region_iso3.upper(): {str(year): value for year, value in rates_list}
            }
        }
    }
    url = IMF_URL_TEMPLATE.format(indicator=indicator, iso=region_iso3.upper())
    return FetchResult(
        url=url,
        payload=json.dumps(payload, sort_keys=True).encode("utf-8"),
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────


def parse_rates(payload: bytes) -> dict[int, float]:
    """Decode the IMF SDMX-JSON payload into ``{year: rate}``.

    Exposed as a top-level helper so the normalizer can call it directly
    when converting non-USD financials, without having to go through
    ``run_adapter()``. The orchestrated path stays the same — we still
    persist raw payload + source row — but the parsed value is the
    interesting thing to a downstream consumer.
    """
    doc = json.loads(payload.decode("utf-8"))
    values = doc.get("values") or {}
    # SDMX-JSON nests as values.{indicator}.{iso3}.{year}.
    for indicator_block in values.values():
        for country_block in indicator_block.values():
            return {int(year): float(rate) for year, rate in country_block.items()}
    return {}


def extract(payload: bytes) -> AdapterExtraction:
    """Return an empty fact-row tuple — FX has no warehouse table yet.

    The raw payload is still persisted by ``run_adapter()`` so the
    rates are recoverable for audit even though they aren't promoted
    into a fact table in Phase 8.
    """
    try:
        parsed = parse_rates(payload)
        log.info("imf: parsed %d rate observations", len(parsed))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("imf: payload parse failed: %s", exc)
    return AdapterExtraction(
        payload=payload,
        retrieved_at=datetime.now(timezone.utc),
        fact_rows=(),
    )


__all__ = [
    "IMF_INDICATOR_FX_USD",
    "IMF_PUBLISHER",
    "IMF_SOURCE_TYPE",
    "IMF_URL_TEMPLATE",
    "extract",
    "fetch_from_fixture",
    "fetch_via_http",
    "parse_rates",
]

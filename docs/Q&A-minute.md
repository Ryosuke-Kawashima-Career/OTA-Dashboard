# Questions for the Agent

## Questions and Answers

### Q: What is the meaning/purpose of `@task(name="monthly_market.industry_research", cache_policy=NO_CACHE)`?

**A:** This Prefect (オーケストレーションツール) decorator registers the function as a task with an explicit run name for observability, and `cache_policy=NO_CACHE` disables result caching (キャッシュ無効化) so the task always re-executes.

- **`name="monthly_market.industry_research"`** → gives the task a stable, traceable identity in the Prefect UI / run graph (dotted namespace = flow.task convention).
- **`cache_policy=NO_CACHE`** → forces a fresh execution every run; prevents Prefect from returning a memoized result keyed on inputs. Critical for adapters that fetch external data (e.g., industry research feeds) where the *same inputs* may yield *different outputs* over time.
- **Purpose summary:** named for traceability (追跡性), NO_CACHE for data freshness (鮮度保証).

### Q: What do adapters do in `ingestion/adapters/`?

**A:** Adapters are per-source connectors (コネクタ) that pull external data and normalize it into the dashboard's fact tables via a shared five-step pipeline.

- **One file per upstream source** — `unwto.py`, `jnto.py`, `imf.py`, `world_bank.py`, `sec_edgar.py`, `hkex.py`, `ir_page.py`, `pdf_report.py`, `industry_research.py`, plus `echo.py` (fixture/smoke test).
- **Two pure callables per adapter:**
  - `fetch(http_client, **params) -> FetchResult` — returns raw bytes + source URL; may set `skipped=True` if robots.txt (クローラ規約) or a fixture sentinel blocks it.
  - `extract(payload, **context) -> AdapterExtraction` — pure parser (純粋関数); turns bytes into `FactRow`s with no network I/O.
- **Shared orchestration in `_base.run_adapter()` runs the five steps:**
  1. **Raw-first persistence (生データ保存)** → `RawPayloadStore.write()` content-addressed by sha256.
  2. **Layout drift guard (レイアウト変化検知)** → DOM-skeleton hash compared via `LayoutChangeDetector`; alerts and aborts on drift (HTML/XBRL only — JSON APIs skip this).
  3. **Parse** → call `extract_fn(payload)`.
  4. **Provenance record (出典記録)** → insert a `sources` row keyed on content hash + retrieved_at.
  5. **Upsert facts (冪等更新)** → `normalizer.upsert()` per `FactRow` with natural key, stamped with the new `source_id`.
- **Why this shape:** separating fetch/extract makes unit tests fixture-driven (no network), and the shared pipeline guarantees every byte that influences analytics is traceable to a `sources` row.
- **Supporting modules:** `_base.py` (scaffolding/dataclasses), `_http.py` (HTTP client + robots check), `_financials_fixture.py` (shared fixture helpers).

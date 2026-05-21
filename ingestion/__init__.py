"""OTA-Worldmap ingestion package (Phase 7 onwards).

This package is intentionally split from `backend/` so the dashboard API
process and the ingestion workers can be deployed and scaled
independently. The ingestion side reuses the backend's SQLAlchemy
models (via `from app.models import ...`), so PYTHONPATH must include
`backend/` when running ingestion flows.
"""

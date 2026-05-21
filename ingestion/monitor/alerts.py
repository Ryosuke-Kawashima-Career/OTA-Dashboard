"""Slack alerting for ingestion-pipeline events (T-7.4, FR-08.5).

We deliberately depend only on `requests` here — adding a heavyweight
Slack SDK would buy us no real value for the handful of webhook calls
we make per day.
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5
_LEVEL_PREFIX = {
    "info": ":information_source:",
    "warning": ":warning:",
    "error": ":rotating_light:",
}


def post_alert(message: str, *, level: str = "warning") -> bool:
    """Send `message` to the configured Slack webhook.

    Returns True if the webhook was posted, False otherwise (missing
    config or transport error). The function never raises — alerting
    must not be able to take down the ingestion job whose problem it's
    trying to report.
    """
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    prefix = _LEVEL_PREFIX.get(level, "")
    if not webhook:
        # Local dev / CI: structured log line is the alert.
        log.warning("alert (no SLACK_WEBHOOK_URL): %s %s", prefix, message)
        return False
    try:
        resp = requests.post(
            webhook,
            json={"text": f"{prefix} {message}".strip()},
            timeout=_TIMEOUT_SECONDS,
        )
        if resp.status_code >= 400:
            log.error("Slack webhook returned %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
    except requests.RequestException as exc:
        log.error("Slack alert transport failure: %s", exc)
        return False

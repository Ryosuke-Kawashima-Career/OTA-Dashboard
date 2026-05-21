"""Layout-change detector (T-7.4, FR-08.5).

External pages mutate. If a rival's IR template silently changes, our
extractor would happily write garbage into `rival_financial` until a
human noticed. This module catches that case by hashing the *structure*
of each fetched payload and comparing it against a rolling window of
recently-seen fingerprints per source URL.

Design choices, written out so the next maintainer doesn't relitigate
them:

* **DOM-skeleton hash, not full-HTML hash.** Real pages change text
  content on every fetch (ad slots, timestamps, A/B variants). Hashing
  only the tag tree — no text, no attributes — keeps the fingerprint
  stable as long as the scraper's selectors still apply. We alert only
  on structural shifts that would actually break extraction.

* **Rolling window of 5, not "compare against last 1".** Many sites
  oscillate between a handful of legitimate templates (earnings-day vs.
  normal day, A/B test cohorts). A window of 5 acts as a small
  allowlist: a new fingerprint is treated as drift only when it
  matches *none* of the recent five. This trades off responsiveness
  (we may take a couple of runs to "learn" a new variant) against
  false-positive volume.

* **Fingerprints are stored on disk, not in the database.** Layout
  fingerprints are operational state, not warehouse data — keeping
  them as small JSON files per source URL means the database stays
  free of pipeline-internal bookkeeping and tests can run without a
  Postgres connection.

* **First-ever run never alerts.** With an empty history there's no
  baseline to "differ from" — alerting there would be noise.
"""
from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from bs4 import BeautifulSoup, NavigableString, Tag

DEFAULT_WINDOW = 5


# ──────────────────────────────────────────────────────────────────────
# Fingerprinting primitives
# ──────────────────────────────────────────────────────────────────────


def _walk_skeleton(node: Tag | NavigableString, parts: list[str]) -> None:
    """Append a structural sketch of `node` (tag-tree only) to `parts`."""
    if isinstance(node, NavigableString):
        # Text content is intentionally ignored.
        return
    if not isinstance(node, Tag):
        return
    parts.append(f"<{node.name}>")
    for child in node.children:
        _walk_skeleton(child, parts)
    parts.append(f"</{node.name}>")


def dom_skeleton_hash(html: str) -> str:
    """SHA-256 of the tag tree of `html`.

    Two pages with the same structural shape (even if the inner text or
    attribute values differ) produce identical hashes.
    """
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    _walk_skeleton(soup, parts)
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def xbrl_tag_count_fingerprint(xbrl: str) -> str:
    """Cheap fingerprint for XBRL filings: hash the sorted tag-count map.

    SEC filings have many thousands of distinct XBRL element types; a
    silent template change (e.g. SEC reorganises the taxonomy) shows up
    immediately as a different fingerprint without us having to parse
    every concept.
    """
    soup = BeautifulSoup(xbrl, "xml")
    counts: dict[str, int] = {}
    for tag in soup.find_all(True):
        counts[tag.name] = counts.get(tag.name, 0) + 1
    canonical = json.dumps(counts, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────
# Detector
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LayoutCheckResult:
    """Outcome of one `LayoutChangeDetector.check(...)` call."""

    changed: bool
    fingerprint: str
    prior_window: tuple[str, ...]

    @property
    def first_run(self) -> bool:
        return not self.prior_window


class LayoutChangeDetector:
    """Per-source rolling-window fingerprint comparator.

    Persists state as `<store_dir>/<sha256(url)>.json` so a restart of
    the ingestion worker doesn't lose history.
    """

    def __init__(self, store_dir: str | Path, *, window: int = DEFAULT_WINDOW):
        self._root = Path(store_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._window = window

    # ── Public API ────────────────────────────────────────────────────

    def check(self, source_url: str, fingerprint: str) -> LayoutCheckResult:
        """Compare `fingerprint` against the rolling window for `source_url`.

        Behaviour:
          * Empty history → record, return `changed=False, first_run=True`.
          * `fingerprint` already in window → record (moves it to most-recent
            slot), return `changed=False`.
          * Otherwise → DO NOT add to window, return `changed=True` so the
            caller can alert and skip the upsert.
        """
        history = self._load(source_url)
        if not history:
            self._save(source_url, [fingerprint])
            return LayoutCheckResult(changed=False, fingerprint=fingerprint, prior_window=())
        if fingerprint in history:
            # Known — push it to the most-recent slot but keep the window
            # bounded.
            new_history = [h for h in history if h != fingerprint] + [fingerprint]
            self._save(source_url, new_history)
            return LayoutCheckResult(
                changed=False, fingerprint=fingerprint, prior_window=tuple(history)
            )
        # Novel fingerprint: flag drift; do not pollute the window.
        return LayoutCheckResult(
            changed=True, fingerprint=fingerprint, prior_window=tuple(history)
        )

    def accept(self, source_url: str, fingerprint: str) -> None:
        """Force-accept a previously-novel fingerprint (e.g. after a human
        confirms the new layout is good and the extractor has been updated).
        Adds to the window if not already present.
        """
        history = self._load(source_url)
        if fingerprint not in history:
            history.append(fingerprint)
        self._save(source_url, history)

    def history(self, source_url: str) -> tuple[str, ...]:
        return tuple(self._load(source_url))

    # ── Storage helpers ──────────────────────────────────────────────

    def _path(self, source_url: str) -> Path:
        key = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        return self._root / f"{key}.json"

    def _load(self, source_url: str) -> list[str]:
        p = self._path(source_url)
        if not p.exists():
            return []
        return list(json.loads(p.read_text()))

    def _save(self, source_url: str, history: Iterable[str]) -> None:
        bounded = list(deque(history, maxlen=self._window))
        self._path(source_url).write_text(json.dumps(bounded))

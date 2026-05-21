"""T-7.4 acceptance: DOM-skeleton hash + rolling window detection."""
from __future__ import annotations

from ingestion.monitor.layout_change_detector import (
    DEFAULT_WINDOW,
    LayoutChangeDetector,
    dom_skeleton_hash,
)


def test_skeleton_hash_ignores_text_and_attribute_changes():
    a = "<html><body><h1 class='a'>One</h1></body></html>"
    b = "<html><body><h1 class='b' style='color:red'>Totally different</h1></body></html>"
    # Same tag tree, different text/attrs → identical hash.
    assert dom_skeleton_hash(a) == dom_skeleton_hash(b)


def test_skeleton_hash_changes_on_structural_change():
    a = "<html><body><h1>One</h1></body></html>"
    b = "<html><body><h1>One</h1><p>Now with paragraph</p></body></html>"
    assert dom_skeleton_hash(a) != dom_skeleton_hash(b)


def test_first_run_never_alerts(tmp_path):
    det = LayoutChangeDetector(tmp_path)
    result = det.check("https://example.com/", "fp-A")

    assert result.changed is False
    assert result.first_run is True
    # Fingerprint must be persisted so the next run can compare.
    assert det.history("https://example.com/") == ("fp-A",)


def test_known_fingerprint_does_not_alert(tmp_path):
    det = LayoutChangeDetector(tmp_path)
    det.check("https://example.com/", "fp-A")
    det.check("https://example.com/", "fp-B")

    result = det.check("https://example.com/", "fp-A")  # re-seen
    assert result.changed is False


def test_novel_fingerprint_after_window_alerts_and_does_not_pollute_window(tmp_path):
    det = LayoutChangeDetector(tmp_path)
    for fp in ("fp-1", "fp-2", "fp-3"):
        det.check("https://example.com/", fp)

    result = det.check("https://example.com/", "fp-NOVEL")

    assert result.changed is True
    # Critically, drift fingerprints must NOT be added to the rolling
    # window — otherwise we'd silently accept the new layout.
    assert "fp-NOVEL" not in det.history("https://example.com/")


def test_window_is_bounded(tmp_path):
    det = LayoutChangeDetector(tmp_path)
    # Push more than `window` distinct fingerprints, all known via accept().
    for i in range(DEFAULT_WINDOW + 3):
        det.accept("https://example.com/", f"fp-{i}")

    # Window has at most DEFAULT_WINDOW entries, oldest evicted.
    history = det.history("https://example.com/")
    assert len(history) == DEFAULT_WINDOW
    assert history[-1] == f"fp-{DEFAULT_WINDOW + 2}"


def test_accept_promotes_novel_fingerprint(tmp_path):
    det = LayoutChangeDetector(tmp_path)
    det.check("https://example.com/", "fp-A")

    novel = det.check("https://example.com/", "fp-B")
    assert novel.changed is True

    # After human review, accept the new layout.
    det.accept("https://example.com/", "fp-B")
    again = det.check("https://example.com/", "fp-B")
    assert again.changed is False

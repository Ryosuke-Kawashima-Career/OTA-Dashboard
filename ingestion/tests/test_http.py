"""T-7.7 acceptance: robots.txt + token-bucket rate limiting."""
from __future__ import annotations

import io
import itertools
import urllib.robotparser

from ingestion.adapters._http import HttpClient, HttpResult, TokenBucket


# ──────────────────────────────────────────────────────────────────────
# robots.txt enforcement
# ──────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"ok", url: str = ""):
        self.status_code = status
        self.content = body
        self.url = url


def _robots_parser(rules: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(rules.splitlines())
    return rp


def test_robots_disallow_skips_fetch():
    rp = _robots_parser("User-agent: *\nDisallow: /private/\n")

    calls: list[str] = []

    def fake_transport(url, **kw):  # transport must NOT be called
        calls.append(url)
        return _FakeResponse()

    client = HttpClient(transport=fake_transport)
    client.set_robots_for_host("example.com", rp)

    result = client.fetch("https://example.com/private/foo")

    assert result.skipped is True
    assert result.skip_reason == "robots.txt disallow"
    assert calls == [], "Disallowed URL must not hit the network"


def test_robots_allow_proceeds_to_fetch():
    rp = _robots_parser("User-agent: *\nAllow: /\n")

    def fake_transport(url, **kw):
        return _FakeResponse(status=200, body=b"ok", url=url)

    client = HttpClient(transport=fake_transport)
    client.set_robots_for_host("example.com", rp)

    result = client.fetch("https://example.com/page")

    assert result.skipped is False
    assert result.ok is True


# ──────────────────────────────────────────────────────────────────────
# Token bucket
# ──────────────────────────────────────────────────────────────────────


def test_token_bucket_paces_requests():
    """At 2 req/s the 2nd request must wait ~0.5s after the 1st."""
    fake_time = iter([0.0, 0.0, 0.0, 0.5, 0.5])  # clock readings
    sleeps: list[float] = []

    bucket = TokenBucket(
        rps=2.0,
        capacity=1,
        clock=lambda _it=fake_time: next(_it),
        sleep=sleeps.append,
    )

    bucket.wait()  # first call uses the token, no sleep
    bucket.wait()  # second call must sleep ~0.5s

    assert sleeps == [0.5]


def test_token_bucket_refills_over_time():
    """After enough wall-clock time, the bucket should refill and not sleep."""
    fake_now = [0.0]

    def clock():
        return fake_now[0]

    def sleep(_):
        # If the bucket asked us to sleep, fail loudly — we shouldn't need to.
        raise AssertionError("Bucket should be full enough that no sleep is needed")

    bucket = TokenBucket(rps=1.0, capacity=1, clock=clock, sleep=sleep)
    bucket.wait()
    fake_now[0] = 2.0  # 2 seconds elapsed → bucket fully refilled
    bucket.wait()

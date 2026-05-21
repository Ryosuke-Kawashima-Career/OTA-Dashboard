"""HTTP middleware for adapters (T-7.7, FR-08.5).

Every production adapter (SEC EDGAR, HKEX, IR pages, press RSS, career
sites…) goes through this client so the same compliance posture applies
uniformly:

* **`robots.txt` is consulted** before any fetch; disallowed paths
  short-circuit with `HttpResult(skipped=True)` rather than 4xx-ing the
  remote host. We cache the parsed rules per host (TTL configurable)
  to avoid hammering `/robots.txt` itself.

* **Per-host token bucket** spaces requests out so we never exceed
  a configured RPS, regardless of how many adapters run in parallel.
  The bucket size + refill rate is per-host because rivals' tolerances
  differ wildly (SEC happily serves 10 req/s, Trip.com may want 1).

* **`Crawl-delay`** from `robots.txt` is honored when present and is
  stricter than the default rate.

This module deliberately has no external dependencies beyond the stdlib
+ `requests` so it stays unit-testable without spinning up a real HTTP
server (tests inject a fake `transport` callable).
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Optional
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Result + exceptions
# ──────────────────────────────────────────────────────────────────────


class RobotsBlocked(Exception):
    """Raised by `HttpClient.fetch_or_raise()` when robots.txt forbids the URL."""


@dataclass
class HttpResult:
    """Outcome of one fetch call.

    `skipped=True` distinguishes "we voluntarily declined to fetch" from
    "the server returned a 4xx" — the layout-change detector + flow
    upstream need to treat those differently.
    """

    url: str
    status: int = 0
    body: bytes = b""
    skipped: bool = False
    skip_reason: str = ""
    final_url: str = ""

    @property
    def ok(self) -> bool:
        return (not self.skipped) and 200 <= self.status < 300


# ──────────────────────────────────────────────────────────────────────
# Token bucket
# ──────────────────────────────────────────────────────────────────────


@dataclass
class TokenBucket:
    """Thread-safe leaky bucket — `rps` tokens per second up to `capacity`.

    A worker calls `wait()` before each request; the call blocks for the
    minimum interval needed to keep within the configured rate. Time is
    sourced from a callable so unit tests can drive the clock.
    """

    rps: float
    capacity: int = 1
    clock: Callable[[], float] = field(default=time.monotonic)
    sleep: Callable[[float], None] = field(default=time.sleep)

    _tokens: float = field(init=False, default=0.0)
    _last: float = field(init=False, default=0.0)
    _lock: Lock = field(init=False, default_factory=Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last = self.clock()

    def wait(self) -> None:
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            deficit = 1.0 - self._tokens
            delay = deficit / self.rps
        self.sleep(delay)
        with self._lock:
            self._refill()
            # After sleeping `deficit / rps`, we now have at least 1 token.
            self._tokens = max(0.0, self._tokens - 1.0)

    def _refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rps)
        self._last = now


# ──────────────────────────────────────────────────────────────────────
# HTTP client
# ──────────────────────────────────────────────────────────────────────


DEFAULT_USER_AGENT = "OTA-Worldmap-Ingestion/1.0 (+https://github.com/ota-worldmap)"


class HttpClient:
    """robots.txt-aware, per-host rate-limited HTTP fetcher.

    Args:
        user_agent: sent as `User-Agent` and used for robots-rules lookup
            (so the per-UA `Allow:` rules apply correctly).
        default_rps: fallback per-host rate when `Crawl-delay` is absent.
        transport: callable `(url, headers, timeout) -> requests.Response`
            for dependency injection in tests. Defaults to `requests.get`.
    """

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        default_rps: float = 1.0,
        transport: Optional[Callable[..., requests.Response]] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._ua = user_agent
        self._default_rps = default_rps
        self._transport = transport or requests.get
        self._clock = clock
        self._sleep = sleep
        self._robots_by_host: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._buckets_by_host: dict[str, TokenBucket] = {}

    # ── Public API ────────────────────────────────────────────────────

    def fetch(self, url: str, *, timeout: float = 10.0) -> HttpResult:
        """Fetch `url`, returning an `HttpResult` (never raises on robots-block)."""
        host = urlparse(url).netloc
        if not self._robots_allows(url):
            log.info("robots.txt disallows %s; skipping", url)
            return HttpResult(
                url=url, skipped=True, skip_reason="robots.txt disallow"
            )
        bucket = self._bucket_for(host)
        bucket.wait()
        resp = self._transport(url, headers={"User-Agent": self._ua}, timeout=timeout)
        return HttpResult(
            url=url,
            status=resp.status_code,
            body=resp.content,
            final_url=getattr(resp, "url", url),
        )

    def fetch_or_raise(self, url: str, *, timeout: float = 10.0) -> HttpResult:
        """Same as `fetch`, but raises `RobotsBlocked` on disallow.

        Useful in tight pipelines where a robots-block is unexpected and
        should surface loudly rather than be silently skipped.
        """
        result = self.fetch(url, timeout=timeout)
        if result.skipped and result.skip_reason == "robots.txt disallow":
            raise RobotsBlocked(url)
        return result

    # Hooks for tests to wire in fake transports / clocks.
    def set_robots_for_host(
        self, host: str, parser: urllib.robotparser.RobotFileParser
    ) -> None:
        self._robots_by_host[host] = parser

    def set_bucket_for_host(self, host: str, bucket: TokenBucket) -> None:
        self._buckets_by_host[host] = bucket

    # ── Internals ─────────────────────────────────────────────────────

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc
        if host not in self._robots_by_host:
            self._robots_by_host[host] = self._load_robots(parsed.scheme, host)
        return self._robots_by_host[host].can_fetch(self._ua, url)

    def _load_robots(
        self, scheme: str, host: str
    ) -> urllib.robotparser.RobotFileParser:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{scheme}://{host}/robots.txt")
        try:
            rp.read()
        except Exception as exc:
            # If robots.txt is unreachable, default to *allow* — same
            # behaviour as urllib.robotparser, and what most polite
            # scrapers do. Worst case we still get gated by the host's
            # rate-limit response.
            log.warning("Could not load robots.txt for %s: %s", host, exc)
            rp.parse([])
        return rp

    def _bucket_for(self, host: str) -> TokenBucket:
        if host in self._buckets_by_host:
            return self._buckets_by_host[host]
        # Honour Crawl-delay if the host published one.
        rp = self._robots_by_host.get(host)
        rps = self._default_rps
        if rp is not None:
            crawl_delay = rp.crawl_delay(self._ua)
            if crawl_delay:
                rps = min(rps, 1.0 / float(crawl_delay))
        bucket = TokenBucket(
            rps=rps, capacity=1, clock=self._clock, sleep=self._sleep
        )
        self._buckets_by_host[host] = bucket
        return bucket

"""Login rate limiting.

**Scope and limitation, stated plainly:** this is an in-process, in-memory
sliding-window counter. It is correct for the current single-instance Phase 1
architecture and requires no external service. It is **not** distributed: with
N workers or N containers each process keeps its own counters, so the
configured limit would effectively be N x ``LOGIN_RATE_LIMIT_MAX`` per window.
Moving to a shared store (Redis, or a Mongo-backed counter) is the fix when the
API is scaled horizontally - that is a deliberate later step, not something
claimed here.

Both the client IP and the submitted address are counted, which stops two
different attacks:

* spraying one account from many addresses (caught by the per-IP counter);
* many accounts from one address (caught by the per-address counter).

A successful login clears the counters for that pair, so a legitimate user who
fumbles their password twice is not penalised for the rest of the window.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class RateLimitVerdict:
    """Outcome of a rate-limit check."""

    allowed: bool
    #: Seconds until the caller may retry. ``0`` when allowed.
    retry_after: int = 0
    #: Attempts recorded in the current window.
    attempts: int = 0

    @property
    def reason(self) -> str:
        return "too_many_attempts"


class LoginRateLimiter:
    """Sliding-window limiter keyed by arbitrary strings."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> LoginRateLimiter:
        settings = settings or get_settings()
        return cls(
            max_attempts=settings.login_rate_limit_max,
            window_seconds=settings.login_rate_limit_window_minutes * 60,
        )

    def _prune(self, key: str, now: float) -> deque[float]:
        bucket = self._attempts[key]
        cutoff = now - self._window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    def check(self, *keys: str) -> RateLimitVerdict:
        """Return whether any of ``keys`` is currently over the limit.

        Does not record an attempt; call :meth:`record_failure` for that.
        """
        now = time.monotonic()
        with self._lock:
            for key in keys:
                bucket = self._prune(key, now)
                if len(bucket) >= self._max_attempts:
                    retry_after = int(bucket[0] + self._window_seconds - now) + 1
                    return RateLimitVerdict(
                        allowed=False, retry_after=max(retry_after, 1), attempts=len(bucket)
                    )
        return RateLimitVerdict(allowed=True)

    def record_failure(self, *keys: str) -> RateLimitVerdict:
        """Record one failed attempt against every key and return the verdict."""
        now = time.monotonic()
        with self._lock:
            for key in keys:
                self._prune(key, now).append(now)
            worst = max(
                (len(self._prune(key, now)) for key in keys),
                default=0,
            )
            if worst >= self._max_attempts:
                oldest = min(
                    (self._prune(key, now)[0] for key in keys if self._prune(key, now)),
                    default=now,
                )
                retry_after = int(oldest + self._window_seconds - now) + 1
                return RateLimitVerdict(
                    allowed=False, retry_after=max(retry_after, 1), attempts=worst
                )
        return RateLimitVerdict(allowed=True, attempts=worst)

    def reset(self, *keys: str) -> None:
        """Forget the recorded attempts for these keys (after a success)."""
        with self._lock:
            for key in keys:
                self._attempts.pop(key, None)

    def prune_idle(self) -> None:
        """Drop buckets that no longer hold attempts.

        Called from the request path periodically so a long-running process
        cannot accumulate one deque per address that was ever submitted.
        """
        now = time.monotonic()
        with self._lock:
            for key in list(self._attempts):
                bucket = self._prune(key, now)
                if not bucket:
                    del self._attempts[key]

    @property
    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._attempts)


#: Process-wide limiter used by the login route.
_limiter: LoginRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_login_rate_limiter(settings: Settings | None = None) -> LoginRateLimiter:
    """Return the shared limiter, building it on first use."""
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                _limiter = LoginRateLimiter.from_settings(settings)
    return _limiter


def reset_login_rate_limiter() -> None:
    """Drop the shared limiter. Used by the test-suite and by tests in between."""
    global _limiter
    with _limiter_lock:
        _limiter = None


def ip_rate_key(client_ip: str) -> str:
    return f"ip:{client_ip}"


def email_rate_key(normalised_email: str) -> str:
    return f"email:{normalised_email}"

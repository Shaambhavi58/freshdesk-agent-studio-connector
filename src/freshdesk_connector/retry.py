"""Bounded retry timing helpers for transient Freshdesk failures."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite

TRANSIENT_STATUS_CODES = frozenset({500, 502, 503, 504})
MAX_BACKOFF_SECONDS = 5.0
MAX_JITTER_SECONDS = 0.2


def retry_after_seconds(value: str | None, *, now: datetime | None = None) -> float | None:
    """Parse Retry-After as seconds or an HTTP date."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    try:
        seconds = float(trimmed)
    except ValueError:
        seconds = None
    if seconds is not None and isfinite(seconds):
        return max(0.0, seconds)
    try:
        retry_at = parsedate_to_datetime(trimmed)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    current_time = now or datetime.now(UTC)
    return max(0.0, (retry_at - current_time).total_seconds())


def backoff_seconds(attempt: int, *, random_value: float | None = None) -> float:
    """Calculate capped exponential backoff with a small non-negative jitter."""
    exponent = max(0, attempt - 1)
    base = min(0.25 * (2**exponent), MAX_BACKOFF_SECONDS)
    jitter = random.random() if random_value is None else random_value
    return base + max(0.0, min(jitter, 1.0)) * MAX_JITTER_SECONDS
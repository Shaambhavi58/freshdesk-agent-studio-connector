"""Retry-After, bounded rate-limit retries, and transient server recovery."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.config import Settings
from freshdesk_connector.errors import RateLimitError, RetryExhaustedError
from freshdesk_connector.models import ListTicketsInput
from freshdesk_connector.retry import backoff_seconds, retry_after_seconds


async def test_rate_limit_retries_and_then_succeeds(settings: Settings) -> None:
    """A 429 response is retried using Retry-After before succeeding."""
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0.75"}),
            httpx.Response(200, json=[]),
        ]
        client = FreshdeskClient(settings, sleep=record_sleep)
        result = await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert result.success is True
    assert route.call_count == 2
    assert delays == [0.75]


async def test_rate_limit_retry_exhaustion_is_typed(settings: Settings) -> None:
    """Retries stop at the configured bound and return a rate-limit error."""
    settings.max_retries = 1
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "0"})
        )
        client = FreshdeskClient(settings, sleep=_record_noop)
        with pytest.raises(RateLimitError):
            await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert route.call_count == 2


async def test_transient_5xx_retries_then_succeeds(settings: Settings) -> None:
    """A 503 is retried, while its successful retry returns normally."""
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets")
        route.side_effect = [httpx.Response(503), httpx.Response(200, json=[])]
        client = FreshdeskClient(settings, sleep=_record_noop)
        result = await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert route.call_count == 2
    assert result.tickets == []


async def test_transient_5xx_retry_exhaustion_is_typed(settings: Settings) -> None:
    """A persistent transient 5xx is reported after the retry limit."""
    settings.max_retries = 1
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            return_value=httpx.Response(503)
        )
        client = FreshdeskClient(settings, sleep=_record_noop)
        with pytest.raises(RetryExhaustedError):
            await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert route.call_count == 2


def test_retry_after_supports_seconds_and_http_dates() -> None:
    """Retry-After supports both standard formats without a network call."""
    now = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    assert retry_after_seconds("2.5", now=now) == 2.5
    assert retry_after_seconds("Fri, 02 Oct 2026 10:00:03 GMT", now=now) == 3
    assert retry_after_seconds("not-a-date", now=now) is None
    assert retry_after_seconds("nan", now=now) is None
    assert backoff_seconds(1, random_value=0) == 0.25


async def _record_noop(_delay: float) -> None:
    """Avoid real waits in tests."""
    return None
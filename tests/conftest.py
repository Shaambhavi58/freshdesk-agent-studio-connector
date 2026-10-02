"""Shared test fixtures for mocked Freshdesk API tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Use fictional, test-only credentials and a reserved example domain."""
    return Settings(
        domain="example-company",
        api_key="test-api-key-not-a-real-credential",
        timeout_seconds=1,
        max_retries=2,
    )


@pytest.fixture
async def freshdesk_client(settings: Settings) -> AsyncIterator[FreshdeskClient]:
    """Create and close a client; all HTTP is intercepted by respx in each test."""
    client = FreshdeskClient(settings, sleep=_no_sleep)
    yield client
    await client.aclose()


async def _no_sleep(_delay: float) -> None:
    """Avoid delays in bounded retry tests."""
    await asyncio.sleep(0)
"""Authentication and secret-safe logging tests."""

from __future__ import annotations

import base64
import logging

import httpx
import respx

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.config import Settings
from freshdesk_connector.models import ListTicketsInput


async def test_api_key_is_basic_auth_username_and_x_is_password() -> None:
    """Freshdesk receives the API key as the basic-auth username."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=[])

    settings = Settings(domain="example-company", api_key="secret-test-key", max_retries=0)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(side_effect=handler)
        client = FreshdeskClient(settings)
        await client.list_tickets(ListTicketsInput())
        await client.aclose()

    expected = base64.b64encode(b"secret-test-key:X").decode()
    assert captured[0].headers["Authorization"] == f"Basic {expected}"


async def test_secret_is_not_written_to_logs_or_exception(caplog: logging.LogCaptureFixture) -> None:
    """Request logs contain metadata only, not the API key or authorization header."""
    secret = "do-not-log-this-test-key"
    settings = Settings(domain="example-company", api_key=secret, max_retries=0)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            return_value=httpx.Response(401, json={"message": secret})
        )
        client = FreshdeskClient(settings)
        with caplog.at_level(logging.INFO):
            try:
                await client.list_tickets(ListTicketsInput())
            except Exception as error:
                assert secret not in str(error)
            finally:
                await client.aclose()

    logged = caplog.text
    assert secret not in logged
    assert "Authorization" not in logged
    assert "description_text" not in logged
"""HTTP, timeout, network, JSON, and error response coverage."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.config import Settings
from freshdesk_connector.errors import (
    AuthenticationError,
    InvalidRequestError,
    InvalidResponseError,
    NetworkConnectionError,
    PermissionDeniedError,
    RequestTimeoutError,
    ServerError,
)
from freshdesk_connector.models import ErrorResponse, ListTicketsInput


@pytest.mark.parametrize(
    ("status_code", "error_type", "code"),
    [
        (400, InvalidRequestError, "invalid_request"),
        (401, AuthenticationError, "authentication_failed"),
        (403, PermissionDeniedError, "permission_denied"),
        (501, ServerError, "server_error"),
    ],
)
async def test_http_errors_map_to_safe_typed_errors(
    settings: Settings,
    status_code: int,
    error_type: type[Exception],
    code: str,
) -> None:
    """Known response codes map without copying private upstream body text."""
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            return_value=httpx.Response(status_code, json={"detail": "private upstream data"})
        )
        client = FreshdeskClient(settings)
        with pytest.raises(error_type) as raised:
            await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert getattr(raised.value, "code") == code
    assert "private upstream data" not in str(raised.value)
    result = ErrorResponse.from_exception(raised.value)  # type: ignore[arg-type]
    assert result.success is False
    assert result.error.code == code


async def test_timeout_is_retried_then_reported(settings: Settings) -> None:
    """Timeouts use bounded retries and never expose transport exception details."""
    settings.max_retries = 1
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            side_effect=httpx.ReadTimeout("sensitive request detail")
        )
        client = FreshdeskClient(settings, sleep=_record_noop)
        with pytest.raises(RequestTimeoutError) as raised:
            await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert route.call_count == 2
    assert "sensitive request detail" not in str(raised.value)


async def test_network_error_is_retried_then_reported(settings: Settings) -> None:
    """Connection errors use the same bounded retry policy."""
    settings.max_retries = 1
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            side_effect=httpx.ConnectError("sensitive transport detail")
        )
        client = FreshdeskClient(settings, sleep=_record_noop)
        with pytest.raises(NetworkConnectionError) as raised:
            await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert route.call_count == 2
    assert "sensitive transport detail" not in str(raised.value)


async def test_invalid_json_response_has_safe_error(settings: Settings) -> None:
    """Non-JSON upstream bodies are rejected without including their contents."""
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            return_value=httpx.Response(200, text="sensitive malformed body")
        )
        client = FreshdeskClient(settings)
        with pytest.raises(InvalidResponseError) as raised:
            await client.list_tickets(ListTicketsInput())
        await client.aclose()

    assert "sensitive malformed body" not in str(raised.value)


def test_settings_require_credentials_outside_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real mode refuses to initialize without an API key and valid domain."""
    from freshdesk_connector.config import Settings
    from freshdesk_connector.errors import ConfigurationError

    for name in (
        "FRESHDESK_DOMAIN",
        "FRESHDESK_API_KEY",
        "FRESHDESK_TIMEOUT_SECONDS",
        "FRESHDESK_MAX_RETRIES",
        "DEMO_MODE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FRESHDESK_DOMAIN", "example-company")
    monkeypatch.setenv("DEMO_MODE", "false")
    with pytest.raises(ConfigurationError):
        Settings.from_env()


async def _record_noop(_delay: float) -> None:
    """Avoid real waits in tests."""
    return None
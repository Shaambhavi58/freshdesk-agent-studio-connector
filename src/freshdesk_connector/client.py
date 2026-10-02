"""Asynchronous, read-only Freshdesk API v2 client."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import ValidationError

from freshdesk_connector.config import Settings
from freshdesk_connector.errors import (
    AuthenticationError,
    FreshdeskError,
    InvalidRequestError,
    InvalidResponseError,
    NetworkConnectionError,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    RetryExhaustedError,
    ServerError,
    TicketNotFoundError,
)
from freshdesk_connector.logging_utils import log_request_attempt
from freshdesk_connector.models import (
    GetTicketInput,
    ListTicketsInput,
    PaginationMetadata,
    SearchTicketsInput,
    TicketDetails,
    TicketDetailsResponse,
    TicketListResponse,
    TicketSearchResponse,
    TicketSummary,
)
from freshdesk_connector.retry import (
    TRANSIENT_STATUS_CODES,
    backoff_seconds,
    retry_after_seconds,
)

SleepFunction = Callable[[float], Awaitable[None]]


class FreshdeskClient:
    """Use Freshdesk API-key authentication for read-only ticket operations."""

    def __init__(
        self,
        settings: Settings,
        *,
        sleep: SleepFunction = asyncio.sleep,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create a client; injectable sleep and transport keep tests deterministic."""
        if not settings.domain or not settings.api_key:
            raise ValueError("A Freshdesk domain and API key are required.")
        self._settings = settings
        self._sleep = sleep
        api_key = settings.api_key.get_secret_value()
        self._client = httpx.AsyncClient(
            base_url=settings.api_base_url,
            auth=(api_key, "X"),
            timeout=httpx.Timeout(settings.timeout_seconds),
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self) -> FreshdeskClient:
        """Support `async with` resource management."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close the underlying HTTP client."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def list_tickets(self, inputs: ListTicketsInput) -> TicketListResponse:
        """List Freshdesk tickets with optional filters and page controls."""
        params = inputs.model_dump(exclude_none=True)
        payload = await self._get_json("/tickets", params=params)
        if not isinstance(payload, list):
            raise InvalidResponseError("Freshdesk returned an invalid ticket list.")
        tickets = self._validate_tickets(payload, TicketSummary)
        return TicketListResponse(
            tickets=tickets,
            pagination=PaginationMetadata(
                page=inputs.page,
                per_page=inputs.per_page,
                has_more=len(tickets) == inputs.per_page,
            ),
        )

    async def get_ticket(self, inputs: GetTicketInput) -> TicketDetailsResponse:
        """Retrieve and normalize one ticket, with a structured not-found error."""
        try:
            payload = await self._get_json(f"/tickets/{inputs.ticket_id}")
        except FreshdeskError as error:
            if error.status_code == 404:
                raise TicketNotFoundError(status_code=404) from None
            raise
        if not isinstance(payload, dict):
            raise InvalidResponseError("Freshdesk returned an invalid ticket.")
        try:
            ticket = TicketDetails.model_validate(payload)
        except ValidationError:
            raise InvalidResponseError("Freshdesk returned an invalid ticket.") from None
        return TicketDetailsResponse(ticket=ticket)

    async def search_tickets(self, inputs: SearchTicketsInput) -> TicketSearchResponse:
        """Search ticket text using Freshdesk's encoded query parameter."""
        payload = await self._get_json(
            "/search/tickets",
            params={"query": f'"{inputs.query}"', "page": inputs.page},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise InvalidResponseError("Freshdesk returned an invalid search response.")
        tickets = self._validate_tickets(payload["results"], TicketSummary)
        total = _nonnegative_int(payload.get("total"))
        page_size = 30
        total_pages = (total + page_size - 1) // page_size if total is not None else None
        has_more = (
            inputs.page < total_pages
            if total_pages is not None
            else len(tickets) == page_size
        )
        return TicketSearchResponse(
            tickets=tickets,
            pagination=PaginationMetadata(
                page=inputs.page,
                per_page=page_size,
                has_more=has_more,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request, retrying only bounded transient failures."""
        total_attempts = self._settings.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            started_at = time.monotonic()
            try:
                response = await self._client.get(path, params=params)
            except httpx.TimeoutException:
                self._log_failure(path, attempt, started_at, "timeout")
                if attempt < total_attempts:
                    await self._sleep(backoff_seconds(attempt))
                    continue
                raise RequestTimeoutError() from None
            except httpx.RequestError:
                self._log_failure(path, attempt, started_at, "network_error")
                if attempt < total_attempts:
                    await self._sleep(backoff_seconds(attempt))
                    continue
                raise NetworkConnectionError() from None

            self._log_response(path, attempt, started_at, response.status_code)
            status = response.status_code
            if status == 429 or status in TRANSIENT_STATUS_CODES:
                if attempt < total_attempts:
                    header = response.headers.get("Retry-After")
                    delay = retry_after_seconds(header)
                    await self._sleep(delay if delay is not None else backoff_seconds(attempt))
                    continue
                if status == 429:
                    raise RateLimitError(status_code=status)
                raise RetryExhaustedError(status_code=status)
            if status >= 500:
                raise ServerError(status_code=status)
            if status == 400:
                raise InvalidRequestError(status_code=status)
            if status == 401:
                raise AuthenticationError(status_code=status)
            if status == 403:
                raise PermissionDeniedError(status_code=status)
            if status == 404:
                raise FreshdeskError(
                    "The requested Freshdesk resource was not found.", status_code=status
                )
            if not 200 <= status < 300:
                raise FreshdeskError(
                    "Freshdesk returned an unsuccessful response.", status_code=status
                )
            try:
                return response.json()
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                raise InvalidResponseError(
                    "Freshdesk returned a response that was not valid JSON.",
                    status_code=status,
                ) from None

        raise RetryExhaustedError()

    def _validate_tickets(
        self,
        payload: list[Any],
        model: type[TicketSummary],
    ) -> list[TicketSummary]:
        """Validate each result without including ticket contents in errors."""
        try:
            return [model.model_validate(item) for item in payload]
        except (ValidationError, TypeError):
            raise InvalidResponseError("Freshdesk returned invalid ticket data.") from None

    @staticmethod
    def _log_response(path: str, attempt: int, started_at: float, status: int) -> None:
        log_request_attempt(
            method="GET",
            path=path,
            status_code=status,
            attempt=attempt,
            duration_ms=(time.monotonic() - started_at) * 1000,
        )

    @staticmethod
    def _log_failure(path: str, attempt: int, started_at: float, kind: str) -> None:
        log_request_attempt(
            method="GET",
            path=path,
            status_code=None,
            attempt=attempt,
            duration_ms=(time.monotonic() - started_at) * 1000,
            error_kind=kind,
        )


def _nonnegative_int(value: Any) -> int | None:
    """Return an integer total when Freshdesk supplies one."""
    if isinstance(value, bool):
        return None
    try:
        integer = int(value)
    except (TypeError, ValueError):
        return None
    return integer if integer >= 0 else None
"""Ticket search query encoding and pagination behavior."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.models import SearchTicketsInput


async def test_search_query_is_encoded_by_httpx(
    freshdesk_client: FreshdeskClient,
) -> None:
    """Search phrases are passed as a parameter, not interpolated into a URL."""
    with respx.mock(assert_all_called=True) as router:
        route = router.get(
            "https://example-company.freshdesk.com/api/v2/search/tickets"
        ).mock(return_value=httpx.Response(200, json={"results": [], "total": 0}))
        result = await freshdesk_client.search_tickets(
            SearchTicketsInput(query="subject:two words & status:2", page=2)
        )

    assert route.calls[0].request.url.params["query"] == '"subject:two words & status:2"'
    assert route.calls[0].request.url.params["page"] == "2"
    assert result.pagination.page == 2
    assert result.pagination.total == 0
    assert result.pagination.has_more is False


def test_search_rejects_whitespace_only_query() -> None:
    """Search input must contain a non-whitespace character."""
    with pytest.raises(ValidationError):
        SearchTicketsInput(query="   ")
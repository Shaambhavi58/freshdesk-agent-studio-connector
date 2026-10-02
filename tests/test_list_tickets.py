"""Ticket list endpoint, filters, pagination, and nullable fields."""

from __future__ import annotations

import httpx
import respx

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.models import ListTicketsInput


async def test_list_tickets_forwards_filters_and_pagination(
    freshdesk_client: FreshdeskClient,
) -> None:
    """All populated list filters are sent to the ticket-list endpoint."""
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://example-company.freshdesk.com/api/v2/tickets").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 123,
                        "subject": "Example issue",
                        "status": 2,
                        "priority": 3,
                        "requester_id": 45,
                        "tags": None,
                        "due_by": None,
                    }
                ],
            )
        )
        result = await freshdesk_client.list_tickets(
            ListTicketsInput(status=2, priority=3, requester_id=45, page=2, per_page=5)
        )

    assert dict(route.calls[0].request.url.params) == {
        "status": "2",
        "priority": "3",
        "requester_id": "45",
        "page": "2",
        "per_page": "5",
    }
    assert result.success is True
    assert result.tickets[0].id == 123
    assert result.tickets[0].tags == []
    assert result.tickets[0].due_by is None
    assert result.pagination.page == 2
    assert result.pagination.per_page == 5
    assert result.pagination.has_more is False


def test_list_input_enforces_page_and_page_size() -> None:
    """Invalid page values are rejected before an HTTP request."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ListTicketsInput(page=0)
    with pytest.raises(ValidationError):
        ListTicketsInput(per_page=101)
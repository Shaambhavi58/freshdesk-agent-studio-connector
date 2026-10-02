"""Single ticket retrieval and not-found behavior."""

from __future__ import annotations

import httpx
import pytest
import respx

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.errors import TicketNotFoundError
from freshdesk_connector.models import GetTicketInput


async def test_get_ticket_returns_complete_normalized_fields(
    freshdesk_client: FreshdeskClient,
) -> None:
    """Ticket details preserve documented fields and tolerate nulls."""
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example-company.freshdesk.com/api/v2/tickets/123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 123,
                    "subject": "Need help",
                    "description_text": "Ticket summary.",
                    "description": "<p>Ticket summary.</p>",
                    "status": 2,
                    "priority": 1,
                    "source": 2,
                    "requester_id": 88,
                    "responder_id": None,
                    "group_id": None,
                    "tags": ["support"],
                    "created_at": "2026-09-01T10:00:00Z",
                    "updated_at": None,
                    "due_by": None,
                    "fr_due_by": None,
                    "requester": {"id": 88, "name": "Riley Example", "email": None},
                    "custom_fields": None,
                    "cc_emails": None,
                    "fwd_emails": None,
                    "reply_cc_emails": None,
                },
            )
        )
        result = await freshdesk_client.get_ticket(GetTicketInput(ticket_id=123))

    assert result.ticket.id == 123
    assert result.ticket.requester is not None
    assert result.ticket.requester.name == "Riley Example"
    assert result.ticket.responder_id is None
    assert result.ticket.custom_fields == {}
    assert result.ticket.cc_emails == []
    assert result.ticket.fwd_emails == []
    assert result.ticket.reply_cc_emails == []


async def test_get_missing_ticket_raises_typed_not_found(
    freshdesk_client: FreshdeskClient,
) -> None:
    """A Freshdesk 404 becomes a safe ticket-specific exception."""
    with respx.mock(assert_all_called=True) as router:
        router.get("https://example-company.freshdesk.com/api/v2/tickets/999").mock(
            return_value=httpx.Response(404, json={"description": "private body"})
        )
        with pytest.raises(TicketNotFoundError) as raised:
            await freshdesk_client.get_ticket(GetTicketInput(ticket_id=999))

    assert raised.value.code == "ticket_not_found"
    assert "private body" not in str(raised.value)
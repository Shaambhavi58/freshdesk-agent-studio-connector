"""Fictional demo-mode list, detail, and search operations."""

from __future__ import annotations

from freshdesk_connector.demo_store import DemoStore
from freshdesk_connector.errors import TicketNotFoundError
from freshdesk_connector.models import GetTicketInput, ListTicketsInput, SearchTicketsInput


async def test_demo_mode_lists_filters_and_paginates() -> None:
    """Demo fixtures support filters and return useful pagination metadata."""
    store = DemoStore.from_fixtures()
    first_page = await store.list_tickets(ListTicketsInput(page=1, per_page=4))
    filtered = await store.list_tickets(ListTicketsInput(status=2, priority=3))

    assert first_page.pagination.total == 12
    assert first_page.pagination.has_more is True
    assert len(first_page.tickets) == 4
    assert len(filtered.tickets) == 1
    assert filtered.tickets[0].id == 84001


async def test_demo_mode_get_and_search() -> None:
    """Demo fixtures support details, requester data, and text search."""
    store = DemoStore.from_fixtures()
    ticket = await store.get_ticket(GetTicketInput(ticket_id=84001))
    matches = await store.search_tickets(SearchTicketsInput(query="invoice"))

    assert ticket.ticket.requester is not None
    assert ticket.ticket.requester.name == "Morgan Lee"
    assert matches.pagination.total == 1
    assert matches.tickets[0].id == 84002


async def test_demo_mode_nonexistent_ticket_is_not_found() -> None:
    """The demo store reports a structured ticket not-found exception."""
    store = DemoStore.from_fixtures()
    try:
        await store.get_ticket(GetTicketInput(ticket_id=99999))
    except TicketNotFoundError as error:
        assert error.code == "ticket_not_found"
    else:
        raise AssertionError("Expected TicketNotFoundError.")


def test_fixture_has_multiple_statuses_priorities_requesters_and_dates() -> None:
    """The example dataset is broad enough to demonstrate useful filters."""
    store = DemoStore.from_fixtures()
    records = store._records

    assert len(records) >= 10
    assert len({record.status for record in records}) >= 4
    assert len({record.priority for record in records}) >= 4
    assert len({record.requester_id for record in records}) >= 8
    assert len({record.created_at for record in records}) >= 10
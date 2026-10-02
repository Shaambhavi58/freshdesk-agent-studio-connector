"""Run the connector's fictional demo operations and print JSON results."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from freshdesk_connector.demo_store import DemoStore
from freshdesk_connector.errors import FreshdeskError
from freshdesk_connector.models import GetTicketInput, ListTicketsInput, SearchTicketsInput


def _format(value: Any) -> str:
    """Serialize Pydantic models as readable, credential-free JSON."""
    return json.dumps(value.model_dump(mode="json"), indent=2, ensure_ascii=False)


async def run_demo() -> None:
    """Demonstrate the same operations exposed by the MCP server."""
    store = DemoStore.from_fixtures()

    print("List tickets (page 1, 3 per page)")
    print(_format(await store.list_tickets(ListTicketsInput(page=1, per_page=3))))

    print("\nFilter tickets (status 2, priority 3)")
    print(_format(await store.list_tickets(ListTicketsInput(status=2, priority=3))))

    print("\nGet ticket 84001")
    print(_format(await store.get_ticket(GetTicketInput(ticket_id=84001))))

    print("\nSearch tickets for 'invoice'")
    print(_format(await store.search_tickets(SearchTicketsInput(query="invoice"))))

    print("\nGet nonexistent ticket 99999")
    try:
        await store.get_ticket(GetTicketInput(ticket_id=99999))
    except FreshdeskError as error:
        print(_format_from_exception(error))


def _format_from_exception(error: FreshdeskError) -> str:
    """Serialize a demo error in the same shape as an MCP tool result."""
    from freshdesk_connector.models import ErrorResponse

    return _format(ErrorResponse.from_exception(error))


if __name__ == "__main__":
    asyncio.run(run_demo())
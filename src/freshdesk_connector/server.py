"""FastMCP server exposing read-only Freshdesk ticket tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field, ValidationError

from freshdesk_connector.client import FreshdeskClient
from freshdesk_connector.config import Settings
from freshdesk_connector.demo_store import DemoStore
from freshdesk_connector.errors import ConfigurationError, FreshdeskError
from freshdesk_connector.logging_utils import configure_logging
from freshdesk_connector.models import (
    ErrorDetail,
    ErrorResponse,
    GetTicketInput,
    ListTicketsInput,
    SearchTicketsInput,
    TicketDetailsResponse,
    TicketListResponse,
    TicketSearchResponse,
)

mcp = FastMCP("Freshdesk Agent Studio Connector")
_service: FreshdeskClient | DemoStore | None = None


def _get_service() -> FreshdeskClient | DemoStore:
    """Create the configured service on first use."""
    global _service
    if _service is None:
        settings = Settings.from_env()
        _service = DemoStore.from_fixtures() if settings.demo_mode else FreshdeskClient(settings)
    return _service


def _configuration_error_response(error: ConfigurationError) -> ErrorResponse:
    """Expose safe configuration errors as typed MCP results."""
    return ErrorResponse.from_exception(error)


@mcp.tool()
async def list_tickets(
    status: Annotated[int | None, Field(ge=1)] = None,
    priority: Annotated[int | None, Field(ge=1)] = None,
    requester_id: Annotated[int | None, Field(ge=1)] = None,
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 30,
) -> TicketListResponse | ErrorResponse:
    """List Freshdesk tickets, optionally filtered by status, priority, and requester."""
    try:
        inputs = ListTicketsInput(
            status=status,
            priority=priority,
            requester_id=requester_id,
            page=page,
            per_page=per_page,
        )
        return await _get_service().list_tickets(inputs)
    except ConfigurationError as error:
        return _configuration_error_response(error)
    except FreshdeskError as error:
        return ErrorResponse.from_exception(error)
    except ValidationError:
        return ErrorResponse(
            error=ErrorDetail(code="invalid_input", message="Ticket list inputs are invalid.")
        )


@mcp.tool()
async def get_ticket(
    ticket_id: Annotated[int, Field(gt=0)],
) -> TicketDetailsResponse | ErrorResponse:
    """Get the complete normalized fields available for one Freshdesk ticket."""
    try:
        inputs = GetTicketInput(ticket_id=ticket_id)
        return await _get_service().get_ticket(inputs)
    except ConfigurationError as error:
        return _configuration_error_response(error)
    except FreshdeskError as error:
        return ErrorResponse.from_exception(error)
    except ValidationError:
        return ErrorResponse(
            error=ErrorDetail(code="invalid_input", message="Ticket ID must be positive.")
        )


@mcp.tool()
async def search_tickets(
    query: Annotated[str, Field(min_length=1, max_length=500)],
    page: Annotated[int, Field(ge=1)] = 1,
) -> TicketSearchResponse | ErrorResponse:
    """Search Freshdesk tickets by their indexed query fields."""
    try:
        inputs = SearchTicketsInput(query=query, page=page)
        return await _get_service().search_tickets(inputs)
    except ConfigurationError as error:
        return _configuration_error_response(error)
    except FreshdeskError as error:
        return ErrorResponse.from_exception(error)
    except ValidationError:
        return ErrorResponse(
            error=ErrorDetail(
                code="invalid_input",
                message="Search query must be non-empty and the page must be positive.",
            )
        )


def main() -> None:
    """Run the MCP server over stdio for local MCP clients."""
    configure_logging()
    try:
        settings = Settings.from_env()
        if settings.demo_mode:
            global _service
            _service = DemoStore.from_fixtures()
        else:
            _service = FreshdeskClient(settings)
    except FreshdeskError as error:
        raise SystemExit(str(error)) from None
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
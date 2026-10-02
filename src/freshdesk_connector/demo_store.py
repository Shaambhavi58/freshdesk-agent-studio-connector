"""Local fictional ticket data implementing the same read-only operations."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from freshdesk_connector.errors import TicketNotFoundError
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


class DemoStore:
    """Read fictional tickets from packaged JSON fixtures without network access."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        """Load and validate in-memory fixture records."""
        self._records = [TicketDetails.model_validate(record) for record in records]

    @classmethod
    def from_fixtures(cls) -> DemoStore:
        """Load the repository's fictional ticket fixture through package resources."""
        source_fixture = (
            Path(__file__).resolve().parents[2] / "fixtures" / "fictional_tickets.json"
        )
        try:
            if source_fixture.is_file():
                fixture_text = source_fixture.read_text(encoding="utf-8")
            else:
                fixture_text = (
                    files("freshdesk_connector")
                    .joinpath("fixtures", "fictional_tickets.json")
                    .read_text(encoding="utf-8")
                )
            records = json.loads(fixture_text)
        except (OSError, json.JSONDecodeError):
            raise RuntimeError("The fictional ticket fixture could not be loaded.") from None
        if not isinstance(records, list):
            raise RuntimeError("The fictional ticket fixture has an invalid format.")
        return cls(records)

    async def list_tickets(self, inputs: ListTicketsInput) -> TicketListResponse:
        """Filter and paginate fictional tickets."""
        matches = [
            record
            for record in self._records
            if (inputs.status is None or record.status == inputs.status)
            and (inputs.priority is None or record.priority == inputs.priority)
            and (inputs.requester_id is None or record.requester_id == inputs.requester_id)
        ]
        start = (inputs.page - 1) * inputs.per_page
        page_records = matches[start : start + inputs.per_page]
        return TicketListResponse(
            tickets=[TicketSummary.model_validate(record.model_dump()) for record in page_records],
            pagination=PaginationMetadata(
                page=inputs.page,
                per_page=inputs.per_page,
                has_more=start + len(page_records) < len(matches),
                total=len(matches),
                total_pages=(len(matches) + inputs.per_page - 1) // inputs.per_page,
            ),
        )

    async def get_ticket(self, inputs: GetTicketInput) -> TicketDetailsResponse:
        """Retrieve one fictional ticket or raise a structured not-found error."""
        for record in self._records:
            if record.id == inputs.ticket_id:
                return TicketDetailsResponse(ticket=record)
        raise TicketNotFoundError()

    async def search_tickets(self, inputs: SearchTicketsInput) -> TicketSearchResponse:
        """Case-insensitively search ticket subjects, descriptions, and tags."""
        query = inputs.query.casefold()
        matches = [
            record
            for record in self._records
            if query
            in " ".join(
                [
                    record.subject or "",
                    record.description_text or "",
                    record.description or "",
                    *record.tags,
                ]
            ).casefold()
        ]
        page_size = 30
        start = (inputs.page - 1) * page_size
        page_records = matches[start : start + page_size]
        return TicketSearchResponse(
            tickets=[TicketSummary.model_validate(record.model_dump()) for record in page_records],
            pagination=PaginationMetadata(
                page=inputs.page,
                per_page=page_size,
                has_more=start + len(page_records) < len(matches),
                total=len(matches),
                total_pages=(len(matches) + page_size - 1) // page_size,
            ),
        )
"""Validated inputs and normalized MCP tool outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from freshdesk_connector.errors import FreshdeskError


class ListTicketsInput(BaseModel):
    """Validated filters and pagination for listing tickets."""

    model_config = ConfigDict(extra="forbid")

    status: int | None = Field(default=None, ge=1)
    priority: int | None = Field(default=None, ge=1)
    requester_id: int | None = Field(default=None, ge=1)
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=30, ge=1, le=100)


class GetTicketInput(BaseModel):
    """Validated input for retrieving a single ticket."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: int = Field(gt=0)


class SearchTicketsInput(BaseModel):
    """Validated query and pagination for ticket search."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    page: int = Field(default=1, ge=1)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        """Reject strings that contain only whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must contain non-whitespace characters.")
        return cleaned


class RequesterInfo(BaseModel):
    """Requester fields returned when Freshdesk includes them."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str | None = None
    email: str | None = None


class TicketSummary(BaseModel):
    """Normalized, compact view of a Freshdesk ticket."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)
    subject: str | None = None
    description_text: str | None = None
    status: int | None = None
    priority: int | None = None
    source: int | None = None
    requester_id: int | None = None
    responder_id: int | None = None
    group_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    due_by: str | None = None
    fr_due_by: str | None = None
    requester: RequesterInfo | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        """Normalize missing or nullable Freshdesk tags."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(tag) for tag in value]
        return []


class TicketDetails(TicketSummary):
    """Normalized ticket with additional detail fields where available."""

    description: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    cc_emails: list[str] = Field(default_factory=list)
    fwd_emails: list[str] = Field(default_factory=list)
    reply_cc_emails: list[str] = Field(default_factory=list)
    email_config_id: int | None = None
    is_escalated: bool | None = None
    spam: bool | None = None

    @field_validator("custom_fields", mode="before")
    @classmethod
    def normalize_custom_fields(cls, value: Any) -> dict[str, Any]:
        """Normalize missing or nullable custom fields."""
        return value if isinstance(value, dict) else {}

    @field_validator("cc_emails", "fwd_emails", "reply_cc_emails", mode="before")
    @classmethod
    def normalize_email_lists(cls, value: Any) -> list[str]:
        """Normalize nullable email lists while preserving available values."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(email) for email in value]
        return []


class PaginationMetadata(BaseModel):
    """Pagination details returned with list and search results."""

    page: int = Field(ge=1)
    per_page: int = Field(ge=1)
    has_more: bool
    total: int | None = Field(default=None, ge=0)
    total_pages: int | None = Field(default=None, ge=0)


class TicketListResponse(BaseModel):
    """Successful response from `list_tickets`."""

    success: Literal[True] = True
    tickets: list[TicketSummary]
    pagination: PaginationMetadata


class TicketDetailsResponse(BaseModel):
    """Successful response from `get_ticket`."""

    success: Literal[True] = True
    ticket: TicketDetails


class TicketSearchResponse(BaseModel):
    """Successful response from `search_tickets`."""

    success: Literal[True] = True
    tickets: list[TicketSummary]
    pagination: PaginationMetadata


class ErrorDetail(BaseModel):
    """Safe structured error data; never contains upstream response bodies."""

    code: str
    message: str
    status_code: int | None = None


class ErrorResponse(BaseModel):
    """Structured MCP tool error response."""

    success: Literal[False] = False
    error: ErrorDetail

    @classmethod
    def from_exception(cls, error: FreshdeskError) -> ErrorResponse:
        """Map internal exceptions to safe tool output."""
        return cls(
            error=ErrorDetail(
                code=error.code,
                message=str(error),
                status_code=error.status_code,
            )
        )
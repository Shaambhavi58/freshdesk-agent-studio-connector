"""Safe, typed errors raised by the Freshdesk client and returned by MCP tools."""

from __future__ import annotations

from typing import Literal


class FreshdeskError(Exception):
    """Base class for connector errors with a safe, user-facing message."""

    code = "freshdesk_error"
    safe_message = "The Freshdesk request could not be completed."

    def __init__(self, message: str | None = None, *, status_code: int | None = None) -> None:
        """Create an error without retaining response bodies or credentials."""
        self.status_code = status_code
        super().__init__(message or self.safe_message)


class ConfigurationError(FreshdeskError):
    """Raised when required connector configuration is invalid or missing."""

    code = "configuration_error"
    safe_message = "Freshdesk configuration is missing or invalid."


class InvalidRequestError(FreshdeskError):
    """Raised when Freshdesk rejects a request as invalid."""

    code = "invalid_request"
    safe_message = "Freshdesk rejected the request as invalid."


class AuthenticationError(FreshdeskError):
    """Raised when Freshdesk rejects API-key authentication."""

    code = "authentication_failed"
    safe_message = "Freshdesk authentication failed. Verify the configured credentials."


class PermissionDeniedError(FreshdeskError):
    """Raised when the Freshdesk account lacks permission for an operation."""

    code = "permission_denied"
    safe_message = "Freshdesk denied access to this operation."


class TicketNotFoundError(FreshdeskError):
    """Raised when the requested ticket does not exist or is not visible."""

    code = "ticket_not_found"
    safe_message = "The requested ticket was not found."


class RateLimitError(FreshdeskError):
    """Raised when the Freshdesk rate limit remains active after retries."""

    code = "rate_limited"
    safe_message = "Freshdesk continued rate-limiting the request after bounded retries."


class ServerError(FreshdeskError):
    """Raised for non-retryable or otherwise unsuccessful Freshdesk server responses."""

    code = "server_error"
    safe_message = "Freshdesk returned a server error."


class RetryExhaustedError(FreshdeskError):
    """Raised after all bounded retries of a transient server response are used."""

    code = "retry_exhausted"
    safe_message = "Freshdesk requests continued to fail after bounded retries."


class NetworkConnectionError(FreshdeskError):
    """Raised when Freshdesk cannot be reached after bounded retries."""

    code = "network_error"
    safe_message = "Could not connect to Freshdesk after bounded retries."


class RequestTimeoutError(FreshdeskError):
    """Raised when Freshdesk requests time out after bounded retries."""

    code = "request_timeout"
    safe_message = "Freshdesk requests timed out after bounded retries."


class InvalidResponseError(FreshdeskError):
    """Raised when Freshdesk returns a response that cannot be safely parsed."""

    code = "invalid_response"
    safe_message = "Freshdesk returned an invalid response."


ErrorCode = Literal[
    "configuration_error",
    "invalid_request",
    "authentication_failed",
    "permission_denied",
    "ticket_not_found",
    "rate_limited",
    "server_error",
    "retry_exhausted",
    "network_error",
    "request_timeout",
    "invalid_response",
    "freshdesk_error",
]
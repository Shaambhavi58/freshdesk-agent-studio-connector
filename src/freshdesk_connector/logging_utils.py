"""Structured request logging that excludes credentials and ticket contents."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "freshdesk_connector.http"


def configure_logging() -> None:
    """Configure stderr logging for MCP stdio compatibility."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(message)s",
    )


def log_request_attempt(
    *,
    method: str,
    path: str,
    status_code: int | None,
    attempt: int,
    duration_ms: float,
    error_kind: str | None = None,
) -> None:
    """Log only safe request metadata, never URLs with queries or payloads."""
    record: dict[str, Any] = {
        "event": "freshdesk_http_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "attempt": attempt,
        "duration_ms": round(duration_ms, 2),
    }
    if error_kind:
        record["error_kind"] = error_kind
    logging.getLogger(LOGGER_NAME).info(json.dumps(record, separators=(",", ":")))
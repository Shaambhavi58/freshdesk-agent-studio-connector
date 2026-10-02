"""Environment-backed, validated connector configuration."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from freshdesk_connector.errors import ConfigurationError

_DOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


class Settings(BaseModel):
    """Validated Freshdesk and runtime settings.

    The API key is stored as a Pydantic secret so model representations do not
    reveal it.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    domain: str | None = None
    api_key: SecretStr | None = Field(default=None, repr=False)
    timeout_seconds: float = Field(default=15.0, gt=0, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    demo_mode: bool = False

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_and_validate_domain(cls, value: Any) -> str | None:
        """Accept a Freshdesk subdomain, not an arbitrary URL or host."""
        if value is None:
            return None
        domain = str(value).strip().lower()
        if not domain:
            return None
        if not _DOMAIN_PATTERN.fullmatch(domain):
            raise ValueError("FRESHDESK_DOMAIN must be a Freshdesk subdomain.")
        return domain

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: Any) -> Any:
        """Treat an empty environment value as an absent credential."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value.strip() if isinstance(value, str) else value

    @classmethod
    def from_env(cls) -> Settings:
        """Load `.env` without overriding process environment values."""
        load_dotenv(override=False)
        demo_mode = _parse_bool(os.getenv("DEMO_MODE", "false"), "DEMO_MODE")
        try:
            settings = cls(
                domain=os.getenv("FRESHDESK_DOMAIN"),
                api_key=os.getenv("FRESHDESK_API_KEY"),
                timeout_seconds=os.getenv("FRESHDESK_TIMEOUT_SECONDS", "15"),
                max_retries=os.getenv("FRESHDESK_MAX_RETRIES", "3"),
                demo_mode=demo_mode,
            )
        except (ValueError, TypeError) as exc:
            raise ConfigurationError("Freshdesk configuration is invalid.") from exc

        if not settings.demo_mode and (not settings.domain or not settings.api_key):
            raise ConfigurationError(
                "Set FRESHDESK_DOMAIN and FRESHDESK_API_KEY, or enable DEMO_MODE."
            )
        return settings

    @property
    def api_base_url(self) -> str:
        """Return the API v2 URL after validating the tenant subdomain."""
        if not self.domain:
            raise ConfigurationError("FRESHDESK_DOMAIN is required outside demo mode.")
        return f"https://{self.domain}.freshdesk.com/api/v2"


def _parse_bool(value: str, name: str) -> bool:
    """Parse common environment boolean values without silent coercion."""
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(f"{name} must be true or false.")
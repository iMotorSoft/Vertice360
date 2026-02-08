"""Simple registry utilities for WhatsApp providers."""

from __future__ import annotations

from typing import Literal

ProviderName = Literal["meta", "gupshup"]


def normalize_provider(value: str | None) -> ProviderName:
    """Normalize provider input, defaulting to 'meta'."""
    if not value:
        return "meta"
    cleaned = value.strip().lower()
    return "gupshup" if cleaned == "gupshup" else "meta"


def validate_provider(value: str | None, default: ProviderName = "meta") -> ProviderName:
    """Validate provider name, falling back to the given default."""
    if not value:
        return default
    cleaned = value.strip().lower()
    if cleaned in ("meta", "gupshup"):
        return cleaned  # type: ignore[return-value]
    return default

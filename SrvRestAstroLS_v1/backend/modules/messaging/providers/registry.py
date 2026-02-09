"""Simple registry utilities for WhatsApp providers."""

from __future__ import annotations

from typing import Literal

ProviderName = Literal["meta", "gupshup"]


def normalize_provider(value: str | None) -> ProviderName:
    """Normalize provider input, defaulting to 'meta'."""
    if not value:
        return "meta"
    cleaned = value.strip().lower()
    if cleaned in ("gupshup", "gupshup_whatsapp", "gs"):
        return "gupshup"
    if cleaned in ("meta", "meta_whatsapp", "wa_meta"):
        return "meta"
    return "meta"


def validate_provider(value: str | None, default: ProviderName = "meta") -> ProviderName:
    """Validate provider name, falling back to the given default."""
    if not value:
        return default
    cleaned = value.strip().lower()
    if cleaned in ("meta", "meta_whatsapp", "wa_meta"):
        return "meta"
    if cleaned in ("gupshup", "gupshup_whatsapp", "gs"):
        return "gupshup"
    return default

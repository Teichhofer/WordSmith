"""Shared default values and normalisation helpers for user inputs."""

from __future__ import annotations

DEFAULT_AUDIENCE: str = "Allgemeine Leserschaft mit Grundkenntnissen"
DEFAULT_TONE: str = "sachlich-lebendig"
DEFAULT_REGISTER: str = "Sie"
DEFAULT_VARIANT: str = "DE-DE"
DEFAULT_CONSTRAINTS: str = "Keine zusätzlichen Vorgaben"
DEFAULT_SOURCES_ALLOWED: bool = False

# Normalisation map for register values used by CLI and the writer agent.
REGISTER_ALIASES: dict[str, str] = {
    "sie": "Sie",
    "du": "Du",
}

# Supported language variants.
VALID_VARIANTS: set[str] = {"DE-DE", "DE-AT", "DE-CH"}

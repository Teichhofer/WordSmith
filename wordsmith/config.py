"""Configuration management for the WordSmith automatikmodus."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_LLM_PROVIDER: str = "ollama"


class ConfigError(Exception):
    """Raised when the configuration could not be loaded or validated."""


@dataclass
class LLMParameters:
    """Deterministic model parameters for reproducible text generation."""

    temperature: float = 0.2
    top_p: float = 0.9
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.3
    seed: Optional[int] = 42

    def update(self, values: Dict[str, Any]) -> None:
        """Update the stored parameters with validated values."""

        for key, value in values.items():
            if not hasattr(self, key):
                raise ConfigError(f"Unbekannter LLM-Parameter: {key}")
            if key == "seed":
                setattr(self, key, None if value is None else int(value))
            else:
                setattr(self, key, float(value))


@dataclass
class Config:
    """Application configuration loaded by the CLI."""

    output_dir: Path = Path("output")
    logs_dir: Path = Path("logs")
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm: LLMParameters = field(default_factory=LLMParameters)
    context_length: int = 4096
    token_limit: int = 1024
    system_prompt: str = (
        "Du bist ein präziser deutschsprachiger Fachtexter. Du erfindest "
        "keine Fakten. Bei fehlenden Daten nutzt du Platzhalter in eckigen "
        "Klammern. Deine Texte sind klar strukturiert, aktiv formuliert, "
        "redundanzarm und adressatengerecht."
    )
    word_count: int = 0

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.logs_dir = Path(self.logs_dir)
        self.ensure_directories()

    def adjust_for_word_count(self, word_count: int) -> None:
        """Store the desired word count and ensure it is sensible."""

        if word_count <= 0:
            raise ConfigError("`word_count` muss größer als 0 sein.")

        self.word_count = int(word_count)

        # Scale context length and token limits with a safety buffer to
        # accommodate prompts, intermediate artefacts and the final text.
        self.context_length = max(2048, int(self.word_count * 4))
        self.token_limit = max(512, int(self.word_count * 1.6))

        # Ensure deterministic generation parameters for reproducible runs.
        self.llm.temperature = 0.2
        self.llm.top_p = 0.9
        self.llm.presence_penalty = 0.0
        self.llm.frequency_penalty = 0.3
        if hasattr(self.llm, "seed"):
            self.llm.seed = 42

    def ensure_directories(self) -> None:
        """Create output and log directories if they do not exist."""

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


def _update_config_from_dict(config: Config, data: Dict[str, Any]) -> None:
    """Merge a dictionary of values into the configuration instance."""

    for key, value in data.items():
        if key in {"output_dir", "logs_dir"}:
            setattr(config, key, Path(str(value)))
        elif key == "llm_provider":
            config.llm_provider = str(value)
        elif key == "system_prompt":
            config.system_prompt = str(value)
        elif key == "context_length":
            config.context_length = int(value)
        elif key == "token_limit":
            config.token_limit = int(value)
        elif key == "llm":
            if not isinstance(value, dict):
                raise ConfigError("LLM-Einstellungen müssen ein Objekt sein.")
            config.llm.update(value)
        else:
            raise ConfigError(f"Unbekannter Konfigurationsschlüssel: {key}")

    config.ensure_directories()


def load_config(path: Optional[str | Path] = None) -> Config:
    """Load configuration data from disk or return defaults."""

    config = Config()
    if path is None:
        return config

    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Konfigurationsdatei '{config_path}' wurde nicht gefunden.")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Konfiguration konnte nicht gelesen werden: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Konfigurationsdatei muss ein JSON-Objekt enthalten.")

    _update_config_from_dict(config, data)
    return config

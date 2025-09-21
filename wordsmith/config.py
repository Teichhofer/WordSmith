"""Configuration management for the WordSmith automatikmodus."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_LLM_PROVIDER: str = "ollama"
OLLAMA_TIMEOUT_SECONDS: int = 3600

MIN_CONTEXT_LENGTH: int = 2048
MIN_TOKEN_LIMIT: int = 1024


TEMPORARY_OUTPUT_PATTERNS: tuple[str, ...] = (
    "briefing.json",
    "idea.txt",
    "outline.txt",
    "source_research.json",
    "current_text.txt",
    "text_type_check.txt",
    "text_type_fix.txt",
    "iteration_*.txt",
    "reflection_*.txt",
)


class ConfigError(Exception):
    """Raised when the configuration could not be loaded or validated."""


@dataclass
class LLMParameters:
    """Deterministic model parameters for reproducible text generation."""

    temperature: float = 0.7
    top_p: float = 1.0
    presence_penalty: float = 0.05
    frequency_penalty: float = 0.05
    seed: Optional[int] = 42
    num_predict: Optional[int] = None

    def update(self, values: Dict[str, Any]) -> None:
        """Update the stored parameters with validated values."""

        for key, value in values.items():
            if not hasattr(self, key):
                raise ConfigError(f"Unbekannter LLM-Parameter: {key}")
            if key in {"seed", "num_predict"}:
                setattr(self, key, None if value is None else int(value))
            else:
                setattr(self, key, float(value))


@dataclass
class Config:
    """Application configuration loaded by the CLI."""

    output_dir: Path = Path("output")
    logs_dir: Path = Path("logs")
    prompt_config_path: Path = Path(__file__).with_name("prompts_config.json")
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    llm: LLMParameters = field(default_factory=LLMParameters)
    context_length: int = 4096
    token_limit: int = 1024
    system_prompt: Optional[str] = None
    word_count: int = 0
    source_search_query_count: int = 3

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.logs_dir = Path(self.logs_dir)
        self.prompt_config_path = Path(self.prompt_config_path)
        self.ensure_directories()
        self._apply_minimum_limits()
        if self.source_search_query_count < 0:
            raise ConfigError("`source_search_query_count` darf nicht negativ sein.")

    def adjust_for_word_count(self, word_count: int) -> None:
        """Store the desired word count and ensure it is sensible."""

        if word_count <= 0:
            raise ConfigError("`word_count` muss größer als 0 sein.")

        self.word_count = int(word_count)

        # Scale context length and token limits with a safety buffer to
        # accommodate prompts, intermediate artefacts and the final text.
        self.context_length = max(8192, int(self.word_count * 4))
        self.token_limit = max(8192, int(self.word_count * 1.9))
        self._apply_minimum_limits()

        # Ensure deterministic generation parameters for reproducible runs.
        self.llm.temperature = 0.7
        self.llm.top_p = 1.0
        self.llm.presence_penalty = 0.05
        self.llm.frequency_penalty = 0.05
        if hasattr(self.llm, "seed"):
            self.llm.seed = 42
        if hasattr(self.llm, "num_predict"):
            self.llm.num_predict = self.token_limit

    def ensure_directories(self) -> None:
        """Create output and log directories if they do not exist."""

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_temporary_outputs(self) -> None:
        """Delete transient artefacts from previous runs in the output directory."""

        for pattern in TEMPORARY_OUTPUT_PATTERNS:
            for path in self.output_dir.glob(pattern):
                if path.is_file():
                    try:
                        path.unlink()
                    except FileNotFoundError:  # pragma: no cover - defensive
                        continue

    def _apply_minimum_limits(self) -> None:
        """Ensure configured context and generation windows meet minimum sizes."""

        self.context_length = max(MIN_CONTEXT_LENGTH, int(self.context_length))
        self.token_limit = max(MIN_TOKEN_LIMIT, int(self.token_limit))


def _update_config_from_dict(config: Config, data: Dict[str, Any]) -> None:
    """Merge a dictionary of values into the configuration instance."""

    for key, value in data.items():
        if key in {"output_dir", "logs_dir"}:
            setattr(config, key, Path(str(value)))
        elif key == "llm_provider":
            config.llm_provider = str(value)
        elif key == "llm_model":
            config.llm_model = str(value) if value is not None else None
        elif key == "ollama_base_url":
            config.ollama_base_url = str(value) if value is not None else None
        elif key == "prompt_config_path":
            config.prompt_config_path = Path(str(value))
        elif key == "system_prompt":
            if value is None:
                config.system_prompt = None
            else:
                cleaned = str(value).strip()
                config.system_prompt = cleaned or None
        elif key == "context_length":
            config.context_length = int(value)
        elif key == "token_limit":
            config.token_limit = int(value)
        elif key == "llm":
            if not isinstance(value, dict):
                raise ConfigError("LLM-Einstellungen müssen ein Objekt sein.")
            config.llm.update(value)
        elif key == "source_search_query_count":
            count = int(value)
            if count < 0:
                raise ConfigError("`source_search_query_count` darf nicht negativ sein.")
            config.source_search_query_count = count
        else:
            raise ConfigError(f"Unbekannter Konfigurationsschlüssel: {key}")

    config.ensure_directories()
    config._apply_minimum_limits()


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

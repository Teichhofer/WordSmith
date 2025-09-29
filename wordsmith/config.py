"""Configuration management for the WordSmith automatikmodus."""

from __future__ import annotations

import json
from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


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
    num_predict: Optional[int] = 900
    num_ctx: Optional[int] = None
    stop: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Track user-provided overrides so stage prompts can respect them.
        if not hasattr(self, "_overrides"):
            self._overrides: set[str] = set()
        self.stop = self._normalise_stop(self.stop)
        self._record_initial_overrides()

    def _record_initial_overrides(self) -> None:
        """Mark constructor arguments that differ from defaults as overrides."""

        for field_definition in fields(self):
            name = field_definition.name
            if name.startswith("_"):
                continue
            default = field_definition.default
            if default is MISSING and field_definition.default_factory is not MISSING:
                default = field_definition.default_factory()
            if default is MISSING:
                # No sensible default available (should not occur for our fields).
                continue
            current = getattr(self, name)
            if current != default:
                self._overrides.add(name)

    def update(self, values: Dict[str, Any]) -> None:
        """Update the stored parameters with validated values."""

        for key, value in values.items():
            if key == "max_tokens":
                normalised_key = "num_predict"
            elif key in {"context_length", "num_ctx"}:
                normalised_key = "num_ctx"
            else:
                normalised_key = key
            if not hasattr(self, normalised_key):
                raise ConfigError(f"Unbekannter LLM-Parameter: {key}")
            if normalised_key == "seed":
                setattr(
                    self,
                    normalised_key,
                    None if value is None else int(value),
                )
            elif normalised_key in {"num_predict", "num_ctx"}:
                setattr(
                    self,
                    normalised_key,
                    None if value is None else int(value),
                )
            elif normalised_key == "stop":
                self.stop = self._normalise_stop(value)
            else:
                setattr(self, normalised_key, float(value))
            self._overrides.add(normalised_key)

    def has_override(self, key: str) -> bool:
        """Return ``True`` when the value was explicitly provided by the user."""

        return key in self._overrides

    @staticmethod
    def _normalise_stop(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            cleaned = value.strip()
            return (cleaned,) if cleaned else ()
        if isinstance(value, Sequence):
            stops: list[str] = []
            for entry in value:
                if entry is None:
                    continue
                cleaned = str(entry).strip()
                if cleaned:
                    stops.append(cleaned)
            return tuple(stops)
        raise ConfigError(
            "LLM-Stop-Sequenzen müssen als String oder Liste von Strings angegeben werden."
        )


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
        if hasattr(self.llm, "num_ctx") and not self.llm.has_override("num_ctx"):
            self.llm.num_ctx = self.context_length
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

        # Ensure deterministic generation parameters for reproducible runs while
        # respecting configurable sampling controls.
        self.llm.presence_penalty = 0.05
        self.llm.frequency_penalty = 0.05
        if hasattr(self.llm, "seed"):
            self.llm.seed = 42
        if hasattr(self.llm, "num_predict") and not self.llm.has_override("num_predict"):
            self.llm.num_predict = self.token_limit
        if hasattr(self.llm, "num_ctx") and not self.llm.has_override("num_ctx"):
            self.llm.num_ctx = self.context_length

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
        if hasattr(self.llm, "num_ctx") and not self.llm.has_override("num_ctx"):
            self.llm.num_ctx = self.context_length


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

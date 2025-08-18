from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging



@dataclass
class Config:
    """Configuration options for the writing agent."""

    log_dir: Path = Path("logs")
    output_dir: Path = Path("output")
    log_level: int = logging.INFO
    log_file: str = "run.log"
    llm_provider: str = "stub"
    model: str = "gpt-3.5-turbo"
    openai_api_key: str | None = None
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    ollama_url: str = "http://192.168.100.148:11434/api/generate"

    def ensure_dirs(self) -> None:
        """Create directories referenced in the configuration."""
        self.log_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)


# Default configuration used by the application.
DEFAULT_CONFIG = Config()

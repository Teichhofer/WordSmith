from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging



@dataclass
class Config:
    """Configuration options for the writing agent."""

    log_dir: Path = Path("logs")
    output_dir: Path = Path("output")
    output_file: str = "current_text.txt"
    outline_file: str = "outline.txt"
    auto_iteration_file_template: str = "iteration_{:02d}.txt"
    log_level: int = logging.INFO
    log_file: str = "run.log"
    llm_log_file: str = "llm.log"
    log_encoding: str = "utf-8"
    llm_provider: str = "stub"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    context_length: int = 2048
    max_tokens: int = 256
    auto_ctx_multiplier: int = 4
    auto_token_multiplier: int = 4
    openai_api_key: str | None = None
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    ollama_url: str = "http://192.168.100.148:11434/api/generate"
    ollama_list_url: str = "http://192.168.100.148:11434/api/tags"

    def ensure_dirs(self) -> None:
        """Create directories referenced in the configuration."""
        self.log_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

    def adjust_for_word_count(self, word_count: int) -> None:
        """Adjust context and token limits for automatic mode.

        The ``word_count`` defines the desired length of the story. To give the
        language model enough room for context and generation we scale the
        configuration based on this value.
        """
        self.context_length = word_count * self.auto_ctx_multiplier
        self.max_tokens = word_count * self.auto_token_multiplier


# Default configuration used by the application.
DEFAULT_CONFIG = Config()

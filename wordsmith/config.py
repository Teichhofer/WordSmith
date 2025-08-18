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

    def ensure_dirs(self) -> None:
        """Create directories referenced in the configuration."""
        self.log_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)


# Default configuration used by the application.
DEFAULT_CONFIG = Config()

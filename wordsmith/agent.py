from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List

from .config import Config, DEFAULT_CONFIG


@dataclass
class Step:
    """Description of a single writing step."""

    task: str


class WriterAgent:
    """A very small placeholder writing agent.

    The agent is intentionally simple – it merely appends sentences based on the
    step's task and the given topic. The goal of the project is to provide the
    scaffolding for an iterative writing workflow rather than sophisticated
    natural language generation.
    """

    def __init__(
        self,
        topic: str,
        word_count: int,
        steps: Iterable[Step],
        iterations: int,
        config: Config | None = None,
    ) -> None:
        self.topic = topic
        self.word_count = word_count
        self.steps: List[Step] = list(steps)
        self.iterations = iterations
        self.config = config or DEFAULT_CONFIG

        self.config.ensure_dirs()

        logging.basicConfig(
            filename=self.config.log_dir / self.config.log_file,
            level=self.config.log_level,
            format="%(asctime)s - %(message)s",
            force=True,
        )
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    def run(self) -> str:
        """Execute the writing process and return the final text."""

        text: List[str] = []
        for step_index, step in enumerate(self.steps, start=1):
            for iteration in range(1, self.iterations + 1):
                addition = self._generate(step.task, iteration)
                text.append(addition)
                current_text = " ".join(text)
                self._save_text(current_text)
                self.logger.info(
                    "step %s/%s iteration %s/%s: %s",
                    step_index,
                    len(self.steps),
                    iteration,
                    self.iterations,
                    addition,
                )

        final_text = " ".join(text)
        # Truncate to desired word count.
        words = final_text.split()
        if len(words) > self.word_count:
            final_text = " ".join(words[: self.word_count])
        self._save_text(final_text)
        return final_text

    # ------------------------------------------------------------------
    def _generate(self, task: str, iteration: int) -> str:
        """Naive text generation used as a placeholder for an LLM.

        In a real project this method would call an actual language model. To
        keep the project self-contained, we generate deterministic sentences
        instead.
        """

        return f"{task.capitalize()} about {self.topic}. (iteration {iteration})"

    # ------------------------------------------------------------------
    def _save_text(self, text: str) -> None:
        # Ensure a trailing newline so the shell prompt does not run into the
        # file contents when viewed with ``cat``.
        (self.config.output_dir / "current_text.txt").write_text(
            text + "\n", encoding="utf8"
        )

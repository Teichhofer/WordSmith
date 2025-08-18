from __future__ import annotations

import json
import logging
import os
import urllib.request
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
        """Generate text using the configured language model.

        The default implementation preserves the previous deterministic
        behaviour. When ``Config.llm_provider`` is set to ``"ollama"`` or
        ``"openai"`` the respective HTTP API is called instead.
        """

        prompt = f"{task} about {self.topic}"

        if self.config.llm_provider == "ollama":
            data = json.dumps(
                {
                    "model": self.config.model,
                    "prompt": prompt,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_ctx": self.config.context_length,
                    },
                }
            ).encode("utf8")
            req = urllib.request.Request(
                self.config.ollama_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
                payload = json.loads(resp.read().decode("utf8"))
            return payload.get("response", "").strip()

        if self.config.llm_provider == "openai":
            api_key = self.config.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            data = json.dumps(
                {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.context_length,
                }
            ).encode("utf8")
            req = urllib.request.Request(self.config.openai_url, data=data, headers=headers)
            with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
                payload = json.loads(resp.read().decode("utf8"))
            return payload["choices"][0]["message"]["content"].strip()

        return f"{task.capitalize()} about {self.topic}. (iteration {iteration})"

    # ------------------------------------------------------------------
    def _save_text(self, text: str) -> None:
        # Ensure a trailing newline so the shell prompt does not run into the
        # file contents when viewed with ``cat``.
        (self.config.output_dir / self.config.output_file).write_text(
            text + "\n", encoding="utf8"
        )

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
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

        # System prompt derived from the user's topic. This is attached to every
        # LLM request so that the model understands the overall context of the
        # writing task.
        self.system_prompt = (
            f"You are a helpful writing assistant focused on {self.topic}."
        )

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
            # Ask the LLM for an optimal prompt for this step before running any
            # iterations.
            prompt = self._craft_prompt(step.task)
            for iteration in range(1, self.iterations + 1):
                current_text = " ".join(text)
                start = time.perf_counter()
                addition = self._generate(prompt, current_text, iteration)
                elapsed = time.perf_counter() - start
                tokens = len(addition.split())
                tok_per_sec = tokens / (elapsed or 1e-8)
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
                print(
                    f"step {step_index}/{len(self.steps)} iteration {iteration}/{self.iterations}: "
                    f"{tokens} tokens ({tok_per_sec:.2f} tok/s)",
                    flush=True,
                )

        final_text = " ".join(text)
        # Truncate to desired word count.
        words = final_text.split()
        if len(words) > self.word_count:
            final_text = " ".join(words[: self.word_count])
        self._save_text(final_text)
        return final_text

    # ------------------------------------------------------------------
    def _craft_prompt(self, task: str) -> str:
        """Ask the LLM to craft an optimal prompt for the given task."""

        meta_prompt = (
            f"Provide an optimal prompt to accomplish: {task} about {self.topic}."
        )
        fallback = f"{task} about {self.topic}"
        return self._call_llm(meta_prompt, fallback=fallback)

    # ------------------------------------------------------------------
    def _generate(self, prompt: str, current_text: str, iteration: int) -> str:
        """Generate text for ``prompt`` given the current text state."""

        user_prompt = (
            f"{prompt}\n\nCurrent text:\n{current_text}\n\nNext part:"
        )
        fallback = f"{prompt}. (iteration {iteration})"
        return self._call_llm(user_prompt, fallback=fallback)

    # ------------------------------------------------------------------
    def _call_llm(self, prompt: str, *, fallback: str) -> str:
        """Internal helper to call the configured language model."""

        full_prompt = f"{self.system_prompt}\n\n{prompt}".strip()

        if self.config.llm_provider == "ollama":
            data = json.dumps(
                {
                    "model": self.config.model,
                    "prompt": full_prompt,
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
            try:
                with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
                    payload = json.loads(resp.read().decode("utf8"))
                return payload.get("response", "").strip()
            except urllib.error.URLError as exc:
                self.logger.error("ollama request failed: %s", exc)
                return fallback

        if self.config.llm_provider == "openai":
            api_key = self.config.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            data = json.dumps(
                {
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.context_length,
                }
            ).encode("utf8")
            req = urllib.request.Request(self.config.openai_url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
                    payload = json.loads(resp.read().decode("utf8"))
                return payload["choices"][0]["message"]["content"].strip()
            except urllib.error.URLError as exc:
                self.logger.error("openai request failed: %s", exc)
                return fallback

        return fallback

    # ------------------------------------------------------------------
    def _save_text(self, text: str) -> None:
        # Ensure a trailing newline so the shell prompt does not run into the
        # file contents when viewed with ``cat``.
        (self.config.output_dir / self.config.output_file).write_text(
            text + "\n", encoding="utf8"
        )

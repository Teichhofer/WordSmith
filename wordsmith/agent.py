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
from . import prompts


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
        content: str = "",
        text_type: str = "Text",
    ) -> None:
        self.topic = topic
        self.word_count = word_count
        self.steps: List[Step] = list(steps)
        self.iterations = iterations
        self.config = config or DEFAULT_CONFIG
        self.content = content
        self.text_type = text_type

        self.config.ensure_dirs()

        # System prompt derived from the user's topic. This is attached to every
        # LLM request so that the model understands the overall context of the
        # writing task.
        self.system_prompt = prompts.SYSTEM_PROMPT.format(
            topic=self.topic, text_type=self.text_type
        )

        logging.basicConfig(
            filename=self.config.log_dir / self.config.log_file,
            level=self.config.log_level,
            format="%(asctime)s - %(message)s",
            encoding=self.config.log_encoding,
            force=True,
        )
        self.logger = logging.getLogger(__name__)

        llm_handler = logging.FileHandler(
            self.config.log_dir / self.config.llm_log_file,
            encoding=self.config.log_encoding,
        )
        llm_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        llm_handler.setLevel(self.config.log_level)
        self.llm_logger = logging.getLogger(f"{__name__}.llm")
        self.llm_logger.addHandler(llm_handler)
        self.llm_logger.propagate = False

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
    def run_auto(self) -> str:
        """Automatically generate a story over multiple iterations.

        Only the title, desired content and number of iterations are
        required. In the first iteration the agent uses a predefined prompt
        based on these inputs. In later iterations it first asks the LLM for
        the next prompt to use and then generates the subsequent text.
        """

        text: List[str] = []
        self.config.adjust_for_word_count(self.word_count)
        for iteration in range(1, self.iterations + 1):
            current_text = " ".join(text)
            if iteration == 1:
                user_prompt = prompts.INITIAL_AUTO_PROMPT.format(
                    title=self.topic,
                    text_type=self.text_type,
                    content=self.content,
                    word_count=self.word_count,
                )
                start = time.perf_counter()
                addition = self._call_llm(
                    user_prompt,
                    fallback=f"Schreibe einen Text über {self.topic}. (iteration {iteration})",
                )
            else:
                meta_prompt = prompts.META_PROMPT.format(
                    title=self.topic,
                    text_type=self.text_type,
                    content=self.content,
                    word_count=self.word_count,
                    current_text=current_text,
                )
                prompt = self._call_llm(
                    meta_prompt, fallback="Fahre mit der Geschichte fort."
                )
                start = time.perf_counter()
                user_prompt = (
                    f"{prompt}\n\nTitel: {self.topic}\n"
                    f"Textart: {self.text_type}\n"
                    f"Gewünschter Inhalt: {self.content}\n"
                    f"Aktueller Text:\n{current_text}\n\nNächster Abschnitt:"
                )
                addition = self._call_llm(
                    user_prompt, fallback=f"{prompt}. (iteration {iteration})"
                )
            elapsed = time.perf_counter() - start
            tokens = len(addition.split())
            tok_per_sec = tokens / (elapsed or 1e-8)
            text.append(addition)
            current_text = " ".join(text)
            self._save_text(current_text)
            self.logger.info(
                "iteration %s/%s: %s", iteration, self.iterations, addition
            )
            bar_len = 20
            filled = int(bar_len * iteration / self.iterations)
            bar = "#" * filled + "-" * (bar_len - filled)
            print(
                f"iteration {iteration}/{self.iterations} [{bar}]: "
                f"{tokens} tokens ({tok_per_sec:.2f} tok/s)",
                flush=True,
            )

        final_text = " ".join(text)
        words = final_text.split()
        if len(words) > self.word_count:
            final_text = " ".join(words[: self.word_count])
        self._save_text(final_text)
        return final_text

    # ------------------------------------------------------------------
    def _craft_prompt(self, task: str) -> str:
        """Ask the LLM to craft an optimal prompt for the given task."""

        meta_prompt = (
            f"Formuliere einen klaren und konkreten Prompt für ein LLM, "
            f"um die Aufgabe '{task}' zum Thema '{self.topic}' umzusetzen. "
            f"Gib nur den Prompt zurück."
        )
        fallback = f"{task} über {self.topic}"
        return self._call_llm(meta_prompt, fallback=fallback)

    # ------------------------------------------------------------------
    def _generate(self, prompt: str, current_text: str, iteration: int) -> str:
        """Generate text for ``prompt`` given the current text state."""

        user_prompt = (
            f"{prompt}\n\nAktueller Text:\n{current_text}\n\nNächster Abschnitt:"
        )
        fallback = f"{prompt}. (Iteration {iteration})"
        return self._call_llm(user_prompt, fallback=fallback)

    # ------------------------------------------------------------------
    def _call_llm(self, prompt: str, *, fallback: str) -> str:
        """Internal helper to call the configured language model."""

        full_prompt = f"{self.system_prompt}\n\n{prompt}".strip()
        self.llm_logger.info("prompt: %s", full_prompt)

        result = fallback

        if self.config.llm_provider == "ollama":
            data = json.dumps(
                {
                    "model": self.config.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_ctx": self.config.context_length,
                        "num_predict": self.config.max_tokens,
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
                result = payload.get("response", "").strip() or fallback
            except urllib.error.URLError as exc:
                self.logger.error("ollama request failed: %s", exc)
                result = fallback

        elif self.config.llm_provider == "openai":
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
                    "max_tokens": self.config.max_tokens,
                }
            ).encode("utf8")
            req = urllib.request.Request(self.config.openai_url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
                    payload = json.loads(resp.read().decode("utf8"))
                result = payload["choices"][0]["message"]["content"].strip()
            except urllib.error.URLError as exc:
                self.logger.error("openai request failed: %s", exc)
                result = fallback

        self.llm_logger.info("response: %s", result)
        return result

    # ------------------------------------------------------------------
    def _save_text(self, text: str) -> None:
        """Persist ``text`` to the configured output file.

        The content is written with a trailing newline and flushed to disk so
        that other processes can observe the progress immediately. This mirrors
        the behaviour of the interactive mode where the current text file is
        updated after each iteration.
        """
        path = self.config.output_dir / self.config.output_file
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            fh.write(text + "\n")
            fh.flush()
            os.fsync(fh.fileno())

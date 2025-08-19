from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Tuple

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
            filename=str(self.config.log_dir / self.config.log_file),
            level=self.config.log_level,
            format="%(asctime)s - %(message)s",
            encoding=self.config.log_encoding,
            errors="backslashreplace",
            force=True,
        )
        self.logger = logging.getLogger(__name__)

        llm_handler = logging.FileHandler(
            self.config.log_dir / self.config.llm_log_file,
            encoding=self.config.log_encoding,
            errors="backslashreplace",
        )
        # Use a minimal formatter; timestamps are included in JSON payloads
        llm_handler.setFormatter(logging.Formatter("%(message)s"))
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
        """Automatically generate a text based on an outline and edit it."""

        text: List[str] = []
        self.config.adjust_for_word_count(self.word_count)

        outline_prompt = prompts.OUTLINE_PROMPT.format(
            title=self.topic,
            text_type=self.text_type,
            content=self.content,
            word_count=self.word_count,
        )
        outline = self._call_llm(outline_prompt, fallback="1. Einleitung (100)")
        sections = self._parse_outline(outline)

        for idx, (title, words) in enumerate(sections, start=1):
            current_text = " ".join(text)
            section_prompt = prompts.SECTION_PROMPT.format(
                outline=outline,
                current_text=current_text,
                title=title,
                word_count=words or 0,
            )
            start = time.perf_counter()
            addition = self._call_llm(section_prompt, fallback=title)
            elapsed = time.perf_counter() - start
            tokens = len(addition.split())
            tok_per_sec = tokens / (elapsed or 1e-8)
            text.append(addition)
            current_text = " ".join(text)
            self._save_text(current_text)
            print(
                f"section {idx}/{len(sections)}: {tokens} tokens ({tok_per_sec:.2f} tok/s)",
                flush=True,
            )

        final_text = " ".join(text)
        words_list = final_text.split()
        if len(words_list) > self.word_count:
            final_text = " ".join(words_list[: self.word_count])
        self._save_text(final_text)

        for iteration in range(1, self.iterations + 1):
            revision_prompt = prompts.REVISION_PROMPT.format(
                title=self.topic,
                text_type=self.text_type,
                content=self.content,
                word_count=self.word_count,
                outline=outline,
                current_text=final_text,
            )
            start = time.perf_counter()
            revised = self._call_llm(revision_prompt, fallback=final_text)
            elapsed = time.perf_counter() - start
            tokens = len(revised.split())
            tok_per_sec = tokens / (elapsed or 1e-8)
            final_text = revised
            self._save_text(final_text)
            self._save_iteration_text(final_text, iteration)
            bar_len = 20
            filled = int(bar_len * iteration / self.iterations)
            bar = "#" * filled + "-" * (bar_len - filled)
            print(
                f"iteration {iteration}/{self.iterations} [{bar}]: "
                f"{tokens} tokens ({tok_per_sec:.2f} tok/s)",
                flush=True,
            )
            self.logger.info("iteration %s/%s: %s", iteration, self.iterations, "edited")

        return final_text

    # ------------------------------------------------------------------
    def _parse_outline(self, outline: str) -> List[Tuple[str, int]]:
        """Parse an outline into (title, word_count) tuples."""

        sections: List[Tuple[str, int]] = []
        for line in outline.splitlines():
            line = line.strip()
            if not line:
                continue
            line = line.split(".", 1)[-1].strip() if "." in line else line
            match = re.search(r"^(.*?)(?:\((\d+)[^)]*\))?$", line)
            if match:
                title = match.group(1).strip()
                words = int(match.group(2)) if match.group(2) else 0
                sections.append((title, words))
        return sections

    # ------------------------------------------------------------------
    def _craft_prompt(self, task: str) -> str:
        """Ask the LLM to craft an optimal prompt for the given task."""

        meta_prompt = prompts.PROMPT_CRAFTING_PROMPT.format(
            task=task, topic=self.topic
        )
        fallback = f"{task} über {self.topic}"
        return self._call_llm(meta_prompt, fallback=fallback)

    # ------------------------------------------------------------------
    def _generate(self, prompt: str, current_text: str, iteration: int) -> str:
        """Generate text for ``prompt`` given the current text state."""

        user_prompt = prompts.STEP_PROMPT.format(
            prompt=prompt, current_text=current_text
        )
        fallback = f"{prompt}. (Iteration {iteration})"
        return self._call_llm(user_prompt, fallback=fallback)

    # ------------------------------------------------------------------
    def _call_llm(self, prompt: str, *, fallback: str) -> str:
        """Internal helper to call the configured language model."""

        full_prompt = f"{self.system_prompt}\n\n{prompt}".strip()
        # Log structured JSON to allow easier parsing and to keep entries on a single line
        self.llm_logger.info(
            json.dumps(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "prompt",
                    "text": full_prompt,
                },
                ensure_ascii=False,
            )
        )

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

        self.llm_logger.info(
            json.dumps(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "response",
                    "text": result,
                },
                ensure_ascii=False,
            )
        )
        return result

    # ------------------------------------------------------------------
    def _save_iteration_text(self, text: str, iteration: int) -> None:
        """Persist ``text`` of the current iteration to a separate file."""

        filename = self.config.auto_iteration_file_template.format(iteration)
        path = self.config.output_dir / filename
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            fh.write(text + "\n")
            fh.flush()
            os.fsync(fh.fileno())

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

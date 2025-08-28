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
from difflib import SequenceMatcher
from collections import Counter
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
        audience: str = "Allgemeine Leserschaft mit Grundkenntnissen",
        tone: str = "sachlich-lebendig",
        register: str = "Sie",
        variant: str = "DE-DE",
        constraints: str = "",
        sources_allowed: bool = True,
        seo_keywords: str = "",
    ) -> None:
        self.topic = topic
        self.word_count = word_count
        self.steps: List[Step] = list(steps)
        self.iterations = iterations
        self.config = config or DEFAULT_CONFIG
        self.content = content
        self.text_type = text_type
        self.audience = audience
        self.tone = tone
        self.register = register
        self.variant = variant
        self.constraints = constraints
        self.sources_allowed = sources_allowed
        self.seo_keywords = seo_keywords
        self.iteration = 0

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
                self.iteration = iteration
                current_text = " ".join(text)
                start = time.perf_counter()
                addition = self._generate(prompt, current_text, iteration)
                elapsed = time.perf_counter() - start
                if not addition.strip():
                    continue
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
        final_text = self._truncate_text(final_text)
        self._save_text(final_text)
        return final_text

    # ------------------------------------------------------------------
    def run_auto(self) -> str:
        """Automatically generate a text based on an outline and edit it."""

        self.config.adjust_for_word_count(self.word_count)
        self.iteration = 0

        briefing_prompt = prompts.BRIEFING_PROMPT.format(
            title=self.topic,
            text_type=self.text_type,
            audience=self.audience,
            tone=self.tone,
            register=self.register,
            variant=self.variant,
            constraints=self.constraints,
            seo_keywords=self.seo_keywords,
            content=self.content,
        )
        fallback_briefing = json.dumps(
            {
                "goal": "",
                "audience": self.audience,
                "tone": self.tone,
                "register": self.register,
                "variant": self.variant,
                "constraints": self.constraints,
                "key_terms": [],
                "messages": [],
                "seo_keywords": [k.strip() for k in self.seo_keywords.split(",") if k.strip()],
                "no_gos": [],
            }
        )
        briefing_json = self._call_llm(briefing_prompt, fallback=fallback_briefing)
        self._save_briefing(briefing_json)

        idea_prompt = prompts.IDEA_IMPROVEMENT_PROMPT.format(content=self.content)
        self.content = self._call_llm(
            idea_prompt,
            fallback=self.content,
            system_prompt=prompts.IDEA_IMPROVEMENT_SYSTEM_PROMPT,
        )
        self._save_idea(self.content)

        outline_prompt = prompts.OUTLINE_PROMPT.format(
            title=self.topic,
            text_type=self.text_type,
            briefing_json=briefing_json,
            word_count=self.word_count,
        )
        outline = self._call_llm(
            outline_prompt,
            fallback="1. Einleitung | Rolle: Hook | Wortbudget: {} | Liefergegenstand: Ziel".format(
                self.word_count
            ),
            system_prompt=prompts.OUTLINE_SYSTEM_PROMPT,
        )
        improve_prompt = prompts.OUTLINE_IMPROVEMENT_PROMPT.format(
            outline=outline, word_count=self.word_count
        )
        outline = self._call_llm(
            improve_prompt,
            fallback=outline,
            system_prompt=prompts.OUTLINE_IMPROVEMENT_SYSTEM_PROMPT,
        )
        outline = self._clean_outline(outline)
        self._save_outline(outline)
        self._save_iteration_text(outline, 0)

        limited_text, final_text = self._generate_sections_from_outline(
            outline, briefing_json
        )
        truncated = self._truncate_text(final_text)
        if truncated != limited_text:
            self._save_text(truncated)
            last_saved = truncated
        else:
            self._save_text(limited_text)
            last_saved = limited_text

        self.iteration = 0
        check_prompt = prompts.TEXT_TYPE_CHECK_PROMPT.format(
            text_type=self.text_type, current_text=final_text
        )
        check_result = self._call_llm(
            check_prompt,
            fallback="",
            system_prompt=prompts.TEXT_TYPE_CHECK_SYSTEM_PROMPT,
        )
        fix_prompt = prompts.TEXT_TYPE_FIX_PROMPT.format(
            issues=check_result, current_text=final_text
        )
        fixed_text = self._call_llm(
            fix_prompt,
            fallback=final_text,
            system_prompt=prompts.TEXT_TYPE_FIX_SYSTEM_PROMPT,
        )
        if fixed_text.strip() != final_text.strip():
            similarity = SequenceMatcher(None, final_text, fixed_text).ratio()
            final_words_list = final_text.split()
            fixed_words_list = fixed_text.split()
            common = sum((Counter(final_words_list) & Counter(fixed_words_list)).values())
            if common >= len(final_words_list) * 0.8 and similarity >= 0.9:
                final_text = fixed_text
                truncated = self._truncate_text(final_text)
                if truncated != last_saved:
                    self._save_text(truncated)
                    last_saved = truncated

        self._save_iteration_text(final_text, 1)

        if self.iterations:
            print(f"Revising: 0/{self.iterations}", end="", flush=True)
        for iteration in range(1, self.iterations + 1):
            self.iteration = iteration
            print(
                f"\rRevising: {iteration}/{self.iterations}",
                end="",
                flush=True,
            )
            final_text = self._load_iteration_text(iteration)
            revision_prompt = prompts.REVISION_PROMPT.format(
                register=self.register,
                variant=self.variant,
                current_text=final_text,
            )
            revised = self._call_llm(
                revision_prompt,
                fallback=final_text,
                system_prompt=prompts.REVISION_SYSTEM_PROMPT,
            )
            if revised.strip() != final_text.strip():
                final_text = revised
                truncated = self._truncate_text(final_text)
                if truncated != last_saved:
                    self._save_text(truncated)
                    last_saved = truncated
            self._save_iteration_text(final_text, iteration + 1)
        if self.iterations:
            print()

        meta = {
            "title": self.topic,
            "audience": self.audience,
            "tone": self.tone,
            "register": self.register,
            "variant": self.variant,
            "keywords": [k.strip() for k in self.seo_keywords.split(",") if k.strip()],
            "final_word_count": len(final_text.split()),
            "rubric_passed": "nein" not in check_result.lower(),
        }
        self._save_metadata(meta)

        return self._truncate_text(final_text)

    # ------------------------------------------------------------------
    def _generate_sections_from_outline(
        self, outline: str, briefing_json: str
    ) -> Tuple[str, str]:
        """Generate text for each section of ``outline`` and return the result."""

        sections = self._parse_outline(outline)
        if not sections:
            return "", ""

        total = sum(b for _, _, b, _ in sections) or 1
        factor = self.word_count / total
        allocated: List[Tuple[str, str, int, str]] = []
        accumulated = 0
        for title, role, budget, deliverable in sections:
            words = max(1, int(round(budget * factor)))
            allocated.append((title, role, words, deliverable))
            accumulated += words
        if allocated:
            title, role, words, deliverable = allocated[-1]
            allocated[-1] = (
                title,
                role,
                words + (self.word_count - accumulated),
                deliverable,
            )

        text_parts: List[str] = []
        full_parts: List[str] = []
        last_saved = ""
        total_sections = len(allocated)
        print(f"Generating sections: 0/{total_sections}", end="", flush=True)
        for idx, (title, role, words, deliverable) in enumerate(allocated, start=1):
            self.iteration = idx
            print(
                f"\rGenerating sections: {idx}/{total_sections}",
                end="",
                flush=True,
            )
            previous = text_parts[-1] if text_parts else ""
            recap = " ".join(previous.split()[-20:])
            section_prompt = prompts.SECTION_PROMPT.format(
                section_number=idx,
                section_title=title,
                role=role,
                deliverable=deliverable,
                budget=words,
                briefing_json=briefing_json,
                previous_section_recap=recap,
            )
            addition = self._call_llm(
                section_prompt,
                fallback=title,
                system_prompt=prompts.SECTION_SYSTEM_PROMPT,
            )
            addition_full = addition.strip()
            addition_limited = self._truncate_words(addition_full, words)
            if addition_limited and (
                not text_parts or addition_limited != text_parts[-1]
            ):
                text_parts.append(addition_limited)
                full_parts.append(addition_full)
                current_text = "\n\n".join(text_parts)
                current_full = "\n\n".join(full_parts)
                if current_text != last_saved:
                    self._save_text(current_text)
                    self._save_iteration_text(current_full, 1)
                    last_saved = current_text
        print()
        return "\n\n".join(text_parts), "\n\n".join(full_parts)

    # ------------------------------------------------------------------
    def _truncate_words(self, text: str, limit: int) -> str:
        """Truncate ``text`` to at most ``limit`` words."""

        words = text.split()
        if len(words) > limit:
            return " ".join(words[:limit])
        return text

    # ------------------------------------------------------------------
    def _parse_outline(self, outline: str) -> List[Tuple[str, str, int, str]]:
        """Parse an outline into ``(title, role, word_count, deliverable)`` tuples."""

        outline = self._clean_outline(outline)
        sections: List[Tuple[str, str, int, str]] = []
        for line in outline.splitlines():
            line = line.strip()
            if not line or line.startswith(('*', '-', '+', '#')):
                continue
            if not re.match(r"\d+(?:\.\d+)*\.", line):
                continue
            parts = [p.strip() for p in line.split('|')]
            title_part = parts[0]
            title = title_part.split('.', 1)[1].strip()
            role = ""
            budget = 0
            deliverable = ""
            for part in parts[1:]:
                key, _, value = part.partition(':')
                key = key.strip().lower()
                value = value.strip()
                if key.startswith('rolle'):
                    role = value
                elif key.startswith('wortbudget'):
                    m = re.search(r"(\d+)", value)
                    if m:
                        budget = int(m.group(1))
                elif key.startswith('liefer') or key.startswith('deliverable'):
                    deliverable = value
            sections.append((title, role, budget, deliverable))
        return sections

    # ------------------------------------------------------------------
    def _clean_outline(self, outline: str) -> str:
        """Remove leading "Outline:" lines and surrounding whitespace."""

        lines = outline.splitlines()
        while lines and lines[0].strip().lower().startswith("outline"):
            lines = lines[1:]
        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    def _craft_prompt(self, task: str) -> str:
        """Ask the LLM to craft an optimal prompt for the given task."""

        meta_prompt = prompts.PROMPT_CRAFTING_PROMPT.format(
            task=task, topic=self.topic
        )
        fallback = f"{task} über {self.topic}"
        return self._call_llm(
            meta_prompt,
            fallback=fallback,
            system_prompt=prompts.PROMPT_CRAFTING_SYSTEM_PROMPT,
        )

    # ------------------------------------------------------------------
    def _generate(self, prompt: str, current_text: str, iteration: int) -> str:
        """Generate text for ``prompt`` given the current text state."""

        user_prompt = prompts.STEP_PROMPT.format(
            prompt=prompt, current_text=current_text
        )
        fallback = f"{prompt}. (Iteration {iteration})"
        return self._call_llm(
            user_prompt,
            fallback=fallback,
            system_prompt=prompts.STEP_SYSTEM_PROMPT,
        )

    # ------------------------------------------------------------------
    def _call_llm(
        self, prompt: str, *, fallback: str, system_prompt: str | None = None
    ) -> str:
        """Internal helper to call the configured language model."""

        combined_system = self.system_prompt
        if system_prompt:
            combined_system = f"{combined_system}\n\n{system_prompt}".strip()

        full_prompt = f"{combined_system}\n\n{prompt}".strip()
        iteration = self.iteration
        # Log structured JSON to allow easier parsing and to keep entries on a single line
        self.llm_logger.info(
            json.dumps(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "prompt",
                    "iteration": iteration,
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
                        "top_p": self.config.top_p,
                        "presence_penalty": self.config.presence_penalty,
                        "frequency_penalty": self.config.frequency_penalty,
                        "seed": self.config.seed,
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
                self.logger.error(
                    "iteration %s: ollama request failed: %s", iteration, exc
                )
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
                        {"role": "system", "content": combined_system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "presence_penalty": self.config.presence_penalty,
                    "frequency_penalty": self.config.frequency_penalty,
                    "seed": self.config.seed,
                    "max_tokens": self.config.max_tokens,
                }
            ).encode("utf8")
            req = urllib.request.Request(self.config.openai_url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req) as resp:  # type: ignore[assignment]
                    payload = json.loads(resp.read().decode("utf8"))
                result = payload["choices"][0]["message"]["content"].strip()
            except urllib.error.URLError as exc:
                self.logger.error(
                    "iteration %s: openai request failed: %s", iteration, exc
                )
                result = fallback

        self.llm_logger.info(
            json.dumps(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "response",
                    "iteration": iteration,
                    "text": result,
                },
                ensure_ascii=False,
            )
        )
        return result

    # ------------------------------------------------------------------
    def _truncate_text(self, text: str) -> str:
        """Return ``text`` truncated to the configured word count."""

        words = text.split()
        if len(words) > self.word_count:
            return " ".join(words[: self.word_count])
        return text

    # ------------------------------------------------------------------
    def _save_iteration_text(self, text: str, iteration: int) -> None:
        """Persist ``text`` of the given iteration to a separate file.

        The numbering scheme reserves ``iteration_00.txt`` for the outline and
        ``iteration_01.txt`` for the initial draft before any revisions. Each
        subsequent revision is written to the next numbered file so that the
        original draft remains available for comparison.
        """

        filename = self.config.auto_iteration_file_template.format(iteration)
        path = self.config.output_dir / filename
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            fh.write(text + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ------------------------------------------------------------------
    def _load_iteration_text(self, iteration: int) -> str:
        """Return text of a previously saved iteration."""

        filename = self.config.auto_iteration_file_template.format(iteration)
        path = self.config.output_dir / filename
        if path.exists():
            return path.read_text(encoding="utf8").rstrip("\n")
        for prev in range(iteration - 1, -1, -1):
            prev_name = self.config.auto_iteration_file_template.format(prev)
            prev_path = self.config.output_dir / prev_name
            if prev_path.exists():
                return prev_path.read_text(encoding="utf8").rstrip("\n")
        return ""

    # ------------------------------------------------------------------
    def _save_outline(self, outline: str) -> None:
        """Persist the generated outline to a dedicated file."""

        path = self.config.output_dir / self.config.outline_file
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            fh.write(outline + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ------------------------------------------------------------------
    def _save_briefing(self, briefing_json: str) -> None:
        """Persist the generated briefing JSON."""

        path = self.config.output_dir / "briefing.json"
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            fh.write(briefing_json.strip() + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ------------------------------------------------------------------
    def _save_idea(self, idea: str) -> None:
        """Persist the improved idea text."""

        path = self.config.output_dir / "idea.txt"
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            fh.write(idea.strip() + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ------------------------------------------------------------------
    def _save_metadata(self, data: dict) -> None:
        """Persist run metadata to a JSON file."""

        path = self.config.output_dir / "metadata.json"
        self.config.output_dir.mkdir(exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            json.dump(data, fh, ensure_ascii=False)
            fh.write("\n")
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
        if path.exists():
            existing = path.read_text(encoding="utf8").rstrip("\n")
            if existing == text:
                return
        with path.open("w", encoding="utf8") as fh:
            fh.write(text + "\n")
            fh.flush()
            os.fsync(fh.fileno())

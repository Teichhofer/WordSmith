"""LLM-first implementation of the Automatikmodus writer agent."""

from __future__ import annotations

import ast
import json
import math
import re
from datetime import datetime
from time import perf_counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Sequence

from . import llm, prompts
from .config import Config, LLMParameters
from .defaults import (
    DEFAULT_AUDIENCE,
    DEFAULT_CONSTRAINTS,
    DEFAULT_REGISTER,
    DEFAULT_TONE,
    DEFAULT_VARIANT,
    REGISTER_ALIASES,
    VALID_VARIANTS,
)
from .llm import LLMGenerationError


_COMPLIANCE_PLACEHOLDERS: tuple[str, ...] = (
    "[KLÄREN",
    "[KENNZAHL]",
    "[QUELLE]",
    "[DATUM]",
    "[ZAHL]",
)

_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<!\[ENTFERNT: )\b(?P<term>vertraulich(?:keit|e[nr]?|en)?)\b", re.IGNORECASE),
    re.compile(r"(?<!\[ENTFERNT: )\b(?P<term>geheim(?:nis|e[nr]?|en)?)\b", re.IGNORECASE),
    re.compile(r"(?<!\[ENTFERNT: )\b(?P<term>sensibel(?:e[nr]?|n)?)\b", re.IGNORECASE),
    re.compile(r"(?<!\[ENTFERNT: )\b(?P<term>personenbezogene?n? daten)\b", re.IGNORECASE),
)


def _extract_json_object(text: str, start_index: int = 0) -> tuple[str, int] | None:
    """Return the next balanced JSON object substring and end position.

    The helper scans ``text`` starting at ``start_index`` for a ``{`` and then
    tracks matching braces while respecting quoted strings. When a balanced
    object is found the JSON substring and the index *after* the closing brace
    are returned. If no balanced object exists ``None`` is returned.
    """

    index = text.find("{", start_index)
    while index != -1:
        depth = 0
        in_string = False
        escape = False
        for position in range(index, len(text)):
            character = text[position]
            if in_string:
                if escape:
                    escape = False
                elif character == "\\":
                    escape = True
                elif character == '"':
                    in_string = False
                continue

            if character == '"':
                in_string = True
                continue
            if character == "{":
                depth += 1
                continue
            if character == "}":
                depth -= 1
                if depth == 0:
                    return text[index : position + 1], position + 1
                continue
        index = text.find("{", index + 1)
    return None


_JSON_LITERAL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("true", "True"),
    ("false", "False"),
    ("null", "None"),
)


_INVALID_ESCAPE_RE = re.compile(r"\\(?![\"\\/bfnrtu])(?P<char>.)", re.DOTALL)


def _sanitize_invalid_json_escapes(candidate: str) -> str:
    """Drop backslashes from invalid escape sequences in JSON strings."""

    if "\\" not in candidate:
        return candidate

    def _replace(match: re.Match[str]) -> str:
        return match.group("char")

    return _INVALID_ESCAPE_RE.sub(_replace, candidate)


def _replace_json_literals(candidate: str) -> str:
    """Convert JSON booleans/null to Python equivalents outside of strings."""

    result: list[str] = []
    index = 0
    in_string = False
    string_delimiter = ""
    length = len(candidate)
    while index < length:
        character = candidate[index]
        if in_string:
            result.append(character)
            if character == "\\":
                if index + 1 < length:
                    result.append(candidate[index + 1])
                    index += 2
                    continue
            elif character == string_delimiter:
                in_string = False
            index += 1
            continue

        if character in {'"', "'"}:
            in_string = True
            string_delimiter = character
            result.append(character)
            index += 1
            continue

        replaced = False
        for literal, replacement in _JSON_LITERAL_REPLACEMENTS:
            literal_end = index + len(literal)
            if candidate.startswith(literal, index):
                previous = candidate[index - 1] if index > 0 else ""
                next_char = candidate[literal_end] if literal_end < length else ""
                if (
                    (not previous.isalnum() and previous != "_")
                    and (not next_char.isalnum() and next_char != "_")
                ):
                    result.append(replacement)
                    index = literal_end
                    replaced = True
                    break
        if replaced:
            continue

        result.append(character)
        index += 1

    return "".join(result)


def _parse_json_candidate(candidate: str) -> Any:
    """Parse a JSON snippet using strict JSON first, then Python literals."""

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        sanitized = _sanitize_invalid_json_escapes(candidate)
        if sanitized != candidate:
            try:
                return json.loads(sanitized)
            except json.JSONDecodeError:
                candidate = sanitized
        python_like = _replace_json_literals(candidate)
        try:
            return ast.literal_eval(python_like)
        except (SyntaxError, ValueError) as exc:
            raise ValueError("Ungültiges JSON-Objekt.") from exc


def _load_json_object(text: str) -> Any:
    """Attempt to parse ``text`` as JSON, extracting embedded objects if needed."""

    cleaned = text.strip()
    candidates: list[str] = [cleaned]
    search_start = 0
    while True:
        extracted = _extract_json_object(cleaned, search_start)
        if extracted is None:
            break
        snippet, search_start = extracted
        snippet = snippet.strip()
        if snippet and snippet not in candidates:
            candidates.append(snippet)

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return _parse_json_candidate(candidate)
        except ValueError as exc:
            last_error = exc
            continue

    raise ValueError("Kein JSON-Objekt gefunden.") from last_error


@dataclass
class OutlineSection:
    """Container describing a single outline entry."""

    number: str
    title: str
    role: str
    budget: int
    deliverable: str

    def format_line(self) -> str:
        """Return the textual representation stored on disk."""

        return (
            f"{self.number}. {self.title} (Rolle: {self.role}, Budget: {self.budget} "
            f"Wörter) -> {self.deliverable}"
        )


class WriterAgentError(Exception):
    """Raised when the writer agent cannot complete its work."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context: dict[str, Any] = context or {}


@dataclass
class WriterAgent:
    """Writer agent that delegates all textual output to the configured LLM."""

    topic: str
    word_count: int
    steps: Sequence[str] | None
    iterations: int
    config: Config
    content: str
    text_type: str
    audience: str
    tone: str
    register: str
    variant: str
    constraints: str
    sources_allowed: bool
    seo_keywords: Sequence[str] | None = None
    progress_callback: Callable[[dict[str, Any]], None] | None = None
    include_compliance_note: bool = False

    output_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    _idea_bullets: List[str] = field(init=False, default_factory=list)
    _run_events: List[dict[str, Any]] = field(init=False, default_factory=list)
    _compliance_audit: List[dict[str, Any]] = field(init=False, default_factory=list)
    _pending_hints: List[dict[str, Any]] = field(init=False, default_factory=list)
    _llm_generation: dict[str, Any] | None = field(init=False, default=None)
    _rubric_passed: bool | None = field(init=False, default=None)
    _run_started_at: float = field(init=False, default=0.0)
    _run_duration: float | None = field(init=False, default=None)
    _compliance_note: str = field(init=False, default="")
    _telemetry: List[dict[str, Any]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.word_count <= 0:
            raise WriterAgentError("`word_count` muss größer als 0 sein.")
        if self.iterations < 0:
            raise WriterAgentError("`iterations` darf nicht negativ sein.")

        self.steps = list(self.steps or [])
        self.seo_keywords = [kw.strip() for kw in (self.seo_keywords or []) if kw.strip()]
        self._apply_input_defaults()
        self.output_dir = Path(self.config.output_dir)
        self.logs_dir = Path(self.config.logs_dir)

    # ------------------------------------------------------------------
    # Input normalisation and user hints
    # ------------------------------------------------------------------
    def _queue_hint(
        self,
        step: str,
        message: str,
        *,
        status: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        self._pending_hints.append(
            {
                "step": step,
                "message": message,
                "status": status,
                "data": data or {},
            }
        )

    def _flush_pending_hints(self) -> None:
        if not self._pending_hints:
            return
        for hint in self._pending_hints:
            self._record_run_event(
                hint["step"],
                hint["message"],
                status=hint.get("status", "info"),
                data=hint.get("data"),
            )
        self._pending_hints.clear()

    def _apply_input_defaults(self) -> None:
        self.topic = self.topic.strip()
        if not self.topic:
            raise WriterAgentError(
                "`topic` darf nicht leer sein. Bitte einen Arbeitstitel übergeben."
            )

        self.text_type = self.text_type.strip()
        if not self.text_type:
            raise WriterAgentError(
                "`text_type` darf nicht leer sein. Bitte den gewünschten Texttyp definieren."
            )

        defaults_used: List[str] = []

        audience = (self.audience or "").strip()
        if not audience:
            self.audience = DEFAULT_AUDIENCE
            defaults_used.append("audience")
        else:
            self.audience = audience

        tone = (self.tone or "").strip()
        if not tone:
            self.tone = DEFAULT_TONE
            defaults_used.append("tone")
        else:
            self.tone = tone

        register_value = (self.register or "").strip()
        if not register_value:
            self.register = DEFAULT_REGISTER
            defaults_used.append("register")
        else:
            lowered = register_value.lower()
            if lowered in REGISTER_ALIASES:
                self.register = REGISTER_ALIASES[lowered]
            else:
                self._queue_hint(
                    "input_defaults",
                    (
                        "Unbekanntes Register \"{value}\" erkannt. Standard 'Sie' wird genutzt."
                    ).format(value=register_value),
                    status="warning",
                    data={"field": "register", "value": register_value},
                )
                self.register = DEFAULT_REGISTER
                defaults_used.append("register")

        variant_value = (self.variant or "").strip()
        if not variant_value:
            self.variant = DEFAULT_VARIANT
            defaults_used.append("variant")
        else:
            upper = variant_value.upper()
            if upper in VALID_VARIANTS:
                self.variant = upper
                if self.variant != variant_value:
                    self._queue_hint(
                        "input_defaults",
                        (
                            "Sprachvariante \"{original}\" wurde auf \"{normalised}\" normalisiert."
                        ).format(original=variant_value, normalised=upper),
                        status="info",
                        data={"field": "variant", "value": variant_value},
                    )
            else:
                self._queue_hint(
                    "input_defaults",
                    (
                        "Unbekannte Sprachvariante \"{value}\" erkannt. Standard 'DE-DE' wird genutzt."
                    ).format(value=variant_value),
                    status="warning",
                    data={"field": "variant", "value": variant_value},
                )
                self.variant = DEFAULT_VARIANT
                defaults_used.append("variant")

        constraints_value = (self.constraints or "").strip()
        if not constraints_value:
            self.constraints = DEFAULT_CONSTRAINTS
            defaults_used.append("constraints")
        else:
            self.constraints = constraints_value

        if defaults_used:
            self._queue_hint(
                "input_defaults",
                "Eingaben ergänzt oder normalisiert: " + ", ".join(sorted(defaults_used)) + ".",
                status="info",
                data={"defaults": sorted(defaults_used)},
            )
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> str:
        """Execute the LLM-driven pipeline and return the final text."""

        self._run_started_at = perf_counter()
        self._run_duration = None
        self.config.ensure_directories()
        self.config.cleanup_temporary_outputs()
        self._idea_bullets.clear()
        self._compliance_audit.clear()
        self._run_events.clear()
        self._pending_hints.clear()
        self._llm_generation = None
        self._rubric_passed = None
        self._telemetry.clear()

        self._record_run_event(
            "start",
            "Automatikmodus gestartet",
            status="started",
            data={
                "topic": self.topic,
                "word_count": self.word_count,
                "iterations": self.iterations,
            },
        )
        self._flush_pending_hints()

        briefing: dict[str, Any] | None = None
        outline_sections: List[OutlineSection] = []
        run_error: Exception | None = None

        try:
            briefing = self._generate_briefing()
            self._write_json(self.output_dir / "briefing.json", briefing)
            self._record_run_event(
                "briefing",
                "Briefing mit LLM erzeugt",
                artifacts=[self.output_dir / "briefing.json"],
                data={
                    "messages": len(briefing.get("messages", [])),
                    "key_terms": len(briefing.get("key_terms", [])),
                },
            )

            idea_text = self._improve_idea_with_llm()
            if idea_text is None:
                raise WriterAgentError("Ideenphase konnte nicht abgeschlossen werden.")
            self._idea_bullets = self._extract_idea_bullets(idea_text)
            self._write_text(self.output_dir / "idea.txt", idea_text)
            self._record_run_event(
                "idea",
                "Idee mit LLM überarbeitet",
                artifacts=[self.output_dir / "idea.txt"],
                data={"bullets": len(self._idea_bullets)},
            )

            outline_sections = self._create_outline_with_llm(briefing)
            if not outline_sections:
                raise WriterAgentError("Outline konnte nicht generiert werden.")
            outline_sections = self._refine_outline_with_llm(briefing, outline_sections)
            outline_sections = self._clean_outline_sections(outline_sections)
            outline_text = self._format_outline_for_prompt(outline_sections)
            self._write_text(self.output_dir / "outline.txt", outline_text)
            self._write_text(self.output_dir / "iteration_00.txt", outline_text)
            self._record_run_event(
                "outline",
                "Outline mit LLM erstellt",
                artifacts=[
                    self.output_dir / "outline.txt",
                    self.output_dir / "iteration_00.txt",
                ],
                data={"sections": len(outline_sections)},
            )

            draft = self._generate_draft_from_outline(
                briefing,
                outline_sections,
                idea_text,
            )
            if draft is None:
                raise WriterAgentError("Finaler Entwurf konnte nicht erstellt werden.")
            draft = self._apply_text_type_review(draft, briefing, outline_sections)
            draft = self._run_compliance("draft", draft, ensure_sources=self.sources_allowed)
            self._write_text(self.output_dir / "current_text.txt", draft)
            self._write_text(self.output_dir / "iteration_01.txt", draft)
            self.steps.append("draft")
            self._record_run_event(
                "draft",
                "Initialer Entwurf abgeschlossen",
                artifacts=[
                    self.output_dir / "current_text.txt",
                    self.output_dir / "iteration_01.txt",
                ],
            )

            for iteration in range(1, self.iterations + 1):
                revised = self._revise_with_llm(draft, iteration, briefing)
                if revised is None:
                    raise WriterAgentError(
                        f"Revision {iteration:02d} konnte nicht generiert werden."
                    )
                revised = self._run_compliance(
                    f"revision_{iteration:02d}",
                    revised,
                    ensure_sources=self.sources_allowed,
                )
                draft = revised
                self._write_text(
                    self.output_dir / f"iteration_{iteration + 1:02d}.txt",
                    draft,
                )
                self._write_text(self.output_dir / "current_text.txt", draft)
                self.steps.append(f"revision_{iteration:02d}")
                self._record_run_event(
                    f"revision_{iteration:02d}",
                    f"Revision {iteration:02d} abgeschlossen",
                    artifacts=[
                        self.output_dir / f"iteration_{iteration + 1:02d}.txt",
                        self.output_dir / "current_text.txt",
                    ],
                    data={"iteration": iteration},
                )

                reflection = self._generate_reflection(draft, iteration)
                if reflection:
                    reflection_path = self.output_dir / f"reflection_{iteration + 1:02d}.txt"
                    self._write_text(reflection_path, reflection)
                    self.steps.append(f"reflection_{iteration:02d}")
                    self._record_run_event(
                        f"reflection_{iteration:02d}",
                        f"Reflexion {iteration:02d} abgeschlossen",
                        artifacts=[reflection_path],
                        data={"iteration": iteration},
                    )

            final_output_path = self._write_final_output(draft)
            final_word_count = self._count_words(draft)
            self._write_metadata(draft)
            self._record_run_event(
                "metadata",
                "Metadaten gespeichert",
                artifacts=[self.output_dir / "metadata.json"],
                data={"final_word_count": final_word_count},
            )
            self._write_compliance_report()
            self._record_run_event(
                "compliance_report",
                "Compliance-Report gespeichert",
                artifacts=[self.output_dir / "compliance.json"],
                data={"checks": len(self._compliance_audit)},
            )
            runtime_seconds = perf_counter() - self._run_started_at
            self._run_duration = runtime_seconds
            self._record_run_event(
                "complete",
                "Automatikmodus erfolgreich abgeschlossen",
                status="succeeded",
                artifacts=[final_output_path],
                data={
                    "iterations": self.iterations,
                    "steps": list(self.steps),
                    "runtime_seconds": runtime_seconds,
                },
            )
            return draft
        except Exception as exc:
            run_error = exc
            message = (
                f"Automatikmodus konnte nicht abgeschlossen werden: {exc}"
                if isinstance(exc, WriterAgentError)
                else f"Automatikmodus unerwartet abgebrochen: {exc}"
            )
            runtime_seconds = perf_counter() - self._run_started_at
            self._run_duration = runtime_seconds
            error_data = {
                "error": str(exc),
                "exception_type": exc.__class__.__name__,
            }
            if isinstance(exc, WriterAgentError) and exc.context:
                error_data.update(exc.context)
            error_data["runtime_seconds"] = runtime_seconds
            self._record_run_event(
                "error",
                message,
                status="failed",
                data=error_data,
            )
            raise
        finally:
            try:
                self._write_logs(briefing or {}, outline_sections)
            except Exception:
                if run_error is None:
                    raise

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------
    def _generate_briefing(self) -> dict:
        notes = (self.content or "").strip() or "[KLÄREN: Keine Notizen geliefert.]"
        seo_text = ", ".join(self.seo_keywords or [])
        prompt = prompts.BRIEFING_PROMPT.format(
            title=self.topic,
            text_type=self.text_type,
            word_count=self.word_count,
            audience=self.audience,
            tone=self.tone,
            register=self.register,
            variant=self.variant,
            constraints=self.constraints,
            seo_keywords=seo_text or "keine",
            content=notes,
        )
        briefing_text = self._call_llm_stage(
            stage="briefing_llm",
            prompt_type="briefing",
            prompt=prompt,
            system_prompt=prompts.BRIEFING_SYSTEM_PROMPT,
            success_message="Briefing generiert",
            failure_message="Briefing-Generierung fehlgeschlagen",
            data={"phase": "briefing", "target_words": self.word_count},
        )
        if briefing_text is None:
            raise WriterAgentError("Briefing konnte nicht generiert werden.")
        try:
            briefing = _load_json_object(briefing_text)
        except ValueError as exc:  # pragma: no cover - defensive
            raise WriterAgentError(
                "Briefing-Antwort konnte nicht als JSON interpretiert werden.",
                context={"raw_text": briefing_text},
            ) from exc
        if not isinstance(briefing, dict):
            raise WriterAgentError("Briefing-Antwort muss ein Objekt sein.")
        briefing.setdefault("goal", f"{self.text_type} zu '{self.topic}' erstellen")
        briefing.setdefault("audience", self.audience)
        briefing.setdefault("tone", self.tone)
        briefing.setdefault("register", self.register)
        briefing.setdefault("variant", self.variant)
        briefing.setdefault("constraints", self.constraints)
        briefing.setdefault("messages", [])
        briefing.setdefault("key_terms", [])
        briefing.setdefault("seo_keywords", list(self.seo_keywords or []))
        return briefing

    def _improve_idea_with_llm(self) -> str | None:
        content = (self.content or "").strip()
        if not content:
            content = "[KLÄREN: Inhaltliches Briefing ergänzen]"
        prompt = prompts.IDEA_IMPROVEMENT_PROMPT.format(content=content)
        return self._call_llm_stage(
            stage="idea_llm",
            prompt_type="idea_improvement",
            prompt=prompt,
            system_prompt=prompts.IDEA_IMPROVEMENT_SYSTEM_PROMPT,
            success_message="Idee mit LLM überarbeitet",
            failure_message="LLM-Ideenverbesserung fehlgeschlagen",
            data={"phase": "idea", "target_words": self.word_count},
        )

    def _extract_idea_bullets(self, text: str) -> List[str]:
        bullets: List[str] = []
        bullet_pattern = re.compile(r"^\s*[-*•]\s+(?P<content>.+)")
        numbered_pattern = re.compile(r"^\s*\d+[.)\-]\s*(?P<content>.+)")
        for line in text.splitlines():
            match = bullet_pattern.match(line)
            if match:
                cleaned = match.group("content").strip()
                if cleaned and not cleaned.lower().startswith("summary"):
                    bullets.append(cleaned)
        if not bullets:
            for line in text.splitlines():
                match = numbered_pattern.match(line)
                if match:
                    cleaned = match.group("content").strip()
                    if cleaned and not cleaned.lower().startswith("summary"):
                        bullets.append(cleaned)
        return bullets

    def _create_outline_with_llm(self, briefing: dict) -> List[OutlineSection]:
        prompt = prompts.OUTLINE_PROMPT.format(
            text_type=self.text_type,
            title=self.topic,
            briefing_json=json.dumps(briefing, ensure_ascii=False, indent=2),
            word_count=self.word_count,
        )
        outline_text = self._call_llm_stage(
            stage="outline_llm",
            prompt_type="outline",
            prompt=prompt,
            system_prompt=prompts.OUTLINE_SYSTEM_PROMPT,
            success_message="Outline mit LLM erstellt",
            failure_message="LLM-Outline fehlgeschlagen",
            data={"phase": "outline", "target_words": self.word_count},
        )
        if not outline_text:
            return []
        sections = self._parse_outline_sections(outline_text)
        return sections

    def _parse_outline_sections(self, outline_text: str) -> List[OutlineSection]:
        lines = [line.strip() for line in outline_text.splitlines() if line.strip()]
        sections: List[OutlineSection] = []
        number_pattern = re.compile(
            r"^\s*(?:[-*•]\s*)?(?P<number>\d+(?:\.\d+)*)[\)\.:\-\s]+(?P<body>.+)$"
        )
        for line in lines:
            match = number_pattern.match(line)
            if not match:
                continue
            number = match.group("number").strip()
            body = match.group("body").strip()

            deliverable: str | None = None
            title_part = body
            if "->" in body:
                title_part, deliverable = [part.strip() for part in body.split("->", 1)]
            else:
                deliverable_match = re.search(
                    r"(liefer\w*):\s*(?P<deliverable>[^,;]+)",
                    body,
                    flags=re.IGNORECASE,
                )
                if deliverable_match:
                    deliverable = deliverable_match.group("deliverable").strip()
                    title_part = body[: deliverable_match.start()].strip()

            detail_text = ""
            title = title_part
            detail_match = re.search(r"\((?P<details>[^)]*)\)", title_part)
            if detail_match:
                detail_text = detail_match.group("details")
                title = (title_part[: detail_match.start()] + title_part[detail_match.end():]).strip()
            else:
                title = title_part.strip()

            role = "Abschnitt"
            budget = 0
            if detail_text:
                for part in re.split(r"[;,]", detail_text):
                    key, _, value = part.partition(":")
                    if not _:
                        continue
                    key_lower = key.strip().lower()
                    value = value.strip()
                    if "rolle" in key_lower or "funktion" in key_lower:
                        if value:
                            role = value
                    elif "wort" in key_lower:
                        number_match = re.search(r"\d+", value)
                        if number_match:
                            budget = int(number_match.group())
                    elif "liefer" in key_lower and not deliverable:
                        if value:
                            deliverable = value

            if not title:
                title = f"Abschnitt {number}"
            if not deliverable:
                deliverable = "Liefergegenstand definieren."

            sections.append(
                OutlineSection(
                    number=number,
                    title=title,
                    role=role,
                    budget=budget,
                    deliverable=deliverable,
                )
            )

        return sections
    def _format_outline_for_prompt(
        self, sections: Sequence[OutlineSection]
    ) -> str:
        return "\n".join(section.format_line() for section in sections)

    def _refine_outline_with_llm(
        self, briefing: dict, sections: Sequence[OutlineSection]
    ) -> List[OutlineSection]:
        prompt = (
            prompts.OUTLINE_IMPROVEMENT_PROMPT.format(word_count=self.word_count).strip()
            + "\n\nBriefing:\n"
            + json.dumps(briefing, ensure_ascii=False, indent=2)
            + "\n\nAktuelle Outline:\n"
            + self._format_outline_for_prompt(sections)
        )
        improved_text = self._call_llm_stage(
            stage="outline_improvement_llm",
            prompt_type="outline_improvement",
            prompt=prompt,
            system_prompt=prompts.OUTLINE_IMPROVEMENT_SYSTEM_PROMPT,
            success_message="Outline mit LLM verfeinert",
            failure_message="LLM-Outline-Überarbeitung fehlgeschlagen",
            data={"phase": "outline", "target_words": self.word_count},
        )
        if not improved_text:
            return list(sections)

        improved_sections = self._parse_outline_sections(improved_text)
        return improved_sections or list(sections)

    def _clean_outline_sections(
        self, sections: Sequence[OutlineSection]
    ) -> List[OutlineSection]:
        cleaned: List[OutlineSection] = []
        for section in sections:
            role_value = (section.role or "").strip()
            deliverable_value = (section.deliverable or "").strip()
            title_value = (section.title or "").strip()
            cleaned_section = OutlineSection(
                number=section.number,
                title=title_value or f"Abschnitt {section.number}",
                role=role_value or "Abschnitt",
                budget=max(section.budget, 0),
                deliverable=deliverable_value or "Liefergegenstand definieren.",
            )
            cleaned.append(cleaned_section)

        if not cleaned:
            return []

        total_budget = sum(section.budget for section in cleaned)
        if total_budget <= 0:
            average_budget = max(50, int(self.word_count / max(1, len(cleaned))))
            for section in cleaned:
                section.budget = average_budget
            total_budget = average_budget * len(cleaned)

        difference = self.word_count - total_budget
        if difference != 0:
            cleaned[-1].budget = max(0, cleaned[-1].budget + difference)

        for section in cleaned:
            if not section.role:
                section.role = "Abschnitt"

        return cleaned

    def _generate_draft_from_outline(
        self,
        briefing: dict,
        sections: Sequence[OutlineSection],
        idea_text: str,
    ) -> str | None:
        compiled_sections: List[tuple[OutlineSection, str]] = []
        aggregate_parts: List[str] = []

        for index, section in enumerate(sections, start=1):
            prompt = self._build_section_prompt(
                briefing=briefing,
                sections=sections,
                section=section,
                idea_text=idea_text,
                compiled_sections=compiled_sections,
            )
            stage = f"section_{index:02d}_llm"
            section_text = self._call_llm_stage(
                stage=stage,
                prompt_type="section",
                prompt=prompt,
                system_prompt=prompts.SECTION_SYSTEM_PROMPT,
                success_message=f"Abschnitt {index:02d} generiert",
                failure_message=f"Abschnitt {index:02d} fehlgeschlagen",
                data={
                    "phase": "section",
                    "section": section.number,
                    "title": section.title,
                    "target_words": section.budget,
                },
            )
            if not section_text:
                self._llm_generation = {
                    "status": "failed",
                    "provider": self.config.llm_provider,
                    "model": self.config.llm_model,
                    "section": section.number,
                    "title": section.title,
                }
                self._record_run_event(
                    "llm_generation",
                    f"Abschnitt {index:02d} konnte nicht generiert werden.",
                    status="warning",
                    data={"section": section.number, "title": section.title},
                )
                return None

            cleaned_section = section_text.strip()
            compiled_sections.append((section, cleaned_section))
            aggregate_parts.append(self._format_section_output(section, cleaned_section))
            partial_draft = "\n\n".join(aggregate_parts).strip()
            self._write_text(self.output_dir / "current_text.txt", partial_draft)
            self.steps.append(f"section_{index:02d}")

        draft = "\n\n".join(aggregate_parts).strip()
        self._llm_generation = {
            "status": "success",
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "sections": len(compiled_sections),
            "response_preview": draft[:400],
        }
        self.steps.append("llm_generation")
        self._record_run_event(
            "llm_generation",
            "Abschnittsweise Generierung abgeschlossen",
            status="info",
            data={"sections": len(compiled_sections)},
        )
        return draft

    def _build_section_prompt(
        self,
        *,
        briefing: dict,
        sections: Sequence[OutlineSection],
        section: OutlineSection,
        idea_text: str,
        compiled_sections: Sequence[tuple[OutlineSection, str]],
    ) -> str:
        previous_text = "\n\n".join(
            self._format_section_output(prev_section, text)
            for prev_section, text in compiled_sections
        ).strip()
        idea_clean = idea_text.strip() or "[KLÄREN: Idee ergänzen]"
        recap = self._build_previous_section_recap(compiled_sections)

        min_words, max_words = self._calculate_word_limits(section.budget)
        style_guidelines = self._compose_style_guidelines()

        return (
            prompts.SECTION_PROMPT.format(
                section_number=section.number,
                section_title=section.title,
                role=section.role,
                deliverable=section.deliverable,
                ziel_woerter=section.budget,
                min_woerter=min_words,
                max_woerter=max_words,
                stilrichtlinien=style_guidelines,
                previous_section_recap=recap,
            ).strip()
            + "\n\nBriefing:\n"
            + json.dumps(briefing, ensure_ascii=False, indent=2)
            + "\n\nOutline:\n"
            + self._format_outline_for_prompt(sections)
            + "\n\nKernaussagen:\n"
            + idea_clean
            + "\n\nBisheriger Text:\n"
            + (previous_text or "Noch kein Abschnitt verfasst.")
        )

    def _calculate_word_limits(self, budget: int) -> tuple[int, int]:
        tolerance = 0.1
        minimum = max(1, math.floor(budget * (1 - tolerance)))
        maximum = max(minimum, math.ceil(budget * (1 + tolerance)))
        return minimum, maximum

    def _compose_style_guidelines(self) -> str:
        components: list[str] = []
        if self.tone:
            components.append(f"Ton: {self.tone}")
        if self.register:
            components.append(f"Register: {self.register}")
        if self.variant:
            components.append(f"Variante: {self.variant}")
        if self.audience:
            components.append(f"Zielgruppe: {self.audience}")

        constraints = (self.constraints or "").strip()
        if constraints:
            components.append(f"Zusatzvorgaben: {constraints}")
        else:
            components.append("Zusatzvorgaben: keine spezifischen Zusatzvorgaben")

        if self.seo_keywords:
            components.append(
                "SEO-Keywords: " + ", ".join(keyword for keyword in self.seo_keywords)
            )

        sources_note = "Quellenmodus: erlaubt" if self.sources_allowed else "Quellenmodus: gesperrt"
        components.append(sources_note)

        return "; ".join(components)

    def _build_previous_section_recap(
        self, compiled_sections: Sequence[tuple[OutlineSection, str]]
    ) -> str:
        if not compiled_sections:
            return "Erster Abschnitt – etabliere das Thema und die Zielsetzung klar."
        last_section, last_text = compiled_sections[-1]
        words = [token for token in re.split(r"\s+", last_text.strip()) if token]
        tail = " ".join(words[-60:]).strip()
        return f"Vorheriger Abschnitt '{last_section.title}': {tail}" if tail else (
            f"Vorheriger Abschnitt '{last_section.title}' zusammenfassen."
        )

    def _format_section_output(self, section: OutlineSection, text: str) -> str:
        heading = f"## {section.number}. {section.title}".strip()
        return f"{heading}\n\n{text.strip()}"

    def _apply_text_type_review(
        self,
        draft: str,
        briefing: dict,
        sections: Sequence[OutlineSection],
    ) -> str:
        check_prompt = (
            prompts.TEXT_TYPE_CHECK_PROMPT.format(text_type=self.text_type).strip()
            + "\n\nBriefing:\n"
            + json.dumps(briefing, ensure_ascii=False, indent=2)
            + "\n\nOutline:\n"
            + self._format_outline_for_prompt(sections)
            + "\n\nText:\n"
            + draft
        )
        report = self._call_llm_stage(
            stage="text_type_check_llm",
            prompt_type="text_type_check",
            prompt=check_prompt,
            system_prompt=prompts.TEXT_TYPE_CHECK_SYSTEM_PROMPT,
            success_message="Texttyp-Prüfung abgeschlossen",
            failure_message="Texttyp-Prüfung fehlgeschlagen",
            data={"phase": "text_type_check", "target_words": self.word_count},
        )
        if report is None:
            self._rubric_passed = None
            return draft

        self.steps.append("text_type_check")
        self._write_text(self.output_dir / "text_type_check.txt", report)
        if not self._text_type_check_requires_fix(report):
            self._rubric_passed = True
            return draft

        fix_prompt = (
            prompts.TEXT_TYPE_FIX_PROMPT.strip()
            + "\n\nBriefing:\n"
            + json.dumps(briefing, ensure_ascii=False, indent=2)
            + "\n\nOutline:\n"
            + self._format_outline_for_prompt(sections)
            + "\n\nAbweichungen:\n"
            + report
            + "\n\nText:\n"
            + draft
        )
        fixed = self._call_llm_stage(
            stage="text_type_fix_llm",
            prompt_type="text_type_fix",
            prompt=fix_prompt,
            system_prompt=prompts.TEXT_TYPE_FIX_SYSTEM_PROMPT,
            success_message="Texttyp-Korrektur angewendet",
            failure_message="Texttyp-Korrektur fehlgeschlagen",
            data={"phase": "text_type_fix", "target_words": self.word_count},
        )
        if fixed is None:
            self._rubric_passed = False
            return draft

        self.steps.append("text_type_fix")
        self._write_text(self.output_dir / "text_type_fix.txt", fixed)
        self._rubric_passed = True
        return fixed

    def _text_type_check_requires_fix(self, report: str) -> bool:
        normalised = report.strip().lower()
        if not normalised:
            return False
        ok_markers = [
            "keine abweichung",
            "keine auffälligkeit",
            "erfüllt die kriterien",
            "alles erfüllt",
            "passt",
            "in ordnung",
        ]
        return not any(marker in normalised for marker in ok_markers)

    def _revise_with_llm(self, text: str, iteration: int, briefing: dict) -> str | None:
        min_words, max_words = self._calculate_word_limits(self.word_count)
        prompt_text = text.strip()
        system_prompt = prompts.REVISION_SYSTEM_PROMPT.strip()
        length_hint = (
            f"Zielumfang: {min_words}-{max_words} Wörter; bleib nah an der Vorlage."
            if min_words and max_words
            else ""
        )
        if length_hint:
            system_prompt = f"{system_prompt} {length_hint}".strip()

        if self.include_compliance_note:
            compliance_hint = prompts.COMPLIANCE_HINT_INSTRUCTION.strip()
            if compliance_hint:
                system_prompt = f"{system_prompt} {compliance_hint}".strip()

        return self._call_llm_stage(
            stage=f"revision_{iteration:02d}_llm",
            prompt_type="revision",
            prompt=prompt_text,
            system_prompt=system_prompt,
            success_message=f"Revision {iteration:02d} generiert",
            failure_message=f"Revision {iteration:02d} fehlgeschlagen",
            data={"iteration": iteration, "target_words": self.word_count},
        )

    def _generate_reflection(self, text: str, iteration: int) -> str | None:
        prompt = (
            prompts.REFLECTION_PROMPT.strip()
            + "\n\nText:\n"
            + text.strip()
        )
        return self._call_llm_stage(
            stage=f"reflection_{iteration:02d}_llm",
            prompt_type="reflection",
            prompt=prompt,
            system_prompt=prompts.REFLECTION_SYSTEM_PROMPT,
            success_message=f"Reflexion {iteration:02d} generiert",
            failure_message=f"Reflexion {iteration:02d} fehlgeschlagen",
            data={"iteration": iteration, "phase": "reflection", "target_words": self.word_count},
        )

    # ------------------------------------------------------------------
    # Compliance helpers
    # ------------------------------------------------------------------
    def _extract_compliance_note(self, text: str) -> tuple[str, str]:
        stripped = text.strip()
        if "[COMPLIANCE-" not in stripped:
            return stripped, ""
        body, _, note = stripped.rpartition("\n\n")
        if note.startswith("[COMPLIANCE-"):
            return body, note
        return stripped, ""

    def _contains_placeholder(self, text: str) -> bool:
        return any(marker in text for marker in _COMPLIANCE_PLACEHOLDERS)

    def _mask_sensitive_content(self, text: str) -> tuple[str, int]:
        replacements = 0

        def _replace(match: re.Match[str]) -> str:
            nonlocal replacements
            term = match.group("term")
            replacements += 1
            return f"[ENTFERNT: {term.lower()}]"

        updated = text
        for pattern in _SENSITIVE_PATTERNS:
            updated = pattern.sub(_replace, updated)
        return updated, replacements

    def _run_compliance(
        self,
        stage: str,
        text: str,
        *,
        ensure_sources: bool = False,
        annotation_label: str | None = None,
    ) -> str:
        updated, sensitive_hits = self._mask_sensitive_content(text)
        body, note = self._extract_compliance_note(updated)
        self._compliance_note = note
        if self.include_compliance_note and note:
            result = body + "\n\n" + note
        else:
            result = body
        placeholders_present = self._contains_placeholder(result)
        sources_detail = "zugelassen" if ensure_sources else "gesperrt"
        self._record_compliance(
            stage,
            placeholders=placeholders_present,
            sensitive_hits=sensitive_hits,
            sources_detail=sources_detail,
            note_present=bool(note),
            note_text=note or "",
        )
        return result

    def _record_compliance(
        self,
        stage: str,
        *,
        placeholders: bool,
        sensitive_hits: int,
        sources_detail: str,
        note_present: bool,
        note_text: str,
    ) -> None:
        self._compliance_audit.append(
            {
                "stage": stage,
                "placeholders_present": placeholders,
                "sensitive_replacements": sensitive_hits,
                "sources": sources_detail,
                "compliance_note": note_present,
                "compliance_note_text": note_text if note_present else "",
            }
        )

    def _write_compliance_report(self) -> None:
        report = {
            "topic": self.topic,
            "sources_allowed": self.sources_allowed,
            "checks": [dict(entry) for entry in self._compliance_audit],
            "latest_compliance_note": self._compliance_note or "",
        }
        self._write_json(self.output_dir / "compliance.json", report)
    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------
    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_text(self, path: Path, text: str) -> None:
        path.write_text(text.strip() + "\n", encoding="utf-8")

    def _write_final_output(self, text: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_path = self.output_dir / f"Final-{timestamp}.txt"
        self._write_text(final_path, text)
        return final_path

    def _write_metadata(self, text: str) -> None:
        metadata = {
            "title": self.topic,
            "audience": self.audience,
            "tone": self.tone,
            "register": self.register,
            "variant": self.variant,
            "keywords": list(self.seo_keywords or []),
            "final_word_count": self._count_words(text),
            "rubric_passed": self._rubric_passed,
            "sources_allowed": self.sources_allowed,
            "llm_provider": self.config.llm_provider,
            "llm_model": self.config.llm_model,
            "system_prompt": prompts.SYSTEM_PROMPT,
            "system_prompts": dict(prompts.STAGE_SYSTEM_PROMPTS),
            "compliance_checks": [dict(entry) for entry in self._compliance_audit],
            "latest_compliance_note": self._compliance_note or "",
        }
        self._write_json(self.output_dir / "metadata.json", metadata)

    def _write_logs(
        self,
        briefing: dict,
        outline_sections: Sequence[OutlineSection],
    ) -> None:
        run_log = self.logs_dir / "run.log"
        run_entries = [dict(entry) for entry in self._run_events]
        for index, entry in enumerate(run_entries):
            entry.setdefault("sequence", index)
        run_lines = [json.dumps(entry, ensure_ascii=False) for entry in run_entries]
        run_log.write_text("\n".join(run_lines) + "\n", encoding="utf-8")

        llm_log = self.logs_dir / "llm.log"
        min_words, max_words = self._calculate_word_limits(self.word_count)

        llm_entry = {
            "stage": "pipeline",
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "parameters": asdict(self.config.llm),
            "system_prompt": prompts.SYSTEM_PROMPT,
            "system_prompts": dict(prompts.STAGE_SYSTEM_PROMPTS),
            "topic": self.topic,
            "word_count": self.word_count,
            "audience": self.audience,
            "text_type": self.text_type,
            "messages": briefing.get("messages", []),
            "outline": [asdict(section) for section in outline_sections],
            "prompts": {
                "briefing": prompts.BRIEFING_PROMPT.strip(),
                "idea": prompts.IDEA_IMPROVEMENT_PROMPT.strip(),
                "outline": prompts.OUTLINE_PROMPT.strip(),
                "outline_improvement": prompts.OUTLINE_IMPROVEMENT_PROMPT.strip(),
                "section": prompts.SECTION_PROMPT.strip(),
                "text_type_check": prompts.TEXT_TYPE_CHECK_PROMPT.strip(),
                "text_type_fix": prompts.TEXT_TYPE_FIX_PROMPT.strip(),
                "revision": prompts.build_revision_prompt(
                    include_compliance_hint=self.include_compliance_note,
                    target_words=self.word_count,
                    min_words=min_words,
                    max_words=max_words,
                ),
            },
            "events": run_entries,
            "llm_generation": self._llm_generation,
            "telemetry": self._telemetry,
            "runtime_seconds": self._run_duration,
        }
        llm_log.write_text(
            json.dumps(llm_entry, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @property
    def runtime_seconds(self) -> float | None:
        """Return the measured runtime of the most recent run."""

        return self._run_duration

    def _record_run_event(
        self,
        step: str,
        message: str,
        *,
        status: str = "completed",
        artifacts: Sequence[Path | str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {"step": step, "status": status, "message": message}
        event["timestamp"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if artifacts:
            event["artifacts"] = [self._format_artifact_path(Path(artifact)) for artifact in artifacts]
        if data:
            event["data"] = data
        event["sequence"] = len(self._run_events)
        self._run_events.append(event)
        if self.progress_callback is not None:
            self.progress_callback(dict(event))

    def _build_stage_parameters(self, prompt_type: str) -> LLMParameters:
        base = LLMParameters(
            temperature=self.config.llm.temperature,
            top_p=self.config.llm.top_p,
            presence_penalty=self.config.llm.presence_penalty,
            frequency_penalty=self.config.llm.frequency_penalty,
            seed=self.config.llm.seed,
        )
        if hasattr(base, "num_predict"):
            base.num_predict = getattr(self.config.llm, "num_predict", None)
        overrides = prompts.STAGE_PROMPT_PARAMETERS.get(prompt_type, {})
        for key, value in overrides.items():
            if hasattr(base, key):
                setattr(base, key, value)
        return base

    def _record_telemetry(
        self,
        *,
        stage: str,
        prompt_type: str,
        parameters: LLMParameters,
        required_tokens: int,
        token_limit: int,
        target_words: int,
        iteration: int | None,
        status: str,
        abort_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        output_word_count: int | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "sequence": len(self._telemetry),
            "stage": stage,
            "prompt_type": prompt_type,
            "iteration": iteration,
            "token_limit": token_limit,
            "required_tokens": required_tokens,
            "target_word_count": target_words,
            "parameters": asdict(parameters),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "output_word_count": output_word_count,
            "status": status,
        }
        if abort_reason:
            entry["abort_reason"] = abort_reason
        self._telemetry.append(entry)

    def _format_artifact_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.output_dir))
        except ValueError:
            try:
                return str(path.relative_to(self.logs_dir))
            except ValueError:
                return str(path)

    def _estimate_token_usage(self, *parts: str) -> int:
        total_characters = sum(len(part) for part in parts if part)
        if total_characters <= 0:
            return 0
        return math.ceil(total_characters / 4)

    def _should_use_llm(self) -> bool:
        provider = (self.config.llm_provider or "").strip().lower()
        model = (self.config.llm_model or "").strip()
        return bool(model) and provider == "ollama"

    def _call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, Any] | None = None,
    ) -> str | None:
        if not self._should_use_llm():
            raise WriterAgentError("Es ist kein kompatibles LLM-Modell konfiguriert.")

        token_limit = max(1, int(self.config.token_limit))
        reserve_limit = max(1, math.floor(token_limit * 0.85))
        required_tokens = self._estimate_token_usage(system_prompt, prompt)
        parameters = self._build_stage_parameters(prompt_type)
        context_data = data or {}
        iteration = context_data.get("iteration")
        raw_target_words = context_data.get("target_words", self.word_count)
        try:
            target_words = int(raw_target_words)
        except (TypeError, ValueError):
            target_words = self.word_count
        if required_tokens > reserve_limit:
            context = {
                "stage": stage,
                "token_limit": token_limit,
                "required_tokens": required_tokens,
                "usable_tokens": reserve_limit,
            }
            self._record_telemetry(
                stage=stage,
                prompt_type=prompt_type,
                parameters=parameters,
                required_tokens=required_tokens,
                token_limit=token_limit,
                target_words=target_words,
                iteration=iteration if isinstance(iteration, int) else None,
                status="blocked",
                abort_reason="token_reserve_exceeded",
                prompt_tokens=required_tokens,
                completion_tokens=None,
            )
            raise WriterAgentError(
                (
                    "Tokenbudget überschritten: "
                    f"{required_tokens} > {reserve_limit} (85 % von {token_limit})."
                ),
                context=context,
            )
        try:
            result = llm.generate_text(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                prompt=prompt,
                system_prompt=system_prompt,
                parameters=parameters,
                base_url=self.config.ollama_base_url,
            )
        except LLMGenerationError as exc:
            event_data = {"provider": self.config.llm_provider, "model": self.config.llm_model}
            if data:
                event_data.update(data)
            event_data["error"] = str(exc)
            self._record_run_event(
                stage,
                f"{failure_message}: {exc}",
                status="warning",
                data=event_data,
            )
            self._record_telemetry(
                stage=stage,
                prompt_type=prompt_type,
                parameters=parameters,
                required_tokens=required_tokens,
                token_limit=token_limit,
                target_words=target_words,
                iteration=iteration if isinstance(iteration, int) else None,
                status="error",
                abort_reason=str(exc),
                prompt_tokens=required_tokens,
                completion_tokens=None,
            )
            return None

        text = result.text.strip()
        if not text:
            event_data = {"provider": self.config.llm_provider, "model": self.config.llm_model}
            if data:
                event_data.update(data)
            self._record_run_event(
                stage,
                f"{failure_message}: leere Antwort",
                status="warning",
                data=event_data,
            )
            self._record_telemetry(
                stage=stage,
                prompt_type=prompt_type,
                parameters=parameters,
                required_tokens=required_tokens,
                token_limit=token_limit,
                target_words=target_words,
                iteration=iteration if isinstance(iteration, int) else None,
                status="empty",
                abort_reason="empty_response",
                prompt_tokens=result.raw.get("prompt_eval_count") if result.raw else required_tokens,
                completion_tokens=result.raw.get("eval_count") if result.raw else None,
                output_word_count=0,
            )
            return None

        event_data = {
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "characters": len(text),
        }
        if data:
            event_data.update(data)
        self._record_run_event(
            stage,
            success_message,
            status="info",
            data=event_data,
        )
        prompt_tokens = None
        completion_tokens = None
        if isinstance(result.raw, dict):
            raw_prompt_tokens = result.raw.get("prompt_eval_count")
            raw_completion_tokens = result.raw.get("eval_count")
            prompt_tokens = int(raw_prompt_tokens) if isinstance(raw_prompt_tokens, int) else raw_prompt_tokens
            completion_tokens = (
                int(raw_completion_tokens) if isinstance(raw_completion_tokens, int) else raw_completion_tokens
            )
        self._record_telemetry(
            stage=stage,
            prompt_type=prompt_type,
            parameters=parameters,
            required_tokens=required_tokens,
            token_limit=token_limit,
            target_words=target_words,
            iteration=iteration if isinstance(iteration, int) else None,
            status="success",
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else prompt_tokens,
            completion_tokens=completion_tokens if isinstance(completion_tokens, int) else completion_tokens,
            output_word_count=self._count_words(text),
        )
        return text

    def _count_words(self, text: str) -> int:
        return len([token for token in text.split() if token.strip()])

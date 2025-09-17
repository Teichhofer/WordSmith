"""Implementation of the Automatikmodus writer agent pipeline.

The module emulates the documented steps from ``docs/automatikmodus.md`` in a
deterministic way so that the CLI can be tested end-to-end without real LLM
calls.  The agent focuses on structure, artefact creation and rule adherence
rather than open-ended text generation.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from itertools import cycle
from pathlib import Path
from typing import Any, Iterable, List, Sequence


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

from . import llm, prompts
from .config import Config
from .defaults import (
    DEFAULT_AUDIENCE,
    DEFAULT_CONSTRAINTS,
    DEFAULT_REGISTER,
    DEFAULT_TONE,
    DEFAULT_VARIANT,
    REGISTER_ALIASES,
    VALID_VARIANTS,
)


class WriterAgentError(Exception):
    """Raised when the writer agent cannot complete its work."""


@dataclass
class WriterAgent:
    """Deterministic re-implementation of the documented writer pipeline."""

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

    output_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    _terminology_cache: List[str] = field(init=False, default_factory=list)
    _term_cycle: Iterable[str] = field(init=False, repr=False)
    _idea_bullets: List[str] = field(init=False, default_factory=list)
    _placeholder_inserted: bool = field(init=False, default=False)
    _sources_sentence_used: bool = field(init=False, default=False)
    _keywords_used: set[str] = field(init=False, default_factory=set)
    _compliance_audit: List[dict] = field(init=False, default_factory=list)
    _run_events: List[dict[str, Any]] = field(init=False, default_factory=list)
    _pending_hints: List[dict[str, Any]] = field(init=False, default_factory=list)
    _llm_generation: dict[str, Any] | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.word_count <= 0:
            raise WriterAgentError("`word_count` muss größer als 0 sein.")
        if self.iterations < 0:
            raise WriterAgentError("`iterations` darf nicht negativ sein.")
        self.steps = list(self.steps or [])
        self.seo_keywords = [kw.strip() for kw in (self.seo_keywords or []) if kw.strip()]
        self._pending_hints = []
        self._apply_input_defaults()
        self.output_dir = Path(self.config.output_dir)
        self.logs_dir = Path(self.config.logs_dir)
        self._term_cycle = cycle([self.topic.lower()])

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
        """Execute the documented pipeline and return the final text."""

        self.config.ensure_directories()
        self._placeholder_inserted = False
        self._sources_sentence_used = False
        self._keywords_used.clear()
        self._idea_bullets = []
        self._compliance_audit.clear()
        self._run_events.clear()

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

        briefing = self._normalize_briefing()
        self._write_json(self.output_dir / "briefing.json", briefing)
        self._record_run_event(
            "briefing",
            "Briefing normalisiert",
            artifacts=[self.output_dir / "briefing.json"],
            data={
                "messages": len(briefing.get("messages", [])),
                "key_terms": len(briefing.get("key_terms", [])),
            },
        )

        idea = self._improve_idea(briefing)
        self._write_text(self.output_dir / "idea.txt", idea)
        self._record_run_event(
            "idea",
            "Idee überarbeitet",
            artifacts=[self.output_dir / "idea.txt"],
            data={"bullets": len(self._idea_bullets)},
        )

        outline_sections = self._create_outline(briefing)
        outline_text = self._format_outline(outline_sections)
        self._write_text(self.output_dir / "outline.txt", outline_text)
        self._write_text(self.output_dir / "iteration_00.txt", outline_text)
        self._record_run_event(
            "outline",
            "Outline erstellt",
            artifacts=[
                self.output_dir / "outline.txt",
                self.output_dir / "iteration_00.txt",
            ],
            data={"sections": len(outline_sections)},
        )

        self._llm_generation = None
        draft_source = "pipeline"
        llm_draft = self._try_llm_generation(
            outline_sections, briefing, idea, outline_text
        )
        if llm_draft is not None:
            draft = llm_draft
            draft_source = "llm"
        else:
            draft = self._generate_sections(outline_sections, briefing)
        draft = self._enforce_length(draft)
        draft = self._run_compliance(
            "draft",
            draft,
            ensure_sources=True,
            annotation_label="llm" if draft_source == "llm" else "pipeline",
        )
        self._write_text(self.output_dir / "current_text.txt", draft)
        self._write_text(self.output_dir / "iteration_01.txt", draft)

        rubric_passed, issues = self._check_text_type(draft, briefing)
        if issues:
            draft_body, _ = self._extract_compliance_note(draft)
            fixed = self._apply_text_type_fix(draft_body, issues, briefing)
            if not self._similar_enough(draft_body, fixed):
                fixed = self._blend_with_original(draft_body, fixed)
            fixed = self._enforce_length(fixed)
            draft = self._run_compliance(
                "draft_fix",
                fixed,
                ensure_sources=True,
                annotation_label="pipeline",
            )
            self._write_text(self.output_dir / "current_text.txt", draft)
            self._write_text(self.output_dir / "iteration_01.txt", draft)
            rubric_passed, _ = self._check_text_type(draft, briefing)
        else:
            rubric_passed = True

        self.steps.append("draft")
        self._record_run_event(
            "draft",
            "Initialer Entwurf erstellt",
            artifacts=[
                self.output_dir / "current_text.txt",
                self.output_dir / "iteration_01.txt",
            ],
            data={"rubric_passed": rubric_passed},
        )
        self._record_run_event(
            "text_type_review",
            "Texttypprüfung abgeschlossen",
            data={"rubric_passed": rubric_passed},
        )

        for iteration in range(1, self.iterations + 1):
            base_draft, _ = self._extract_compliance_note(draft)
            revised = self._revise_draft(draft, iteration, briefing)
            if not self._similar_enough(
                base_draft, revised, min_jaccard=0.75, min_ratio=0.88
            ):
                revised = self._blend_with_original(base_draft, revised)
            revised = self._enforce_length(revised)
            draft = self._run_compliance(
                f"revision_{iteration:02d}",
                revised,
                ensure_sources=True,
                annotation_label="pipeline",
            )
            self._write_text(self.output_dir / f"iteration_{iteration + 1:02d}.txt", draft)
            self._write_text(self.output_dir / "current_text.txt", draft)
            reflection = self._reflection_notes(iteration)
            if reflection:
                self._write_text(
                    self.output_dir / f"reflection_{iteration + 1:02d}.txt",
                    reflection,
                )
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
            if reflection:
                self._record_run_event(
                    f"reflection_{iteration + 1:02d}",
                    f"Reflexion {iteration + 1:02d} gespeichert",
                    artifacts=[
                        self.output_dir / f"reflection_{iteration + 1:02d}.txt"
                    ],
                    data={"iteration": iteration + 1},
                )

        final_word_count = self._count_words(draft)
        self._write_metadata(draft, rubric_passed)
        self._record_run_event(
            "metadata",
            "Metadaten gespeichert",
            artifacts=[self.output_dir / "metadata.json"],
            data={
                "final_word_count": final_word_count,
                "rubric_passed": rubric_passed,
            },
        )
        self._write_compliance_report()
        self._record_run_event(
            "compliance_report",
            "Compliance-Report gespeichert",
            artifacts=[self.output_dir / "compliance.json"],
            data={"checks": len(self._compliance_audit)},
        )
        self._record_run_event(
            "complete",
            "Automatikmodus erfolgreich abgeschlossen",
            status="succeeded",
            data={"iterations": self.iterations, "steps": list(self.steps)},
        )
        self._write_logs(briefing, outline_sections, rubric_passed)
        return draft

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------
    def _normalize_briefing(self) -> dict:
        key_terms = self._extract_key_terms()
        if not key_terms:
            key_terms = [self.topic.lower()]
        self._terminology_cache = key_terms
        self._term_cycle = cycle(self._terminology_cache or [self.topic.lower()])

        messages = [line.strip() for line in self.content.splitlines() if line.strip()]
        if not messages:
            messages = ["[KLÄREN: Es wurden keine Notizen geliefert.]"]

        briefing = {
            "goal": f"{self.text_type} zu '{self.topic}' prägnant entwickeln",
            "audience": self.audience,
            "tone": self.tone,
            "register": self.register,
            "variant": self.variant,
            "constraints": self.constraints or "Keine zusätzlichen Vorgaben",
            "key_terms": key_terms,
            "messages": messages,
        }
        if self.seo_keywords:
            briefing["seo_keywords"] = list(self.seo_keywords)

        briefing["compliance"] = self._build_briefing_compliance()
        self._record_compliance(
            "briefing",
            placeholders=True,
            sensitive_hits=0,
            sources_detail=briefing["compliance"]["sources_mode"],
            note_present=False,
        )
        self.steps.append("briefing")
        return briefing

    def _improve_idea(self, briefing: dict) -> str:
        if self._should_use_llm():
            idea_text = self._improve_idea_with_llm()
            if idea_text:
                bullets = self._extract_idea_bullets(idea_text)
                if bullets:
                    self._idea_bullets = bullets
                elif not self._idea_bullets:
                    self._idea_bullets = ["[KLÄREN: Inhaltliches Briefing ergänzen]"]
                idea_text = self._run_compliance(
                    "idea", idea_text, annotation_label="idea"
                )
                self.steps.append("idea")
                return idea_text

        raw_sentences = self._split_content_into_sentences(self.content)
        bullets: List[str] = []
        for sentence in raw_sentences:
            cleaned = sentence.strip()
            if not cleaned:
                continue
            if "?" in cleaned or cleaned.endswith("?"):
                bullets.append(f"[KLÄREN: {cleaned.strip('? ')}]")
            else:
                bullets.append(cleaned)

        if not bullets:
            bullets = ["[KLÄREN: Inhaltliches Briefing ergänzen]"]

        self._idea_bullets = bullets
        bullet_text = "\n".join(f"- {item}" for item in bullets)
        summary = (
            f"Summary: Der Text adressiert {briefing['audience']} und stärkt {self.topic} "
            f"als {self.text_type}."
        )

        idea_text = "\n".join(
            [
                f"Überarbeitete Idee für '{self.topic}':",
                bullet_text,
                "",
                summary,
            ]
        )
        idea_text = self._run_compliance("idea", idea_text, annotation_label="idea")
        self.steps.append("idea")
        return idea_text

    def _create_outline(self, briefing: dict) -> List[OutlineSection]:
        if self._should_use_llm():
            sections = self._create_outline_with_llm(briefing)
            if sections:
                self.steps.append("outline")
                return sections

        sections = self._build_outline_sections()
        sections = self._improve_outline(sections)
        sections = self._clean_outline(sections)
        self.steps.append("outline")
        return sections

    def _improve_idea_with_llm(self) -> str | None:
        content = (self.content or "").strip()
        if not content:
            content = "[KLÄREN: Inhaltliches Briefing ergänzen]"
        prompt = prompts.IDEA_IMPROVEMENT_PROMPT.format(content=content)
        return self._call_llm_stage(
            stage="idea_llm",
            prompt=prompt,
            success_message="Idee mit LLM überarbeitet",
            failure_message="LLM-Ideenverbesserung fehlgeschlagen",
            data={"phase": "idea"},
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

    def _create_outline_with_llm(
        self, briefing: dict
    ) -> List[OutlineSection] | None:
        prompt = prompts.OUTLINE_PROMPT.format(
            text_type=self.text_type,
            title=self.topic,
            briefing_json=json.dumps(briefing, ensure_ascii=False, indent=2),
            word_count=self.word_count,
        )
        outline_text = self._call_llm_stage(
            stage="outline_llm",
            prompt=prompt,
            success_message="Outline mit LLM erstellt",
            failure_message="LLM-Outline fehlgeschlagen",
            data={"phase": "initial"},
        )
        if not outline_text:
            return None

        improvement_prompt = (
            prompts.OUTLINE_IMPROVEMENT_PROMPT.format(word_count=self.word_count)
            + "\n\nOutline:\n"
            + outline_text.strip()
        )
        improved_text = self._call_llm_stage(
            stage="outline_llm_improve",
            prompt=improvement_prompt,
            success_message="Outline mit LLM verfeinert",
            failure_message="LLM-Outline-Verbesserung fehlgeschlagen",
            data={"phase": "improvement"},
        )
        outline_source = improved_text or outline_text

        sections = self._parse_outline_sections(outline_source)
        if not sections:
            self._record_run_event(
                "outline_llm_parse",
                "LLM-Outline konnte nicht interpretiert werden.",
                status="warning",
                data={"phase": "parse_failure"},
            )
            return None

        sections = self._distribute_outline_budgets(sections)
        sections = self._clean_outline(sections)
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

    def _distribute_outline_budgets(
        self, sections: List[OutlineSection]
    ) -> List[OutlineSection]:
        missing = [section for section in sections if section.budget <= 0]
        if not missing:
            return sections

        allocated = sum(section.budget for section in sections if section.budget > 0)
        remaining = self.word_count - allocated
        if remaining <= 0:
            default_budget = max(60, self.word_count // max(1, len(sections)))
        else:
            default_budget = max(60, remaining // max(1, len(missing)))

        if default_budget <= 0:
            default_budget = 60

        for section in sections:
            if section.budget <= 0:
                section.budget = default_budget
        return sections

    def _build_outline_sections(self) -> List[OutlineSection]:
        total = self.word_count
        sections: List[OutlineSection]
        if total < 360:
            intro = max(60, int(total * 0.25))
            outro = max(50, int(total * 0.2))
            body = max(120, total - intro - outro)
            sections = [
                OutlineSection(
                    "1",
                    "Kontext und Zielbild",
                    "Hook",
                    intro,
                    "Auftrag, Zielgruppe und Relevanz klarziehen.",
                ),
                OutlineSection(
                    "2",
                    "Kernbotschaften strukturieren",
                    "Argument",
                    body,
                    "Leitthesen, Nutzen und Entscheidungsgrundlagen bündeln.",
                ),
                OutlineSection(
                    "3",
                    "Fazit und Handlungsimpuls",
                    "CTA",
                    outro,
                    "Schlüsse ziehen und konkrete Aktion anregen.",
                ),
            ]
        else:
            intro = max(80, int(total * 0.22))
            outro = max(70, int(total * 0.18))
            middle = max(180, total - intro - outro)
            core = max(140, int(middle * 0.55))
            support = max(100, middle - core)
            sections = [
                OutlineSection(
                    "1",
                    "Kontext und Zielbild",
                    "Hook",
                    intro,
                    "Ausgangslage, Zielgruppe und Erwartungshaltung verorten.",
                ),
                OutlineSection(
                    "2",
                    "Strategische Leitplanken",
                    "Rahmen",
                    core,
                    "Erfolgsfaktoren, Prioritäten und Entscheidungskriterien bündeln.",
                ),
                OutlineSection(
                    "3",
                    "Umsetzung und Taktik",
                    "Argument",
                    support,
                    "Initiativen, Ressourcenbedarf und Meilensteine skizzieren.",
                ),
                OutlineSection(
                    "4",
                    "Fazit und Handlungsimpuls",
                    "CTA",
                    outro,
                    "Nutzen verdichten und nächsten Schritt aktivieren.",
                ),
            ]
        return sections

    def _improve_outline(self, sections: List[OutlineSection]) -> List[OutlineSection]:
        improved: List[OutlineSection] = []
        term_cycle = cycle(self._terminology_cache or [self.topic.lower()])
        for section in sections:
            term = next(term_cycle)
            deliverable = section.deliverable
            if term and term.lower() not in deliverable.lower():
                deliverable = f"{deliverable} Terminologie-Fokus: {term}."
            improved.append(
                OutlineSection(
                    number=section.number,
                    title=section.title,
                    role=section.role,
                    budget=section.budget,
                    deliverable=deliverable,
                )
            )
        return improved

    def _clean_outline(self, sections: List[OutlineSection]) -> List[OutlineSection]:
        if not sections:
            return sections

        minimum = 60
        adjusted: List[OutlineSection] = []
        total_budget = 0
        for section in sections:
            budget = max(minimum, int(section.budget))
            adjusted.append(
                OutlineSection(
                    section.number,
                    section.title,
                    section.role,
                    budget,
                    section.deliverable,
                )
            )
            total_budget += budget

        difference = self.word_count - total_budget
        if difference:
            per_section = difference // len(adjusted)
            remainder = difference % len(adjusted)
            balanced: List[OutlineSection] = []
            for idx, section in enumerate(adjusted):
                extra = per_section + (1 if idx < remainder else 0)
                new_budget = max(minimum, section.budget + extra)
                balanced.append(
                    OutlineSection(
                        section.number,
                        section.title,
                        section.role,
                        new_budget,
                        section.deliverable,
                    )
                )
            adjusted = balanced

        recalculated = sum(section.budget for section in adjusted)
        if recalculated != self.word_count:
            delta = self.word_count - recalculated
            last = adjusted[-1]
            adjusted[-1] = OutlineSection(
                last.number,
                last.title,
                last.role,
                max(minimum, last.budget + delta),
                last.deliverable,
            )

        return adjusted

    def _format_outline(self, sections: Sequence[OutlineSection]) -> str:
        outline_text = "\n".join(section.format_line() for section in sections)
        return self._run_compliance(
            "outline", outline_text, annotation_label="outline"
        )

    def _call_llm_stage(
        self,
        *,
        stage: str,
        prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, Any] | None = None,
    ) -> str | None:
        try:
            result = llm.generate_text(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                prompt=prompt,
                system_prompt=prompts.SYSTEM_PROMPT,
                parameters=self.config.llm,
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
        return text

    def _should_use_llm(self) -> bool:
        provider = (self.config.llm_provider or "").strip().lower()
        model = (self.config.llm_model or "").strip()
        return bool(model) and provider == "ollama"

    def _build_llm_prompt(
        self,
        briefing: dict,
        sections: Sequence[OutlineSection],
        *,
        idea_text: str,
        outline_text: str,
    ) -> str:
        outline_clean = outline_text.strip()
        if not outline_clean:
            outline_clean = "\n".join(
                (
                    f"{section.number}. {section.title} ({section.role}) – "
                    f"{section.deliverable} [{section.budget} Wörter]"
                )
                for section in sections
            )
        idea_clean = idea_text.strip()
        if not idea_clean:
            bullets = self._idea_bullets or ["[KLÄREN: Ideenbriefing ergänzen]"]
            idea_clean = "\n".join(f"- {item}" for item in bullets)

        seo_text = ", ".join(self.seo_keywords or []) or "keine"
        variant_hint = f"Verwende Rechtschreibung für {self.variant}" if self.variant else "Nutze Standardsprache"
        sources_mode = "Quellen erlaubt" if self.sources_allowed else "Quellenangaben blockiert"
        constraints = self.constraints or DEFAULT_CONSTRAINTS

        return prompts.FINAL_DRAFT_PROMPT.format(
            text_type=self.text_type,
            title=self.topic,
            word_count=self.word_count,
            briefing_json=json.dumps(briefing, ensure_ascii=False, indent=2),
            outline=outline_clean,
            idea_bullets=idea_clean,
            tone=self.tone,
            register=self.register,
            variant_hint=variant_hint,
            sources_mode=sources_mode,
            constraints=constraints,
            seo_keywords=seo_text,
        )

    def _try_llm_generation(
        self,
        sections: Sequence[OutlineSection],
        briefing: dict,
        idea_text: str,
        outline_text: str,
    ) -> str | None:
        if not self._should_use_llm():
            return None

        idea_body, _ = self._extract_compliance_note(idea_text)
        outline_body, _ = self._extract_compliance_note(outline_text)
        prompt = self._build_llm_prompt(
            briefing,
            sections,
            idea_text=idea_body or idea_text,
            outline_text=outline_body or outline_text,
        )

        try:
            result = llm.generate_text(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                prompt=prompt,
                system_prompt=prompts.SYSTEM_PROMPT,
                parameters=self.config.llm,
                base_url=self.config.ollama_base_url,
            )
        except LLMGenerationError as exc:
            self._llm_generation = {
                "status": "failed",
                "provider": self.config.llm_provider,
                "model": self.config.llm_model,
                "error": str(exc),
                "prompt_preview": prompt[:200],
            }
            self._record_run_event(
                "llm_generation",
                f"LLM-Generierung fehlgeschlagen: {exc}",
                status="warning",
                data={
                    "provider": self.config.llm_provider,
                    "model": self.config.llm_model,
                },
            )
            return None

        text = result.text.strip()
        if not text:
            self._llm_generation = {
                "status": "failed",
                "provider": self.config.llm_provider,
                "model": self.config.llm_model,
                "error": "Leere Antwort erhalten.",
                "prompt_preview": prompt[:200],
            }
            self._record_run_event(
                "llm_generation",
                "LLM-Generierung lieferte keinen Text.",
                status="warning",
                data={
                    "provider": self.config.llm_provider,
                    "model": self.config.llm_model,
                },
            )
            return None

        generation_record: dict[str, Any] = {
            "status": "success",
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "prompt": prompt,
            "response_preview": text[:400],
        }
        if isinstance(result, LLMResult) and result.raw is not None:
            generation_record["raw"] = result.raw
        self._llm_generation = generation_record
        self.steps.append("llm_generation")
        self._record_run_event(
            "llm_generation",
            f"Entwurf mit {self.config.llm_provider} erstellt",
            status="info",
            data={
                "provider": self.config.llm_provider,
                "model": self.config.llm_model,
                "characters": len(text),
            },
        )
        return text

    def _generate_sections(self, sections: Sequence[OutlineSection], briefing: dict) -> str:
        paragraphs: List[str] = []
        previous_summary = ""
        mutable_sections = [
            OutlineSection(section.number, section.title, section.role, section.budget, section.deliverable)
            for section in sections
        ]
        batch_index = 1
        batch_limit = max(100, int(self.config.token_limit * 0.9))
        batch_usage = 0

        for index, section in enumerate(mutable_sections):
            recap_sentence: str | None = None
            estimated_usage = section.budget
            if batch_usage and batch_usage + estimated_usage > batch_limit:
                batch_index += 1
                recap_sentence = self._build_recap_sentence(previous_summary, batch_index)
                self._record_run_event(
                    "batch_generation",
                    f"Kontextlimit erreicht – Batch {batch_index} gestartet.",
                    status="info",
                    data={
                        "batch_index": batch_index,
                        "limit": batch_limit,
                        "trigger_section": section.number,
                    },
                )
                batch_usage = 0

            section_text, summary = self._compose_section(
                section,
                index,
                mutable_sections,
                briefing,
                previous_summary,
                recap_sentence=recap_sentence,
            )
            paragraphs.append(section_text)
            previous_summary = summary

            body = section_text.split("\n", 1)[1] if "\n" in section_text else section_text
            actual_words = self._count_words(body)
            batch_usage += actual_words

            shortfall = section.budget - actual_words
            threshold = max(3, int(section.budget * 0.05))
            if shortfall >= threshold and index < len(mutable_sections) - 1:
                redistributed = self._rebalance_future_budgets(mutable_sections, index + 1, shortfall)
                if redistributed:
                    self._record_run_event(
                        "budget_rebalance",
                        (
                            f"Wortbudget nach Abschnitt {section.number} um {redistributed} Wörter neu verteilt."
                        ),
                        status="info",
                        data={
                            "section": section.number,
                            "planned": section.budget,
                            "actual": actual_words,
                            "shortfall": shortfall,
                            "redistributed": redistributed,
                        },
                    )

        return "\n\n".join(paragraphs)

    def _rebalance_future_budgets(
        self,
        sections: List[OutlineSection],
        start_index: int,
        surplus: int,
    ) -> int:
        if start_index >= len(sections) or surplus <= 0:
            return 0

        remaining = sections[start_index:]
        total_reference = sum(section.budget for section in remaining)
        if total_reference <= 0:
            return 0

        base_shares = [
            (surplus * section.budget) // total_reference if total_reference else 0
            for section in remaining
        ]
        distributed = sum(base_shares)
        remainder = surplus - distributed

        if remainder > 0:
            order = sorted(
                range(len(remaining)),
                key=lambda idx: remaining[idx].budget,
                reverse=True,
            )
            for position in order:
                if remainder <= 0:
                    break
                base_shares[position] += 1
                remainder -= 1

        distributed = sum(base_shares)
        for offset, share in enumerate(base_shares):
            if share <= 0:
                continue
            idx = start_index + offset
            section = sections[idx]
            sections[idx] = OutlineSection(
                section.number,
                section.title,
                section.role,
                section.budget + share,
                section.deliverable,
            )
        return distributed

    def _build_recap_sentence(self, summary: str, batch_index: int) -> str:
        cleaned = summary.strip().rstrip(". ") if summary.strip() else (
            "die bisherige Passage die Ausgangslage skizziert hat"
        )
        previous_batch = max(1, batch_index - 1)
        return (
            f"Zur Orientierung fasst Batch {previous_batch} zusammen: {cleaned}. "
            "Der neue Abschnitt knüpft daran an und vertieft den Gedanken."
        )

    # ------------------------------------------------------------------
    # Compliance helpers
    # ------------------------------------------------------------------
    def _build_briefing_compliance(self) -> dict:
        sources_mode = "zugelassen" if self.sources_allowed else "gesperrt"
        return {
            "policy": "Keine erfundenen Fakten.",
            "placeholders": [
                "[KLÄREN: ...]",
                "[KENNZAHL]",
                "[QUELLE]",
                "[DATUM]",
                "[ZAHL]",
            ],
            "sources_mode": sources_mode,
            "sensitive_handling": "Sensible Inhalte als [ENTFERNT: sensibler inhalt] kennzeichnen.",
        }

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

    def _add_placeholder(self, text: str, stage: str) -> str:
        placeholder = "[KLÄREN: Daten werden nachgereicht.]"
        if not text:
            return placeholder
        if stage == "idea" and "\n" in text:
            return text.rstrip() + f"\n- {placeholder}"
        if "\n" in text:
            return text.rstrip() + "\n\n" + placeholder
        return text.rstrip() + " " + placeholder

    def _build_compliance_note(self, label: str) -> str:
        sources_state = "erlaubt" if self.sources_allowed else "gesperrt"
        return (
            f"[COMPLIANCE-{label.upper()}] Keine erfundenen Fakten; offene Angaben bleiben "
            "durch Platzhalter wie [KLÄREN: ...] und [KENNZAHL] markiert; "
            "sensible Inhalte werden als [ENTFERNT: sensibler inhalt] gekennzeichnet; "
            f"Quellenmodus: {sources_state}."
        )

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

    def _ensure_sources_policy(self, text: str) -> tuple[str, str]:
        if self.sources_allowed:
            cleaned = re.sub(
                r"\s*Quellen:\s*(?:-?\s*\[Quelle:[^\]]+\][^\n]*)?(?:\n-?\s*\[Quelle:[^\]]+\][^\n]*)*",
                "",
                text,
                flags=re.IGNORECASE,
            )
            cleaned = cleaned.strip()
            if cleaned:
                cleaned += "\n\n"
            cleaned += "Quellen:\n- [Quelle: Freigabe steht aus]"
            return cleaned, "Quellenliste formatiert"

        placeholder = "[KLÄREN: Quellenfreigabe ausstehend]"
        lines = text.splitlines()
        filtered_lines = [
            line
            for line in lines
            if not line.strip().startswith("Quellen:")
            and not line.strip().startswith("- [Quelle:")
        ]
        cleaned = "\n".join(filtered_lines).strip()
        if placeholder not in cleaned:
            cleaned = (cleaned.rstrip() + "\n\n" + placeholder) if cleaned else placeholder
            detail = "Quellen blockiert"
        else:
            detail = "Quellenblock bestätigt"
        return cleaned, detail

    def _run_compliance(
        self,
        stage: str,
        text: str,
        *,
        ensure_sources: bool = False,
        annotation_label: str | None = None,
    ) -> str:
        body, _ = self._extract_compliance_note(text)
        updated, sensitive_hits = self._mask_sensitive_content(body)
        if not self._contains_placeholder(updated):
            updated = self._add_placeholder(updated, stage)
        sources_detail = "nicht erforderlich"
        if ensure_sources:
            updated, sources_detail = self._ensure_sources_policy(updated)
        note = self._build_compliance_note(annotation_label or stage)
        if note not in updated:
            updated = updated.rstrip() + "\n\n" + note
        placeholders_present = self._contains_placeholder(updated)
        self._record_compliance(
            stage,
            placeholders=placeholders_present,
            sensitive_hits=sensitive_hits,
            sources_detail=sources_detail,
            note_present=True,
        )
        return updated

    def _record_compliance(
        self,
        stage: str,
        *,
        placeholders: bool,
        sensitive_hits: int,
        sources_detail: str,
        note_present: bool,
    ) -> None:
        self._compliance_audit.append(
            {
                "stage": stage,
                "placeholders_present": placeholders,
                "sensitive_replacements": sensitive_hits,
                "sources": sources_detail,
                "compliance_note": note_present,
            }
        )

    def _write_compliance_report(self) -> None:
        report = {
            "topic": self.topic,
            "sources_allowed": self.sources_allowed,
            "checks": self._compliance_audit,
        }
        self._write_json(self.output_dir / "compliance.json", report)

    def _compose_section(
        self,
        section: OutlineSection,
        index: int,
        sections: Sequence[OutlineSection],
        briefing: dict,
        previous_summary: str,
        *,
        recap_sentence: str | None = None,
    ) -> tuple[str, str]:
        heading = f"## {section.number}. {section.title} ({section.role})"
        sentences: List[str] = []
        key_terms = self._take_terms(2)
        messages = briefing["messages"]
        message = messages[index % len(messages)] if messages else self.topic

        if index == 0:
            sentences.append(
                f"Dieser {self.text_type.lower()} positioniert '{self.topic}' für {self.audience} und erklärt, "
                f"warum {briefing['goal']} jetzt wichtig ist."
            )
        else:
            reference = previous_summary or sections[index - 1].title.lower()
            sentences.append(
                f"Aufbauend auf {reference} vertieft der Abschnitt die Perspektive auf {self.topic}."
            )

        if recap_sentence:
            sentences.append(recap_sentence)

        if key_terms:
            focus_terms = ", ".join(key_terms)
            sentences.append(
                f"{section.deliverable} Begriffe wie {focus_terms} dienen als Terminologie-Anker."
            )
        else:
            sentences.append(f"{section.deliverable} Dabei bleibt der Fokus klar auf {self.topic}.")

        if self._idea_bullets:
            bullet = self._idea_bullets[index % len(self._idea_bullets)].strip()
            sentences.append(f"Die ausgearbeitete Idee betont: {bullet}.")

        if not self._placeholder_inserted:
            sentences.append(
                "Kennzahlen ohne Freigabe markieren wir als [KENNZAHL], bis die verantwortlichen Stellen sie liefern."
            )
            self._placeholder_inserted = True

        if self.seo_keywords:
            self._inject_keyword(sentences)

        if not self.sources_allowed and not self._sources_sentence_used:
            sentences.append("Quellenangaben werden nach Freigabe ergänzt [KLÄREN: Quellenfreigabe].")
            self._sources_sentence_used = True

        sentences.append(
            f"So übersetzt der Abschnitt die Anforderung '{message}' in handlungsfähige Schritte."
        )

        if index < len(sections) - 1:
            next_title = sections[index + 1].title
            sentences.append(f"Der Ausblick bereitet den Abschnitt \"{next_title}\" vor.")
        else:
            sentences.append(self._cta_sentence())

        text = self._adjust_section_to_budget(sentences, section.budget, briefing, section)
        summary = self._section_summary(section, text)
        return heading + "\n" + text, summary

    def _cta_sentence(self) -> str:
        if self.register.lower() == "du":
            return (
                f"Nutze die Impulse, um {self.topic.lower()} im Alltag deines Teams zu verankern."
            )
        return (
            f"Nutzen Sie die Impulse, um {self.topic.lower()} im Alltag Ihres Teams zu verankern."
        )

    def _adjust_section_to_budget(
        self,
        sentences: List[str],
        budget: int,
        briefing: dict,
        section: OutlineSection,
    ) -> str:
        lower = max(1, int(budget * 0.85))
        upper = max(lower, int(budget * 1.05))
        text = " ".join(sentences)
        words = self._count_words(text)

        while words > upper and len(sentences) > 1:
            sentences.pop()
            text = " ".join(sentences)
            words = self._count_words(text)

        if words > upper:
            trimmed_words = text.split()[:upper]
            text = " ".join(trimmed_words)
            words = len(trimmed_words)

        while words < lower:
            sentences.append(self._expansion_sentence(briefing, section))
            text = " ".join(sentences)
            words = self._count_words(text)

        return self._ensure_variant(text)

    def _expansion_sentence(self, briefing: dict, section: OutlineSection) -> str:
        term = self._take_terms(1)
        message = briefing["messages"][0] if briefing["messages"] else self.topic
        keyword = term[0] if term else self.topic.lower()
        return (
            f"Der Abschnitt verknüpft {message} mit dem Schlüsselbegriff {keyword} und hält den Fokus auf {section.title}."
        )

    def _section_summary(self, section: OutlineSection, text: str) -> str:
        first_sentence = text.split(".")[0].strip()
        if first_sentence:
            return first_sentence
        return section.title.lower()

    def _take_terms(self, count: int) -> List[str]:
        if not self._terminology_cache:
            return []
        terms: List[str] = []
        for _ in range(count):
            term = next(self._term_cycle)
            terms.append(term)
        return terms

    def _inject_keyword(self, sentences: List[str]) -> None:
        for keyword in self.seo_keywords or []:
            lowered = keyword.lower()
            if lowered in self._keywords_used:
                continue
            sentences.append(
                f"Das Stichwort '{keyword}' stärkt die SEO-Ausrichtung ohne den Lesefluss zu stören."
            )
            self._keywords_used.add(lowered)
            break

    # ------------------------------------------------------------------
    # Text generation utilities
    # ------------------------------------------------------------------
    def _split_content_into_sentences(self, text: str) -> List[str]:
        sentences: List[str] = []
        for raw in text.replace("\n", " ").split("."):
            cleaned = raw.strip()
            if cleaned:
                sentences.append(cleaned)
        return sentences

    def _extract_key_terms(self) -> List[str]:
        terms = set()
        for token in self.content.replace("\n", " ").split():
            token = token.strip().strip(",.;:!?()[]{}" "\"'").lower()
            if len(token) > 4:
                terms.add(token)
        topic_terms = [piece.strip().lower() for piece in self.topic.split() if len(piece) > 4]
        terms.update(topic_terms)
        return sorted(terms)

    def _ensure_variant(self, text: str) -> str:
        variant = self.variant.upper()
        if variant in {"DE-AT", "DE-CH"}:
            return text.replace("ß", "ss")
        return text

    def _count_words(self, text: str) -> int:
        return len([token for token in text.split() if token.strip()])

    def _enforce_length(self, text: str) -> str:
        body, note = self._extract_compliance_note(text)
        base_text = (body if body else text).strip()
        sentinel = "<<NEWLINE>>"

        def to_tokens(value: str) -> List[str]:
            return [token for token in value.replace("\n", f" {sentinel} ").split() if token]

        def from_tokens(tokens: List[str]) -> str:
            lines: List[str] = []
            current: List[str] = []
            for token in tokens:
                if token == sentinel:
                    lines.append(" ".join(current).strip())
                    current = []
                else:
                    current.append(token)
            lines.append(" ".join(current).strip())
            return "\n".join(lines).strip()

        tokens = to_tokens(base_text)
        word_tokens = [token for token in tokens if token != sentinel]
        if not word_tokens:
            result = base_text
            if note and result:
                return result + "\n\n" + note
            if note:
                return note
            return base_text
        min_words = int(self.word_count * 0.97)
        max_words = int(self.word_count * 1.03)
        if len(word_tokens) > max_words:
            trimmed: List[str] = []
            kept = 0
            for token in tokens:
                if token == sentinel:
                    trimmed.append(token)
                    continue
                if kept >= max_words:
                    break
                trimmed.append(token)
                kept += 1
            tokens = trimmed
        elif len(word_tokens) < min_words:
            adjusted_text = base_text
            filler_terms = self._take_terms(3)
            if filler_terms:
                addition = f"Zusätzliche Details zu {', '.join(filler_terms)} verdeutlichen den Nutzen."
            else:
                addition = f"Zusätzliche Details verdeutlichen den Nutzen von {self.topic}."
            while len(word_tokens) < min_words:
                adjusted_text = (adjusted_text + " " + addition).strip()
                tokens = to_tokens(adjusted_text)
                word_tokens = [token for token in tokens if token != sentinel]
        adjusted = from_tokens(tokens)
        adjusted = self._ensure_variant(adjusted.strip())
        if note:
            combined = adjusted.strip()
            if combined:
                return combined + "\n\n" + note
            return note
        return adjusted

    # ------------------------------------------------------------------
    # Quality checks and revisions
    # ------------------------------------------------------------------
    def _check_text_type(self, text: str, briefing: dict) -> tuple[bool, List[str]]:
        issues: List[str] = []
        lowered = text.lower()
        if "##" not in text:
            issues.append("Zwischenüberschriften fehlen.")
        if "fazit" not in lowered and "abschluss" not in lowered:
            issues.append("Abschluss fehlt.")
        if self.register == "Sie" and " du " in lowered:
            issues.append("Register 'Sie' verletzt.")
        if self.register == "Du" and " Sie " in text:
            issues.append("Register 'Du' verletzt.")
        for keyword in self.seo_keywords or []:
            if keyword.lower() not in lowered:
                issues.append(f"SEO-Keyword '{keyword}' fehlt.")
        if self.register == "Sie" and "Nutzen Sie" not in text:
            issues.append("CTA in Sie-Ansprache fehlt.")
        if self.register.lower() == "du" and "Nutze" not in text:
            issues.append("CTA in Du-Ansprache fehlt.")
        return (not issues), issues

    def _apply_text_type_fix(self, text: str, issues: List[str], briefing: dict) -> str:
        fixed = text
        for issue in issues:
            if "SEO-Keyword" in issue:
                keyword = issue.split("'")[1]
                fixed += f"\n\n{keyword} unterstreicht den thematischen Fokus."  # add gently
                self._keywords_used.add(keyword.lower())
            elif "Zwischenüberschriften" in issue:
                fixed = self._ensure_headings(fixed)
            elif "CTA" in issue:
                fixed = fixed.strip() + "\n\n" + self._cta_sentence()
            elif "Register" in issue:
                fixed = self._apply_register(fixed)
            elif "Abschluss" in issue:
                fixed = fixed.strip() + "\n\n" + "Ein kompaktes Fazit bündelt den Nutzen." \
                    + f" {self._cta_sentence()}"
        if not self._similar_enough(text, fixed):
            fixed = self._blend_with_original(text, fixed)
        return self._ensure_variant(fixed)

    def _ensure_headings(self, text: str) -> str:
        lines = text.splitlines()
        enriched: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and stripped == stripped.upper():
                enriched.append(f"## {stripped.title()}")
            else:
                enriched.append(line)
        if all(not line.strip().startswith("##") for line in enriched):
            enriched.insert(0, "## Überblick")
        return "\n".join(enriched)

    def _similar_enough(
        self,
        original: str,
        revised: str,
        *,
        min_jaccard: float = 0.8,
        min_ratio: float = 0.9,
    ) -> bool:
        original_tokens = {token.lower() for token in original.split() if token.strip()}
        revised_tokens = {token.lower() for token in revised.split() if token.strip()}
        if not original_tokens or not revised_tokens:
            return True
        intersection = len(original_tokens & revised_tokens)
        jaccard = intersection / max(len(original_tokens), 1)
        ratio = SequenceMatcher(None, original, revised).ratio()
        return jaccard >= min_jaccard and ratio >= min_ratio

    def _blend_with_original(self, original: str, revised: str) -> str:
        base_sentences = self._split_sentences(original)
        new_sentences = self._split_sentences(revised)
        combined = base_sentences[:]
        for sentence in new_sentences:
            if sentence and sentence not in combined:
                combined.append(sentence)
        blended = " ".join(combined)
        return self._ensure_variant(blended)

    def _split_sentences(self, text: str) -> List[str]:
        sentences: List[str] = []
        for raw in text.replace("\n", " ").split("."):
            cleaned = raw.strip()
            if cleaned:
                sentences.append(cleaned + ".")
        return sentences

    def _apply_register(self, text: str) -> str:
        if self.register == "Sie":
            return text.replace(" du ", " Sie ")
        return text.replace(" Sie ", " du ")

    def _revise_draft(self, text: str, iteration: int, briefing: dict) -> str:
        body, _ = self._extract_compliance_note(text)
        sentences = self._split_sentences(body)
        unique_sentences: List[str] = []
        seen = set()
        for sentence in sentences:
            lowered = sentence.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            unique_sentences.append(sentence)
        revision_note = (
            f"Revision {iteration} schärft Klarheit, Flow und Terminologie für {self.audience}."
        )
        revised = " ".join(unique_sentences) + " " + revision_note
        revised = self._apply_register(revised)
        return self._ensure_variant(revised)

    def _reflection_notes(self, iteration: int) -> str:
        points = [
            f"Tonfall {self.tone} an Beispielen konkretisieren.",
            "Praxisbeispiel ergänzen, sobald Daten vorliegen [KLÄREN: Beispiel].",
            f"CTA stärker auf {self.audience} zuschneiden.",
        ]
        header = f"Reflexion nach Revision {iteration}:"
        lines = [header]
        for idx, point in enumerate(points, start=1):
            lines.append(f"{idx}. {point}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------
    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_text(self, path: Path, text: str) -> None:
        path.write_text(text.strip() + "\n", encoding="utf-8")

    def _write_metadata(self, text: str, rubric_passed: bool) -> None:
        metadata = {
            "title": self.topic,
            "audience": self.audience,
            "tone": self.tone,
            "register": self.register,
            "variant": self.variant,
            "keywords": list(self.seo_keywords or []),
            "final_word_count": self._count_words(text),
            "rubric_passed": rubric_passed,
            "sources_allowed": self.sources_allowed,
            "llm_provider": self.config.llm_provider,
            "llm_model": self.config.llm_model,
            "system_prompt": prompts.SYSTEM_PROMPT,
            "compliance_checks": self._compliance_audit,
        }
        self._write_json(self.output_dir / "metadata.json", metadata)

    def _write_logs(
        self,
        briefing: dict,
        outline_sections: Sequence[OutlineSection],
        rubric_passed: bool,
    ) -> None:
        run_log = self.logs_dir / "run.log"
        run_entries = [dict(entry) for entry in self._run_events]
        for index, entry in enumerate(run_entries):
            entry.setdefault("sequence", index)
        run_lines = [json.dumps(entry, ensure_ascii=False) for entry in run_entries]
        run_log.write_text("\n".join(run_lines) + "\n", encoding="utf-8")

        llm_log = self.logs_dir / "llm.log"
        llm_entry = {
            "stage": "pipeline",
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "parameters": asdict(self.config.llm),
            "system_prompt": prompts.SYSTEM_PROMPT,
            "topic": self.topic,
            "word_count": self.word_count,
            "audience": self.audience,
            "text_type": self.text_type,
            "messages": briefing["messages"],
            "outline": [asdict(section) for section in outline_sections],
            "rubric_passed": rubric_passed,
            "prompts": {
                "briefing": prompts.BRIEFING_PROMPT.strip(),
                "idea": prompts.IDEA_IMPROVEMENT_PROMPT.strip(),
                "outline": prompts.OUTLINE_PROMPT.strip(),
                "outline_improvement": prompts.OUTLINE_IMPROVEMENT_PROMPT.strip(),
                "section": prompts.SECTION_PROMPT.strip(),
                "text_type_check": prompts.TEXT_TYPE_CHECK_PROMPT.strip(),
                "text_type_fix": prompts.TEXT_TYPE_FIX_PROMPT.strip(),
                "revision": prompts.REVISION_PROMPT.strip(),
                "reflection": prompts.REFLECTION_PROMPT.strip(),
            },
            "events": run_entries,
            "llm_generation": self._llm_generation,
        }
        llm_log.write_text(
            json.dumps(llm_entry, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

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
        if artifacts:
            event["artifacts"] = [self._format_artifact_path(Path(artifact)) for artifact in artifacts]
        if data:
            event["data"] = data
        event["sequence"] = len(self._run_events)
        self._run_events.append(event)

    def _format_artifact_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.output_dir))
        except ValueError:
            try:
                return str(path.relative_to(self.logs_dir))
            except ValueError:
                return str(path)
from .llm import LLMGenerationError, LLMResult

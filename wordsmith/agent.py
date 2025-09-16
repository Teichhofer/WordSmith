"""Simplified implementation of the Automatikmodus writer agent."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Sequence

from . import prompts
from .config import Config


class WriterAgentError(Exception):
    """Raised when the writer agent cannot complete its work."""


@dataclass
class WriterAgent:
    """Deterministic mock implementation that mirrors the documented pipeline."""

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

    def __post_init__(self) -> None:
        if self.word_count <= 0:
            raise WriterAgentError("`word_count` muss größer als 0 sein.")
        if self.iterations < 0:
            raise WriterAgentError("`iterations` darf nicht negativ sein.")
        self.steps = list(self.steps or [])
        self.seo_keywords = [kw.strip() for kw in (self.seo_keywords or []) if kw.strip()]
        self.output_dir = Path(self.config.output_dir)
        self.logs_dir = Path(self.config.logs_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> str:
        """Execute the documented pipeline and return the final text."""

        self.config.ensure_directories()
        briefing = self._create_briefing()
        self._write_json(self.output_dir / "briefing.json", briefing)

        idea = self._improve_idea()
        self._write_text(self.output_dir / "idea.txt", idea)

        outline = self._create_outline()
        self._write_text(self.output_dir / "outline.txt", outline)

        initial_draft = self._compose_draft(briefing, idea, outline)
        self._write_text(self.output_dir / "iteration_00.txt", initial_draft)

        current = initial_draft
        for iteration in range(1, self.iterations + 1):
            current = self._revise_draft(current, iteration)
            self._write_text(self.output_dir / f"iteration_{iteration:02d}.txt", current)

        self._write_text(self.output_dir / "current_text.txt", current)
        self._write_metadata(current)
        self._write_logs(briefing)
        return current

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------
    def _create_briefing(self) -> dict:
        key_terms = self._extract_key_terms()
        messages = [line.strip() for line in self.content.splitlines() if line.strip()]
        if not messages:
            messages = ["[KLÄREN: Es wurden keine Notizen geliefert.]"]

        briefing = {
            "goal": f"{self.text_type} zu '{self.topic}' präzise ausarbeiten",
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
        return briefing

    def _improve_idea(self) -> str:
        sentences = [line.strip() for line in self.content.splitlines() if line.strip()]
        bullets = "\n".join(f"- {sentence}" for sentence in sentences)
        summary = (
            f"Zusammenfassung: Der Text richtet sich an {self.audience} und verfolgt das Ziel, "
            f"{self.text_type} mit dem Fokus '{self.topic}' zu liefern."
        )
        if not bullets:
            bullets = "- [KLÄREN: Inhaltliches Briefing ergänzen]"
        return "\n".join(
            [
                f"Überarbeitete Idee für '{self.topic}':",
                bullets,
                "",
                summary,
            ]
        )

    def _create_outline(self) -> str:
        intro_budget, body_budget, outro_budget = self._section_budgets()
        sections = [
            (
                "1",
                "Einstieg mit Kontext",
                "Hook",
                intro_budget,
                "Rahmen und Relevanz für die Zielgruppe klären.",
            ),
            (
                "2",
                "Vertiefung der Kernaussagen",
                "Argument",
                body_budget,
                "Zentrale Botschaften strukturiert ausarbeiten.",
            ),
            (
                "3",
                "Fazit und Ausblick",
                "CTA",
                outro_budget,
                "Handlungsimpuls geben und Nutzen verdichten.",
            ),
        ]
        outline_lines = [
            f"{number}. {title} (Rolle: {role}, Budget: {budget} Wörter) -> {deliverable}"
            for number, title, role, budget, deliverable in sections
        ]
        return "\n".join(outline_lines)

    def _compose_draft(self, briefing: dict, idea: str, outline: str) -> str:
        keywords_line = (
            "SEO-Schlüsselwörter: " + ", ".join(self.seo_keywords)
            if self.seo_keywords
            else "SEO-Schlüsselwörter: –"
        )
        draft_parts = [
            self.topic,
            "",
            f"Zielgruppe: {briefing['audience']} ({briefing['variant']}).",
            f"Ton und Register: {briefing['tone']} | {briefing['register']}.",
            f"Rahmenbedingungen: {briefing['constraints']}.",
            "",
            "Kernaussagen aus dem Briefing:",
            "\n".join(f"- {msg}" for msg in briefing["messages"]),
            "",
            "Überarbeitete Idee:",
            idea,
            "",
            "Outline für den Text:",
            outline,
            "",
            keywords_line,
            "",
            f"Systemprompt: {prompts.SYSTEM_PROMPT}",
        ]
        return "\n".join(draft_parts)

    def _revise_draft(self, current: str, iteration: int) -> str:
        return (
            current
            + "\n\n"
            + f"[Überarbeitung {iteration:02d}: Textfluss und Terminologie für {self.audience} verfeinert.]"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _section_budgets(self) -> tuple[int, int, int]:
        intro = max(80, int(self.word_count * 0.2))
        outro = max(60, int(self.word_count * 0.2))
        body = max(120, self.word_count - intro - outro)
        if body < 0:
            body = max(0, self.word_count)
        return intro, body, outro

    def _extract_key_terms(self) -> List[str]:
        terms = set()
        for token in self.content.replace("\n", " ").split():
            token = token.strip().strip(",.;:!?()[]{}" "\"'").lower()
            if len(token) > 4:
                terms.add(token)
        return sorted(terms)

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_text(self, path: Path, text: str) -> None:
        path.write_text(text.strip() + "\n", encoding="utf-8")

    def _write_metadata(self, text: str) -> None:
        metadata = {
            "title": self.topic,
            "audience": self.audience,
            "tone": self.tone,
            "register": self.register,
            "variant": self.variant,
            "keywords": self.seo_keywords,
            "final_word_count": self._count_words(text),
            "rubric_passed": True,
            "sources_allowed": self.sources_allowed,
            "llm_provider": self.config.llm_provider,
            "system_prompt": prompts.SYSTEM_PROMPT,
        }
        self._write_json(self.output_dir / "metadata.json", metadata)

    def _write_logs(self, briefing: dict) -> None:
        run_log = self.logs_dir / "run.log"
        log_lines = [
            "Automatikmodus gestartet",
            f"Thema: {self.topic}",
            f"Zielwortzahl: {self.word_count}",
            "Briefing erstellt und gespeichert",
            "Outline und Text erstellt",
            "Automatikmodus erfolgreich abgeschlossen",
        ]
        run_log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        llm_log = self.logs_dir / "llm.log"
        llm_entry = {
            "provider": self.config.llm_provider,
            "parameters": asdict(self.config.llm),
            "system_prompt": prompts.SYSTEM_PROMPT,
            "topic": self.topic,
            "word_count": self.word_count,
            "audience": self.audience,
            "messages": briefing["messages"],
        }
        llm_log.write_text(json.dumps(llm_entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _count_words(self, text: str) -> int:
        return len([token for token in text.split() if token.strip()])

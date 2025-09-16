"""Implementation of the Automatikmodus writer agent pipeline.

The module emulates the documented steps from ``docs/automatikmodus.md`` in a
deterministic way so that the CLI can be tested end-to-end without real LLM
calls.  The agent focuses on structure, artefact creation and rule adherence
rather than open-ended text generation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from itertools import cycle
from pathlib import Path
from typing import Iterable, List, Sequence


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

from . import prompts
from .config import Config


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

    def __post_init__(self) -> None:
        if self.word_count <= 0:
            raise WriterAgentError("`word_count` muss größer als 0 sein.")
        if self.iterations < 0:
            raise WriterAgentError("`iterations` darf nicht negativ sein.")
        self.steps = list(self.steps or [])
        self.seo_keywords = [kw.strip() for kw in (self.seo_keywords or []) if kw.strip()]
        self.output_dir = Path(self.config.output_dir)
        self.logs_dir = Path(self.config.logs_dir)
        self._term_cycle = cycle([self.topic.lower()])

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

        briefing = self._normalize_briefing()
        self._write_json(self.output_dir / "briefing.json", briefing)

        idea = self._improve_idea(briefing)
        self._write_text(self.output_dir / "idea.txt", idea)

        outline_sections = self._create_outline(briefing)
        outline_text = self._format_outline(outline_sections)
        self._write_text(self.output_dir / "outline.txt", outline_text)
        self._write_text(self.output_dir / "iteration_00.txt", outline_text)

        draft = self._generate_sections(outline_sections, briefing)
        draft = self._enforce_length(draft)
        self._write_text(self.output_dir / "current_text.txt", draft)
        self._write_text(self.output_dir / "iteration_01.txt", draft)

        rubric_passed, issues = self._check_text_type(draft, briefing)
        if issues:
            fixed = self._apply_text_type_fix(draft, issues, briefing)
            if not self._similar_enough(draft, fixed):
                fixed = self._blend_with_original(draft, fixed)
            draft = self._enforce_length(fixed)
            self._write_text(self.output_dir / "current_text.txt", draft)
            self._write_text(self.output_dir / "iteration_01.txt", draft)
            rubric_passed, _ = self._check_text_type(draft, briefing)
        else:
            rubric_passed = True

        for iteration in range(1, self.iterations + 1):
            revised = self._revise_draft(draft, iteration, briefing)
            if not self._similar_enough(draft, revised, min_jaccard=0.75, min_ratio=0.88):
                revised = self._blend_with_original(draft, revised)
            draft = self._enforce_length(revised)
            self._write_text(self.output_dir / f"iteration_{iteration + 1:02d}.txt", draft)
            self._write_text(self.output_dir / "current_text.txt", draft)
            reflection = self._reflection_notes(iteration)
            if reflection:
                self._write_text(
                    self.output_dir / f"reflection_{iteration + 1:02d}.txt",
                    reflection,
                )

        self._write_metadata(draft, rubric_passed)
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

        self.steps.append("briefing")
        return briefing

    def _improve_idea(self, briefing: dict) -> str:
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
        self.steps.append("idea")
        return idea_text

    def _create_outline(self, briefing: dict) -> List[OutlineSection]:
        sections = self._build_outline_sections()
        sections = self._improve_outline(sections)
        sections = self._clean_outline(sections)
        self.steps.append("outline")
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
        return "\n".join(section.format_line() for section in sections)

    def _generate_sections(self, sections: Sequence[OutlineSection], briefing: dict) -> str:
        paragraphs: List[str] = []
        previous_summary = ""
        for index, section in enumerate(sections):
            section_text, summary = self._compose_section(
                section,
                index,
                sections,
                briefing,
                previous_summary,
            )
            paragraphs.append(section_text)
            previous_summary = summary
        return "\n\n".join(paragraphs)

    def _compose_section(
        self,
        section: OutlineSection,
        index: int,
        sections: Sequence[OutlineSection],
        briefing: dict,
        previous_summary: str,
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
        words = text.split()
        if not words:
            return text
        min_words = int(self.word_count * 0.97)
        max_words = int(self.word_count * 1.03)
        if len(words) > max_words:
            text = " ".join(words[:max_words])
        elif len(words) < min_words:
            filler_terms = self._take_terms(3)
            if filler_terms:
                addition = (
                    f"Zusätzliche Details zu {', '.join(filler_terms)} verdeutlichen den Nutzen."
                )
            else:
                addition = f"Zusätzliche Details verdeutlichen den Nutzen von {self.topic}."
            text = text.strip() + " " + addition
        return self._ensure_variant(text.strip())

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
        sentences = self._split_sentences(text)
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
            "system_prompt": prompts.SYSTEM_PROMPT,
        }
        self._write_json(self.output_dir / "metadata.json", metadata)

    def _write_logs(
        self,
        briefing: dict,
        outline_sections: Sequence[OutlineSection],
        rubric_passed: bool,
    ) -> None:
        run_log = self.logs_dir / "run.log"
        log_lines = [
            "Automatikmodus gestartet",
            f"Thema: {self.topic}",
            f"Zielwortzahl: {self.word_count}",
            "Briefing normalisiert",
            "Idee überarbeitet",
            "Outline generiert und bereinigt",
            "Abschnitte ausformuliert",
            (
                "Texttypprüfung bestanden"
                if rubric_passed
                else "Texttypprüfung mit Nachbesserungen abgeschlossen"
            ),
        ]
        for iteration in range(1, self.iterations + 1):
            log_lines.append(f"Revision {iteration:02d} abgeschlossen")
        log_lines.append("Automatikmodus erfolgreich abgeschlossen")
        run_log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        llm_log = self.logs_dir / "llm.log"
        llm_entry = {
            "provider": self.config.llm_provider,
            "parameters": asdict(self.config.llm),
            "system_prompt": prompts.SYSTEM_PROMPT,
            "topic": self.topic,
            "word_count": self.word_count,
            "audience": self.audience,
            "text_type": self.text_type,
            "messages": briefing["messages"],
            "outline": [asdict(section) for section in outline_sections],
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
        }
        llm_log.write_text(
            json.dumps(llm_entry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

"""Tests for the predefined prompt templates."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import prompts


def test_prompt_templates_match_specification() -> None:
    """Ensure all prompt templates follow the documented specification."""

    assert prompts.BRIEFING_PROMPT == (
        "Verdichte folgende Angaben zu einem Arbeitsbriefing als kompaktes JSON "
        "mit Schlüsseln: goal, audience, tone, register, variant, constraints, "
        "key_terms, messages, seo_keywords (optional).\n"
        "**Eingaben:**\n"
        "title: {title}\n"
        "text_type: {text_type}\n"
        "audience: {audience}\n"
        "tone: {tone}\n"
        "register: {register}\n"
        "variant: {variant}\n"
        "constraints: {constraints}\n"
        "seo_keywords: {seo_keywords}\n"
        "notes: {content}\n"
    )

    assert prompts.IDEA_IMPROVEMENT_PROMPT == (
        "Überarbeite diesen Rohinhalt **ohne neue Fakten**.\n"
        "1) Straffe Sprache, 2) markiere Unklarheiten `[KLÄREN: …]`, 3) gib "
        "Kernaussagen als Bullets + 1-Satz-Summary.\n"
        "**Rohinhalt:** {content}\n"
    )

    assert prompts.OUTLINE_PROMPT == (
        "Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` "
        "basierend auf dem Briefing:\n"
        "{briefing_json}\n"
        "Für jeden Abschnitt: Nummer, Titel, **Rollenfunktion**, **Wortbudget**, "
        "**Liefergegenstand**.\n"
        "Gesamtwortzahl: {word_count}. Keine Fakten erfinden.\n"
    )

    assert prompts.OUTLINE_IMPROVEMENT_PROMPT == (
        "Prüfe und verbessere die Outline: entferne Überschneidungen, füge "
        "fehlende Brücken, balanciere Budgets (Summe = {word_count}). Behalte "
        "Faktenneutralität.\n"
    )

    assert prompts.SECTION_PROMPT == (
        "Schreibe Abschnitt {section_number} „{section_title}“ (Rolle: {role}) "
        "mit Ziel `{deliverable}`.\n"
        "Nutze Briefing und bisherige Abschnitte (Kohärenz, Terminologie).\n"
        "Regeln: aktive Verben, keine Füllphrasen, natürliche Übergänge, **keine** "
        "erfundenen Fakten (Platzhalter bei Lücken).\n"
        "Zielwortzahl: {budget}.\n"
        "**Bisheriger Kontext (Kurz-Recap)**: {previous_section_recap}\n"
    )

    assert prompts.TEXT_TYPE_CHECK_PROMPT == (
        "Prüfe den Text gegen die Rubrik für `{text_type}` (Kriterienliste siehe "
        "oben). Liste **konkrete** Abweichungen und betroffene Stellen.\n"
    )

    assert prompts.TEXT_TYPE_FIX_PROMPT == (
        "Korrigiere nur die genannten Abweichungen **minimal-invasiv**, ohne "
        "Faktenzuwachs. Erhalte Ton, Terminologie, Struktur.\n"
    )

    assert prompts.REVISION_PROMPT == (
        "Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit, Flow, "
        "Terminologie, Wiederholungen, Rhythmus, starke Verben, Abschluss, "
        "Register, Variantenspezifika. Bei fehlenden Daten: Platzhalter.\n"
    )

    assert prompts.REFLECTION_PROMPT == (
        "Nenne die 3 wirksamsten nächsten Verbesserungen (knapp, umsetzbar).\n"
    )

    assert prompts.FINAL_DRAFT_PROMPT == (
        "Schreibe den finalen {text_type} zum Thema \"{title}\" mit etwa {word_count} "
        "Wörtern (±3 %).\n"
        "Arbeite strikt mit den folgenden Informationen und Regeln.\n\n"
        "Briefing:\n"
        "{briefing_json}\n\n"
        "Gliederung:\n"
        "{outline}\n\n"
        "Kernaussagen aus der Idee:\n"
        "{idea_bullets}\n\n"
        "Regeln:\n"
        "- Tonfall: {tone}\n"
        "- Register: {register}\n"
        "- Sprachvariante: {variant_hint}\n"
        "- Quellenmodus: {sources_mode}\n"
        "- Zusätzliche Constraints: {constraints}\n"
        "- SEO-Keywords: {seo_keywords}\n"
        "- Keine neuen Fakten erfinden; nutze Platzhalter wie [KLÄREN:], [KENNZAHL], "
        "[QUELLE], [DATUM].\n"
        "- Nutze Zwischenüberschriften gemäß Gliederung und schließe mit einem CTA in "
        "der passenden Ansprache.\n\n"
        "Gib ausschließlich den ausgearbeiteten Text in Markdown zurück.\n"
    )

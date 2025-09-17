"""Prompt templates and shared system prompt for WordSmith."""

SYSTEM_PROMPT: str = (
    "Du bist ein präziser deutschsprachiger Fachtexter. Du erfindest keine "
    "Fakten. Bei fehlenden Daten nutzt du Platzhalter in eckigen Klammern. "
    "Deine Texte sind klar strukturiert, aktiv formuliert, redundanzarm "
    "und adressatengerecht."
)

# Normalisiert die Eingaben zu einem strukturierten Arbeitsbriefing.
BRIEFING_PROMPT: str = """\
Verdichte folgende Angaben zu einem Arbeitsbriefing als kompaktes JSON mit Schlüsseln: goal, audience, tone, register, variant, constraints, key_terms, messages, seo_keywords (optional).
Gib ausschließlich ein JSON-Objekt ohne erläuternden Text zurück.
**Eingaben:**
title: {title}
text_type: {text_type}
audience: {audience}
tone: {tone}
register: {register}
variant: {variant}
constraints: {constraints}
seo_keywords: {seo_keywords}
notes: {content}
"""

# Strafft und strukturiert die Ausgangsidee ohne neue Fakten.
IDEA_IMPROVEMENT_PROMPT: str = """\
Überarbeite diesen Rohinhalt **ohne neue Fakten**.
1) Straffe Sprache, 2) markiere Unklarheiten `[KLÄREN: …]`, 3) gib Kernaussagen als Bullets + 1-Satz-Summary.
**Rohinhalt:** {content}
"""

# Baut eine detaillierte Outline mit Rollen, Budgets und Deliverables.
OUTLINE_PROMPT: str = """\
Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` basierend auf dem Briefing:
{briefing_json}
Für jeden Abschnitt: Nummer, Titel, **Rollenfunktion**, **Wortbudget**, **Liefergegenstand**.
Gesamtwortzahl: {word_count}. Keine Fakten erfinden.
"""

# Verfeinert die Outline und balanciert Wortbudgets ohne Faktenzugabe.
OUTLINE_IMPROVEMENT_PROMPT: str = """\
Prüfe und verbessere die Outline: entferne Überschneidungen, füge fehlende Brücken, balanciere Budgets (Summe = {word_count}). Behalte Faktenneutralität.
"""

# Generiert Abschnittstexte kohärent zu Briefing, Outline und Vorabschnitten.
SECTION_PROMPT: str = """\
Schreibe Abschnitt {section_number} „{section_title}“ (Rolle: {role}) mit Ziel `{deliverable}`.
Nutze Briefing und bisherige Abschnitte (Kohärenz, Terminologie).
Regeln: aktive Verben, keine Füllphrasen, natürliche Übergänge, **keine** erfundenen Fakten (Platzhalter bei Lücken).
Zielwortzahl: {budget}.
**Bisheriger Kontext (Kurz-Recap)**: {previous_section_recap}
"""

# Prüft den Gesamttext gegen die Rubrik für den angegebenen Texttyp.
TEXT_TYPE_CHECK_PROMPT: str = """\
Prüfe den Text gegen die Rubrik für `{text_type}` (Kriterienliste siehe oben). Liste **konkrete** Abweichungen und betroffene Stellen.
"""

# Korrigiert minimal die in der Prüfung gefundenen Abweichungen.
TEXT_TYPE_FIX_PROMPT: str = """\
Korrigiere nur die genannten Abweichungen **minimal-invasiv**, ohne Faktenzuwachs. Erhalte Ton, Terminologie, Struktur.
"""

# Führt gezielte sprachliche Revisionen entlang der Qualitätsprioritäten durch.
REVISION_PROMPT: str = """\
Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit, Flow, Terminologie, Wiederholungen, Rhythmus, starke Verben, Abschluss, Register, Variantenspezifika. Bei fehlenden Daten: Platzhalter.
"""

# Hält optionale Reflexionsnotizen zu weiteren Verbesserungsmöglichkeiten fest.
REFLECTION_PROMPT: str = """\
Nenne die 3 wirksamsten nächsten Verbesserungen (knapp, umsetzbar).
"""


FINAL_DRAFT_PROMPT: str = """\
Schreibe den finalen {text_type} zum Thema "{title}" mit etwa {word_count} Wörtern (±3 %).
Arbeite strikt mit den folgenden Informationen und Regeln.

Briefing:
{briefing_json}

Gliederung:
{outline}

Kernaussagen aus der Idee:
{idea_bullets}

Regeln:
- Tonfall: {tone}
- Register: {register}
- Sprachvariante: {variant_hint}
- Quellenmodus: {sources_mode}
- Zusätzliche Constraints: {constraints}
- SEO-Keywords: {seo_keywords}
- Keine neuen Fakten erfinden; nutze Platzhalter wie [KLÄREN:], [KENNZAHL], [QUELLE], [DATUM].
- Nutze Zwischenüberschriften gemäß Gliederung und schließe mit einem CTA in der passenden Ansprache.

Gib ausschließlich den ausgearbeiteten Text in Markdown zurück.
"""


def set_system_prompt(prompt: str) -> None:
    """Update the globally shared system prompt."""

    global SYSTEM_PROMPT
    SYSTEM_PROMPT = prompt

"""Prompt templates used by WriterAgent."""

from __future__ import annotations

_DEFAULT_SYSTEM_PROMPT = (
    "Du bist ein kreativer deutschsprachiger Autor. Du erfindest keine Fakten. "
    "Vermeide Wiederholungen und Füllwörter. Deine Texte sind klar strukturiert, "
    "aktiv formuliert, redundanzarm und adressatengerecht."
)

SYSTEM_PROMPT: str = _DEFAULT_SYSTEM_PROMPT


def set_system_prompt(prompt: str | None) -> None:
    """Configure the system prompt for subsequent LLM interactions."""

    global SYSTEM_PROMPT

    if prompt is None:
        SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
        return

    cleaned = str(prompt).strip()
    SYSTEM_PROMPT = cleaned or _DEFAULT_SYSTEM_PROMPT


BRIEFING_PROMPT = """\
Verdichte folgende Angaben zu einem konsistenten Arbeitsbriefing als strikt valides JSON-Objekt (UTF-8, ohne Kommentare).
Erstelle genau die Schlüssel: goal, audience, tone, register, variant, constraints, key_terms, messages, seo_keywords (optional).
- Formuliere `goal` als prägnanten Zielsatz.
- Gib `audience`, `tone`, `register`, `variant`, `constraints` als getrimmte Strings zurück (fehlende Angaben → `[KLÄREN: …]`).
- Liste `key_terms`, `messages` und `seo_keywords` als Arrays mit einzelnen Strings (fehlende Angaben → leeres Array; Einträge trimmen, Duplikate entfernen).
- Interpretiere Eingaben wie „keine“ oder leere Werte bei Keywords als leeres Array.
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

IDEA_IMPROVEMENT_PROMPT = """\
Überarbeite diesen Rohinhalt **ohne neue Fakten** und in der vorhandenen Sprache.
Liefere das Ergebnis in folgender Markdown-Struktur:
1. **Überarbeitete Fassung:** optimierter Fließtext mit klarer Dramaturgie.
2. **Unklarheiten:** Bullet-Liste mit `[KLÄREN: …]`-Hinweisen für Informationslücken.
3. **Kernaussagen:** Bullet-Liste der wichtigsten Aussagen (ein Bullet pro Gedanke).
4. **Summary:** exakt ein Satz, der die Idee kondensiert.
**Rohinhalt:** {content}
"""

OUTLINE_PROMPT = """\
Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` basierend auf dem Briefing:
{briefing_json}
Nutze nummerierte Einträge (`1.`, `1.1` …) mit dem Format `{{nummer}}. {{Titel}} (Rolle: …; Wortbudget: …; Liefergegenstand: …)`.
Berücksichtige strategische Übergänge und stelle sicher, dass die Wortbudgets in Summe {word_count} Wörter ergeben (Rundungen dokumentieren).
Keine Fakten erfinden; nutze bei Bedarf Platzhalter.
"""

OUTLINE_IMPROVEMENT_PROMPT = """\
Prüfe und verbessere die Outline: entferne Überschneidungen, füge fehlende Brücken, balanciere Budgets (Summe = {word_count}).
Vorgehen:
1. Liste konkrete Probleme oder Risiken (Stichpunkte).
2. Präsentiere die optimierte Outline im Format `{{nummer}}. {{Titel}} (Rolle: …; Wortbudget: …; Liefergegenstand: …)`.
3. Bestätige die Gesamtsumme als `Gesamt: {word_count} Wörter` (Rundungsabweichungen begründen).
Behalte Faktenneutralität.
"""

SECTION_PROMPT = """\
Schreibe Abschnitt {section_number} „{section_title}“ (Rolle: {role}) mit Ziel `{deliverable}`.
Nutze Briefing, Outline und bisherige Abschnitte für Kohärenz, Terminologie und Übergänge.
Regeln:
- Liefere ausschließlich den Abschnittsfließtext ohne eigene Überschrift.
- Verwende aktive Verben, vermeide Füllphrasen und halte das Register konsistent.
- Knüpfe an den vorherigen Abschnitt an und baue einen logischen Ausblick auf den nächsten.
- **Keine** erfundenen Fakten; fehlende Details → Platzhalter in eckigen Klammern.
Zielwortzahl: {budget}.
**Bisheriger Kontext (Kurz-Recap)**: {previous_section_recap}
"""

TEXT_TYPE_CHECK_PROMPT = """\
Prüfe den Text gegen die Rubrik für `{text_type}` (Kriterienliste siehe oben).
Strukturiere deine Antwort so:
1. **Gesamturteil:** `PASS` oder `FAIL` mit kurzer Begründung.
2. **Abweichungen:** Markdown-Tabelle mit Spalten `Kriterium | Beschreibung | Fundstelle | Dringlichkeit`. Wenn keine Abweichungen vorliegen, schreibe `Keine Abweichungen`.
3. **Empfehlungen:** Bullet-Liste mit umsetzbaren Korrekturschritten.
"""

TEXT_TYPE_FIX_PROMPT = """\
Korrigiere nur die genannten Abweichungen **minimal-invasiv**, ohne Faktenzuwachs. Erhalte Ton, Terminologie, Struktur.
Vorgehen:
1. Übernimm ausschließlich die notwendigen Änderungen direkt im Text (keine Anmerkungen).
2. Bewahre Formatierung, Abschnittsüberschriften und Wortbudgets soweit möglich.
3. Nutze vorhandene Platzhalter weiter oder markiere neue Informationslücken mit `[KLÄREN: …]`.
Gib nur den aktualisierten Text zurück.
"""

REVISION_PROMPT = """\
Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit, Flow, Terminologie, Wiederholungen, Rhythmus, starke Verben, Abschluss, Register, Variantenspezifika.
Arbeite Schritt für Schritt: plane die Eingriffe kurz, führe sie dann aus.
Liefere den überarbeiteten Text in Markdown ohne Meta-Kommentare; bei fehlenden Daten setze Platzhalter.
"""

COMPLIANCE_HINT_INSTRUCTION = (
    "Falls Compliance-Hinweise nötig sind, füge sie als separate Zeile im Format `[COMPLIANCE-HINWEIS: …]` am Ende an."
)


def build_revision_prompt(include_compliance_hint: bool = False) -> str:
    """Return the revision prompt, optionally with the compliance hint appended."""

    prompt = REVISION_PROMPT.strip()
    if include_compliance_hint:
        return f"{prompt}\n{COMPLIANCE_HINT_INSTRUCTION}"
    return prompt


REFLECTION_PROMPT = """\
Nenne die 3 wirksamsten nächsten Verbesserungen als priorisierte Markdown-Liste (1 = höchste Wirkung).
Jeder Punkt: maximal 15 Wörter, klar umsetzbar, mit Hinweis auf den betroffenen Abschnitt.
"""

FINAL_DRAFT_PROMPT = """\
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
- Übernehme Zwischenüberschriften exakt gemäß Gliederung (`## {{nummer}}. {{Titel}}`) und halte die Wortbudgets pro Abschnitt grob ein.
- Sorg für einen packenden Einstieg, klare Übergänge zwischen den Abschnitten und einen CTA, der die adressierte Zielgruppe anspricht.
- Nutze Keywords natürlich im Fließtext und optimiere für Lesbarkeit und SEO.

Gib ausschließlich den ausgearbeiteten Text in Markdown zurück.
"""

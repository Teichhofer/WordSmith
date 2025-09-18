"""Tests for the predefined prompt templates."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import prompts


def test_prompt_templates_match_specification() -> None:
    """Ensure all prompt templates follow the documented specification."""

    assert prompts.BRIEFING_PROMPT == """\
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

    assert prompts.IDEA_IMPROVEMENT_PROMPT == """\
Überarbeite diesen Rohinhalt **ohne neue Fakten** und in der vorhandenen Sprache.
Liefere das Ergebnis in folgender Markdown-Struktur:
1. **Überarbeitete Fassung:** optimierter Fließtext mit klarer Dramaturgie.
2. **Unklarheiten:** Bullet-Liste mit `[KLÄREN: …]`-Hinweisen für Informationslücken.
3. **Kernaussagen:** Bullet-Liste der wichtigsten Aussagen (ein Bullet pro Gedanke).
4. **Summary:** exakt ein Satz, der die Idee kondensiert.
**Rohinhalt:** {content}
"""

    assert prompts.OUTLINE_PROMPT == """\
Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` basierend auf dem Briefing:
{briefing_json}
Nutze nummerierte Einträge (`1.`, `1.1` …) mit dem Format `{{nummer}}. {{Titel}} (Rolle: …; Wortbudget: …; Liefergegenstand: …)`.
Berücksichtige strategische Übergänge und stelle sicher, dass die Wortbudgets in Summe {word_count} Wörter ergeben (Rundungen dokumentieren).
Keine Fakten erfinden; nutze bei Bedarf Platzhalter.
"""

    assert prompts.OUTLINE_IMPROVEMENT_PROMPT == """\
Prüfe und verbessere die Outline: entferne Überschneidungen, füge fehlende Brücken, balanciere Budgets (Summe = {word_count}).
Vorgehen:
1. Liste konkrete Probleme oder Risiken (Stichpunkte).
2. Präsentiere die optimierte Outline im Format `{{nummer}}. {{Titel}} (Rolle: …; Wortbudget: …; Liefergegenstand: …)`.
3. Bestätige die Gesamtsumme als `Gesamt: {word_count} Wörter` (Rundungsabweichungen begründen).
Behalte Faktenneutralität.
"""

    assert prompts.SECTION_PROMPT == """\
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

    assert prompts.TEXT_TYPE_CHECK_PROMPT == """\
Prüfe den Text gegen die Rubrik für `{text_type}` (Kriterienliste siehe oben).
Strukturiere deine Antwort so:
1. **Gesamturteil:** `PASS` oder `FAIL` mit kurzer Begründung.
2. **Abweichungen:** Markdown-Tabelle mit Spalten `Kriterium | Beschreibung | Fundstelle | Dringlichkeit`. Wenn keine Abweichungen vorliegen, schreibe `Keine Abweichungen`.
3. **Empfehlungen:** Bullet-Liste mit umsetzbaren Korrekturschritten.
"""

    assert prompts.TEXT_TYPE_FIX_PROMPT == """\
Korrigiere nur die genannten Abweichungen **minimal-invasiv**, ohne Faktenzuwachs. Erhalte Ton, Terminologie, Struktur.
Vorgehen:
1. Übernimm ausschließlich die notwendigen Änderungen direkt im Text (keine Anmerkungen).
2. Bewahre Formatierung, Abschnittsüberschriften und Wortbudgets soweit möglich.
3. Nutze vorhandene Platzhalter weiter oder markiere neue Informationslücken mit `[KLÄREN: …]`.
Gib nur den aktualisierten Text zurück.
"""

    assert prompts.REVISION_PROMPT == """\
Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit, Flow, Terminologie, Wiederholungen, Rhythmus, starke Verben, Abschluss, Register, Variantenspezifika.
Arbeite Schritt für Schritt: plane die Eingriffe kurz, führe sie dann aus.
Liefere den überarbeiteten Text in Markdown ohne Meta-Kommentare; bei fehlenden Daten setze Platzhalter.
Falls Compliance-Hinweise nötig sind, füge sie als separate Zeile im Format `[COMPLIANCE-HINWEIS: …]` am Ende an.
"""

    assert prompts.REFLECTION_PROMPT == """\
Nenne die 3 wirksamsten nächsten Verbesserungen als priorisierte Markdown-Liste (1 = höchste Wirkung).
Jeder Punkt: maximal 15 Wörter, klar umsetzbar, mit Hinweis auf den betroffenen Abschnitt.
"""

    assert prompts.FINAL_DRAFT_PROMPT == """\
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

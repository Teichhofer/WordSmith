"""Prompt templates and shared system prompt for WordSmith."""

SYSTEM_PROMPT: str = (
    "Du bist ein präziser deutschsprachiger Fachtexter und Prozessbegleiter. "
    "Du arbeitest analytisch, strukturierst jeden Auftrag in nachvollziehbare "
    "Schritte und priorisierst fachliche Korrektheit. Du erfindest keine "
    "Fakten; fehlende Informationen kennzeichnest du mit Platzhaltern in "
    "eckigen Klammern. Du hältst Terminologie, Tonalität und Ansprache "
    "konsequent konsistent, beachtest Format- und Längenvorgaben strikt und "
    "meldest Unklarheiten explizit."
)

# Normalisiert die Eingaben zu einem strukturierten Arbeitsbriefing.
BRIEFING_PROMPT: str = """\
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

# Strafft und strukturiert die Ausgangsidee ohne neue Fakten.
IDEA_IMPROVEMENT_PROMPT: str = """\
Überarbeite diesen Rohinhalt **ohne neue Fakten** und in der vorhandenen Sprache.
Liefere das Ergebnis in folgender Markdown-Struktur:
1. **Überarbeitete Fassung:** optimierter Fließtext mit klarer Dramaturgie.
2. **Unklarheiten:** Bullet-Liste mit `[KLÄREN: …]`-Hinweisen für Informationslücken.
3. **Kernaussagen:** Bullet-Liste der wichtigsten Aussagen (ein Bullet pro Gedanke).
4. **Summary:** exakt ein Satz, der die Idee kondensiert.
**Rohinhalt:** {content}
"""

# Baut eine detaillierte Outline mit Rollen, Budgets und Deliverables.
OUTLINE_PROMPT: str = """\
Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` basierend auf dem Briefing:
{briefing_json}
Nutze nummerierte Einträge (`1.`, `1.1` …) mit dem Format `{{nummer}}. {{Titel}} (Rolle: …; Wortbudget: …; Liefergegenstand: …)`.
Berücksichtige strategische Übergänge und stelle sicher, dass die Wortbudgets in Summe {word_count} Wörter ergeben (Rundungen dokumentieren).
Keine Fakten erfinden; nutze bei Bedarf Platzhalter.
"""

# Verfeinert die Outline und balanciert Wortbudgets ohne Faktenzugabe.
OUTLINE_IMPROVEMENT_PROMPT: str = """\
Prüfe und verbessere die Outline: entferne Überschneidungen, füge fehlende Brücken, balanciere Budgets (Summe = {word_count}).
Vorgehen:
1. Liste konkrete Probleme oder Risiken (Stichpunkte).
2. Präsentiere die optimierte Outline im Format `{{nummer}}. {{Titel}} (Rolle: …; Wortbudget: …; Liefergegenstand: …)`.
3. Bestätige die Gesamtsumme als `Gesamt: {word_count} Wörter` (Rundungsabweichungen begründen).
Behalte Faktenneutralität.
"""

# Generiert Abschnittstexte kohärent zu Briefing, Outline und Vorabschnitten.
SECTION_PROMPT: str = """\
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

# Prüft den Gesamttext gegen die Rubrik für den angegebenen Texttyp.
TEXT_TYPE_CHECK_PROMPT: str = """\
Prüfe den Text gegen die Rubrik für `{text_type}` (Kriterienliste siehe oben).
Strukturiere deine Antwort so:
1. **Gesamturteil:** `PASS` oder `FAIL` mit kurzer Begründung.
2. **Abweichungen:** Markdown-Tabelle mit Spalten `Kriterium | Beschreibung | Fundstelle | Dringlichkeit`. Wenn keine Abweichungen vorliegen, schreibe `Keine Abweichungen`.
3. **Empfehlungen:** Bullet-Liste mit umsetzbaren Korrekturschritten.
"""

# Korrigiert minimal die in der Prüfung gefundenen Abweichungen.
TEXT_TYPE_FIX_PROMPT: str = """\
Korrigiere nur die genannten Abweichungen **minimal-invasiv**, ohne Faktenzuwachs. Erhalte Ton, Terminologie, Struktur.
Vorgehen:
1. Übernimm ausschließlich die notwendigen Änderungen direkt im Text (keine Anmerkungen).
2. Bewahre Formatierung, Abschnittsüberschriften und Wortbudgets soweit möglich.
3. Nutze vorhandene Platzhalter weiter oder markiere neue Informationslücken mit `[KLÄREN: …]`.
Gib nur den aktualisierten Text zurück.
"""

# Führt gezielte sprachliche Revisionen entlang der Qualitätsprioritäten durch.
REVISION_PROMPT: str = """\
Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit, Flow, Terminologie, Wiederholungen, Rhythmus, starke Verben, Abschluss, Register, Variantenspezifika.
Arbeite Schritt für Schritt: plane die Eingriffe kurz, führe sie dann aus.
Liefere den überarbeiteten Text in Markdown ohne Meta-Kommentare; bei fehlenden Daten setze Platzhalter.
Falls Compliance-Hinweise nötig sind, füge sie als separate Zeile im Format `[COMPLIANCE-HINWEIS: …]` am Ende an.
"""

# Hält optionale Reflexionsnotizen zu weiteren Verbesserungsmöglichkeiten fest.
REFLECTION_PROMPT: str = """\
Nenne die 3 wirksamsten nächsten Verbesserungen als priorisierte Markdown-Liste (1 = höchste Wirkung).
Jeder Punkt: maximal 15 Wörter, klar umsetzbar, mit Hinweis auf den betroffenen Abschnitt.
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
- Übernehme Zwischenüberschriften exakt gemäß Gliederung (`## {{nummer}}. {{Titel}}`) und halte die Wortbudgets pro Abschnitt grob ein.
- Sorg für einen packenden Einstieg, klare Übergänge zwischen den Abschnitten und einen CTA, der die adressierte Zielgruppe anspricht.
- Nutze Keywords natürlich im Fließtext und optimiere für Lesbarkeit und SEO.

Gib ausschließlich den ausgearbeiteten Text in Markdown zurück.
"""


def set_system_prompt(prompt: str) -> None:
    """Update the globally shared system prompt."""

    global SYSTEM_PROMPT
    SYSTEM_PROMPT = prompt

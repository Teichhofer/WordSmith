"""Prompt templates used by WriterAgent."""

# Global system prompt used for all LLM calls in automatic mode
SYSTEM_PROMPT = (
    "Du bist ein präziser deutschsprachiger Fachtexter. "
    "Du erfindest keine Fakten. Bei fehlenden Daten nutzt du Platzhalter in eckigen Klammern. "
    "Deine Texte sind klar strukturiert, aktiv formuliert, redundanzarm und adressatengerecht. "
    "Vermeide Wiederholungen und Füllwörter und achte besonders auf die inhaltliche Qualität des Textes. "
    "Dein Thema lautet: {topic}. Du verfasst einen {text_type}."
)

# ---------------------------------------------------------------------------
# Prompts for the revised automatic mode

BRIEFING_PROMPT = (
    "Verdichte folgende Angaben zu einem Arbeitsbriefing als kompaktes JSON mit Schlüsseln: "
    "goal, audience, tone, register, variant, constraints, key_terms, messages, seo_keywords (optional).\n"
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

IDEA_IMPROVEMENT_SYSTEM_PROMPT = (
    "Du überarbeitest Ideen, korrigierst Rechtschreib- und Grammatikfehler und formulierst sie klarer."
)

IDEA_IMPROVEMENT_PROMPT = (
    "Überarbeite diesen Rohinhalt ohne neue Fakten.\n"
    "1) Straffe Sprache, 2) markiere Unklarheiten `[KLÄREN: …]`, 3) gib Kernaussagen als Bullets + 1-Satz-Summary.\n"
    "**Rohinhalt:** {content}"
)

OUTLINE_SYSTEM_PROMPT = (
    "Du gliederst Themen in übersichtliche, gut strukturierte Outlines und achtest auf klare Hierarchien "
    "sowie eine sinnvolle Reihenfolge."
)

OUTLINE_PROMPT = (
    "Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` basierend auf dem Briefing:\n"
    "{briefing_json}\n"
    "Für jeden Abschnitt: Nummer, Titel, Rollenfunktion, Wortbudget, Liefergegenstand.\n"
    "Gesamtwortzahl: {word_count}. Keine Fakten erfinden."
)

OUTLINE_IMPROVEMENT_SYSTEM_PROMPT = (
    "Du überarbeitest Outlines, vertiefst die Charakterisierung der Figuren und sorgst für eine klare, konsistente Struktur."
)

OUTLINE_IMPROVEMENT_PROMPT = (
    "Prüfe und verbessere die Outline: entferne Überschneidungen, füge fehlende Brücken, balanciere Budgets (Summe = {word_count}). "
    "Behalte Faktenneutralität.\n\nOutline:\n{outline}\n"
)

SECTION_SYSTEM_PROMPT = (
    "Du schreibst spannende Prosatexte auf Deutsch und hältst dich strikt an die Outline. Du bleibst konsequent im Stil."
)

SECTION_PROMPT = (
    "Schreibe Abschnitt {section_number} „{section_title}“ (Rolle: {role}) mit Ziel `{deliverable}`.\n"
    "Nutze Briefing und bisherige Abschnitte (Kohärenz, Terminologie).\n"
    "Briefing: {briefing_json}\n"
    "Bisheriger Kontext (Kurz-Recap): {previous_section_recap}\n"
    "Regeln: aktive Verben, keine Füllphrasen, natürliche Übergänge, keine erfundenen Fakten (Platzhalter bei Lücken).\n"
    "Zielwortzahl: {budget}.\n"
    "Gib ausschließlich den neu generierten Abschnittstext aus."
)

SECTION_CONTINUE_PROMPT = (
    "Der Abschnitt {section_number} „{section_title}“ (Rolle: {role}) mit Ziel `{deliverable}` ist noch zu kurz. "
    "Führe ihn fort und erweitere ihn um etwa {budget} Wörter, ohne den bisherigen Text zu wiederholen.\n"
    "Briefing: {briefing_json}\n"
    "Bisheriger Abschnitt: {existing_text}\n"
    "Bisheriger Kontext (Kurz-Recap): {previous_section_recap}"
)

STORY_DEEPENING_SYSTEM_PROMPT = (
    "Du überarbeitest Texte und vertiefst die Geschichte, indem du Details ergänzt und eine stimmige Dramaturgie sicherstellst."
)

STORY_DEEPENING_PROMPT = (
    "Der Text ist insgesamt noch zu kurz. Überarbeite den gesamten Text, vertiefe die Geschichte und füge etwa {remaining} zusätzliche Wörter ein, ohne nur den Schluss aufzublähen.\n"
    "Briefing: {briefing_json}\n"
    "Aktueller Text:\n{current_text}\n"
)

REVISION_SYSTEM_PROMPT = (
    "Du überarbeitest Texte präzise, verbesserst Stil, Kohärenz und Grammatik und orientierst dich an einer vorgegebenen Outline."
)

REVISION_PROMPT = (
    "Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit & Prägnanz, Flow & Übergänge, Terminologie-Konsistenz, "
    "Wiederholungen tilgen, Rhythmus variieren, spezifische Verben/Nomen stärken, Schlussteil schärfen (CTA/Resolution), "
    "Registersicherheit ({register}), Variantenspezifika ({variant}).\n\n"
    "Aktueller Text:\n{current_text}\n\nÜberarbeiteter Text:"
)

TEXT_TYPE_CHECK_SYSTEM_PROMPT = (
    "Du prüfst als seit 20 Jahren erfahrene Lektorin Texte darauf, ob sie den Merkmalen der angegebenen Textart entsprechen."
)

TEXT_TYPE_CHECK_PROMPT = (
    "Prüfe den folgenden Text gegen die Rubrik für `{text_type}`. Liste konkrete Abweichungen und betroffene Stellen.\n\n"
    "Text:\n{current_text}\n"
)

TEXT_TYPE_FIX_SYSTEM_PROMPT = (
    "Du überarbeitest Texte anhand eines Textchecks und behebst die genannten Mängel präzise."
)

TEXT_TYPE_FIX_PROMPT = (
    "Der Rubrik-Check hat ergeben, dass es folgende Abweichungen im Text gibt:\n"
    "{issues}\n"
    "Behebe sie im folgenden Text und liefere die verbesserte Version:\n"
    "{current_text}\n"
)


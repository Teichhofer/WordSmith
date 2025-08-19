"""Prompt templates used by WriterAgent."""

SYSTEM_PROMPT = (
    "Du bist eine erfahrene, kreative Autorin und Lektorin. "
    "Du verfasst gut strukturierte und ansprechende {text_type} in klarem Deutsch. "
    "Achte auf logische Übergänge, natürlichen Stil und vermeide Wiederholungen. "
    "Achte besonderes auf die inhaltliche Qualität des Textes. "
    "Dein Thema lautet: {topic}."
)

META_PROMPT = (
    "Du arbeitest an einem {text_type} mit dem Titel: {title}\n"
    "Er behandelt folgenden Inhalt: {content}\n"
    "Die gewünschte Länge beträgt etwa {word_count} Wörter.\n"
    "Aktueller Stand des Textes:\n{current_text}\n\n"
    "Beschreibe den nächsten sinnvollen Schritt der Geschichte, der den Text literarisch vertiefen würde. "
    "Achte darauf, dass Atmosphäre, Spannung und innere Konflikte verstärkt werden und die Figuren "
    "lebendiger, widersprüchlicher und psychologisch nachvollziehbarer wirken. "
    "Lege Wert auf subtile Andeutungen, emotionale Zwischentöne und mögliche symbolische Elemente, "
    "die den Text dichter und vielschichtiger machen. "
    "Formuliere ausschließlich einen präzisen Prompt für ein LLM, der genau diesen nächsten sinnvollen Schritt beschreibt, "
    "so dass daraus eine kreative und literarisch hochwertige Erweiterung der Geschichte entstehen kann."
)


INITIAL_AUTO_PROMPT = (
    "Schreibe diesen Text als erfahrene Autorin mit jahrzenten an erfahung.\n"
    "Titel: {title}\n"
    "Textart: {text_type}\n"
    "Inhalt: {content}\n"
    "Er soll etwa {word_count} Wörter umfassen."
    "Achte auf einen klaren, ansprechenden Stil und logische Übergänge. "
    "Achte darauf die Konventionen der Textart {text_type} zu beachten.\n"
)

OUTLINE_PROMPT = (
    "Erstelle eine gegliederte Outline für einen {text_type} mit dem Titel: {title}\n"
    "Der Text behandelt folgenden Inhalt: {content}\n"
    "Die Gesamtlänge beträgt etwa {word_count} Wörter.\n"
    "Gib eine nummerierte Liste der Abschnitte zurück und vermerke in Klammern den ungefähren Wortumfang jedes Abschnitts."
)

SECTION_PROMPT = (
    "Outline:\n{outline}\n\n"
    "Bisheriger Text:\n{current_text}\n\n"
    "Schreibe den Abschnitt '{title}' mit etwa {word_count} Wörtern."
    "Schreibe nur diesen Abschnitt."
)

REVISION_PROMPT = (
    "Überarbeite den folgenden {text_type} basierend auf der Outline."
    "Die Gesamtlänge soll etwa {word_count} Wörter betragen.\n\n"
    "Outline:\n{outline}\n\n"
    "Aktueller Text:\n{current_text}\n\n"
    "Überarbeiteter Text:"
)


PROMPT_CRAFTING_PROMPT = (
    "Formuliere einen klaren und konkreten Prompt für ein LLM, "
    "um die Aufgabe '{task}' zum Thema '{topic}' umzusetzen. "
    "Gib nur den Prompt zurück."
)


STEP_PROMPT = (
    "{prompt}\n\nAktueller Text:\n{current_text}\n\nNächster Abschnitt:"
)




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
    "Bestimme den nächsten sinnvollen Schritt, um diesen Text zu verbessern oder zu erweitern. "
    "Formuliere ausschließlich einen präzisen Prompt für ein LLM, der diesen Schritt beschreibt."
)

INITIAL_AUTO_PROMPT = (
    "Schreibe diesen Text.\n"
    "Titel: {title}\n"
    "Textart: {text_type}\n"
    "Inhalt: {content}\n"
    "Er soll etwa {word_count} Wörter umfassen."
)


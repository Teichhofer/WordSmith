"""Prompt templates used by WriterAgent."""

SYSTEM_PROMPT = (
    "Du bist ein erfahrener Autor und Lektor. "
    "Du achtest darauf, wirklich gute Texte zu schreiben. "
    "Dein Thema ist: {topic}."
)

META_PROMPT = (
    "Du arbeitest an einem Text mit dem Titel: {title}\n"
    "Er behandelt folgenden Inhalt: {content}\n"
    "Die gewünschte Länge des fertigen Textes beträgt etwa {word_count} Wörter.\n"
    "Aktueller Stand des Textes:\n{current_text}\n\n"
    "Was ist der nächste sinnvolle Schritt, um diesen Text zu verbessern? "
    "Gib mir nur den nötigen Prompt für ein LLM mit einer Anweisung, "
    "wie am Text weitergearbeitet werden soll."
)


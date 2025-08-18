"""Prompt templates used by WriterAgent."""

SYSTEM_PROMPT = "Du bist ein Erfahrener Autor und Lektor. du achtest darauf wirklcih gute Texte zu schreiben. Dein Thema ist: {topic}."

META_PROMPT = (
    "Du arbeitest an einem Text mit dem Titel: {title}\n"
    "Es Soll darin um diesen Inhalt gehen : {content}\n"
    "Die Gewünschte Länge des Fertigen Texttes soll etwa: {word_count} Wörter\n"
    "Aktueller Stand des Texttes ist:\n{current_text}\n\n"
    "was ist der nächste Schritt um diese Text besser zu machen, "
    "gib mir nur den nötigen prompt für ein LLM, mit einer eine Anweisung um am Text Weiter zu Arbeiten"
)

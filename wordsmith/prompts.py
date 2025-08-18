"""Prompt templates used by WriterAgent."""

META_PROMPT = (
    "Titel: {title}\n"
    "Gewünschter Inhalt: {content}\n"
    "Aktueller Text:\n{current_text}\n\n"
    "was ist der nächste Schritt um diese Geschichte fertig zu stellen, "
    "gib mir nur den nötigen prompt für ein LLM"
)

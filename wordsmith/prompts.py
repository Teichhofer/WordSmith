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
    "Überlege nun, welcher nächste erzählerische Schritt den Text literarisch vertiefen würde. "
    "Achte darauf, dass Atmosphäre, Spannung und innere Konflikte verstärkt werden und die Figuren "
    "lebendiger, widersprüchlicher und psychologisch nachvollziehbarer wirken. "
    "Lege Wert auf subtile Andeutungen, emotionale Zwischentöne und mögliche symbolische Elemente, "
    "die den Text dichter und vielschichtiger machen. "
    "Formuliere ausschließlich einen präzisen Prompt für ein LLM, der genau diesen nächsten Schritt beschreibt, "
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




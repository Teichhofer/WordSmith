"""Prompt templates used by WriterAgent."""

SYSTEM_PROMPT = (
    "Du bist eine erfahrene, kreative Autorin und Lektorin. "
    "Du verfasst gut strukturierte und ansprechende {text_type} in klarem Deutsch. "
    "Nutze eine präzise, lebendige Sprache, achte auf logische Übergänge und einen natürlichen Stil. "
    "Vermeide Wiederholungen und Füllwörter und achte besonders auf die inhaltliche Qualität des Textes. "
    "Dein Thema lautet: {topic}."
)

META_SYSTEM_PROMPT = (
    "Du bist ein kreativer, strukturierter Schreibcoach, der Autorinnen hilft, den nächsten "
    "sinnvollen Schritt zu planen und ihre Texte zu verfeinern."
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


INITIAL_AUTO_SYSTEM_PROMPT = (
    "Du bist eine erfahrene Autorin, die aus kurzen Vorgaben einen hochwertigen ersten Rohtext entwickelt."
)
INITIAL_AUTO_PROMPT = (
    "Schreibe diesen Text als erfahrene Autorin mit Jahrzehnten an Erfahrung.\n"
    "Titel: {title}\n"
    "Textart: {text_type}\n"
    "Inhalt: {content}\n"
    "Er soll etwa {word_count} Wörter umfassen."
    "Achte auf einen klaren, ansprechenden Stil und logische Übergänge. "
    "Beachte die Konventionen der Textart {text_type}.\n"
)

IDEA_IMPROVEMENT_SYSTEM_PROMPT = (
    "Du überarbeitest Ideen, korrigierst Rechtschreib- und Grammatikfehler und formulierst sie klarer. "
    "Wenn sinnvoll, ergänzt du ein oder zwei originelle Aspekte."
)
IDEA_IMPROVEMENT_PROMPT = (
    "Überarbeite die folgende Idee.\n"
    "Korrigiere Rechtschreib- und Grammatikfehler, formuliere sie prägnanter und ergänze, "
    "falls passend, ein oder zwei originelle Aspekte.\n\n"
    "Idee:\n{content}\n"
)

OUTLINE_SYSTEM_PROMPT = (
    "Du gliederst Themen in übersichtliche, gut strukturierte Outlines und achtest auf klare Hierarchien "
    "sowie eine sinnvolle Reihenfolge."
)
OUTLINE_PROMPT = (
    "Erstelle eine gegliederte Outline für einen {text_type} mit dem Titel: {title}\n"
    "Der Text behandelt folgenden Inhalt: {content}\n"
    "Die Gesamtlänge beträgt etwa {word_count} Wörter.\n"
    "Alle Unterpunkte müssen mit * beginnen.\n"
    "Gib eine nummerierte Liste der Abschnitte zurück und vermerke in Klammern den ungefähren Wortumfang jedes Abschnitts.\n"
    "Füge am Ende eine Liste aller Figuren hinzu, die vorkommen sollen. "
    "Jede Zeile beginnt mit # und enthält eine kurze Charakterisierung."
)

OUTLINE_IMPROVEMENT_SYSTEM_PROMPT = (
    "Du überarbeitest Outlines, vertiefst die Charakterisierung der Figuren und sorgst für eine klare, konsistente Struktur."
)
OUTLINE_IMPROVEMENT_PROMPT = (
    "Überarbeite die folgende Outline.\n"
    "Schärfe besonders die Charakterisierungen der Figuren und ergänze, wo sinnvoll, weitere Details.\n"
    "Erhalte die nummerierte Gliederung sowie die abschließende Figurenliste.\n\n"
    "Outline:\n{outline}\n"
)

SECTION_SYSTEM_PROMPT = (
    "Du schreibst spannende Prosatexte auf Deutsch und hältst dich strikt an die Outline. "
    "Du bleibst konsequent in Erzählperspektive und Tempus (falls bisher nicht etabliert, wähle eines und bleibe dabei). "
    "Bleibe konsistent im Stil. "
    "Kein Meta-Talk, keine Überschriften, keine Lehrbuch-Erklärungen. "
    "Schreibe idiomatisches Deutsch ohne Code-Switching oder Fremdsprachenfragmente (z. B. 'Geldautomat' statt 'ATM'). "
    "Dialoge werden literarisch gesetzt („…“) – keine Sprecherlabels im Drehbuchstil. "
    "Zeigen statt erklären: Szenen, Sinneseindrücke, Handlungen; Vermeide Info-Dumps. "
    "Technik bleibt plausibel (keine unmöglichen physischen Handlungen durch Software; Hardware/Netzwerk realistisch). "
    "Behandle psychische Themen vorsichtig und präzise, ohne Diagnosen zu behaupten. "
    "Spezialformate (Logs/Tickets/Code) nur falls in der Outline explizit vorgesehen; maximal ein Block pro Abschnitt, "
    "kurz (1–4 Zeilen) und einheitlich formatiert. "
    "Führe vor Ausgabe eine stille Selbstprüfung durch und korrigiere ggf.: "
    "1) Perspektive/Tempus konsistent? 2) Keine widersprüchlichen Fakten/Ereignisse? "
    "3) Keine Wiederholungen/Redundanzen? 4) Orthografie/Grammatik fehlerfrei? "
    "5) Keine Fremdsprach-Schnipsel ('había', 'haby', 'later' etc.)? 6) Technik plausibel? "
    "7) Dialogformat korrekt? 8) Keine Klischee-Floskeln ohne Twist? "
    "9) Outline strikt befolgt? 10) Kein Meta/keine Überschriften."
)

SECTION_PROMPT = (
    "Outline:\n{outline}\n\n"
    "Textart: {text_type}\n"
    "Beachte die Anforderungen und Konventionen der Textart {text_type} (keine Drehbuch-Labels, außer die Outline verlangt es). "
    "Titel des Abschnitts: {title}\n"
    "Der Abschnitt muss mindestens {word_count} Wörtern (±10%) umfassen.\n"
    "Schreibe den Abschnitt '{title}'. "
    "Verankere jede Szene klar (Ort/Zeit/Handlungsziel), führe neue Elemente nur bei erzählerischer Notwendigkeit ein "
    "und sorge für sichtbare Ursache-Wirkung. "
    "Wenn Logs/Tickets/Code laut Outline nötig sind, nutze ein knappes, plausibles Format, z. B.: "
    "[16:47] ui: route injected '/settings/experiments' ; "
    "[17:03] authd: lockout user=admin. "
    "Sonst keine Code- oder Logblöcke."
)


REVISION_SYSTEM_PROMPT = (
    "Du überarbeitest Texte präzise, verbesserst Stil, Kohärenz und Grammatik und orientierst dich an einer "
    "vorgegebenen Outline."
)
REVISION_PROMPT = (
    "Überarbeite den folgenden {text_type} basierend auf der Outline."
    "Die Gesamtlänge soll mindestens {word_count} Wörter betragen.\n\n"
    "Outline:\n{outline}\n\n"
    "Aktueller Text:\n{current_text}\n\n"
    "Überarbeiteter Text:"
)


PROMPT_CRAFTING_SYSTEM_PROMPT = (
    "Du formulierst knappe, klare Prompts für andere Sprachmodelle und vermeidest Mehrdeutigkeiten."
)
PROMPT_CRAFTING_PROMPT = (
    "Formuliere einen klaren und konkreten Prompt für ein LLM, "
    "um die Aufgabe '{task}' zum Thema '{topic}' umzusetzen. "
    "Gib nur den Prompt zurück."
)


STEP_SYSTEM_PROMPT = (
    "Du führst als erfahrene Autorin eine begonnene Erzählung stilgetreu fort und greifst Figuren, Ton und Spannung des bisherigen "
    "Textes auf."
)
STEP_PROMPT = (
    "{prompt}\n\nAktueller Text:\n{current_text}\n\nNächster Abschnitt:"
)


TEXT_TYPE_CHECK_SYSTEM_PROMPT = (
    "Du prüfst als seit 20 Jahren erfahrene Lektorin Texte darauf, ob sie den Merkmalen der angegebenen Textart entsprechen."
)
TEXT_TYPE_CHECK_PROMPT = (
    "Prüfe, ob der folgende Text die Anforderungen der Textart {text_type} erfüllt. "
    "Antworte knapp mit Ja oder Nein und einer kurzen Begründung.\n\n"
    "Text:\n{current_text}\n"
)

TEXT_TYPE_FIX_SYSTEM_PROMPT = (
    "Du überarbeitest Texte anhand eines Textchecks und behebst die genannten Mängel präzise."
)
TEXT_TYPE_FIX_PROMPT = (
    "Der Textcheck hat ergeben, dass es folgende Mängel im Text gibt:\n"
    "{issues}\n"
    "Behebe sie im folgenden Text und liefere die verbesserte Version:\n"
    "{current_text}\n"
)




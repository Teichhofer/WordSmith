# Automatikmodus

Dieser Leitfaden beschreibt den Ablauf der Anwendung im **Automatikmodus**. Die Informationen sind so detailliert, dass eine Entwicklerin die Funktionalität nachbauen kann.

Im Kern steuert der `WriterAgent` einen frei wählbaren LLM‑Dienst. Für jede Phase – von der Ideenverbesserung über die Outline‑Erstellung und Abschnittsgenerierung bis zu Texttyp‑Prüfung und Überarbeitung – sendet er definierte Prompts an dieses Modell und verarbeitet die Antworten weiter.

## Eingaben und Initialisierung
1. Die CLI erfragt Titel, groben Inhalt, Textart, gewünschte Wortzahl, Anzahl der Überarbeitungs‑Iterationen und den zu verwendenden LLM‑Provider.
2. Aus diesen Angaben wird ein `WriterAgent` erzeugt. Er erhält den Titel (`topic`), die Wortzahl (`word_count`), eine leere Schrittliste, die Anzahl der Iterationen, die Konfiguration sowie den Eingabetext (`content`) und die Textart (`text_type`).
3. Vor dem Start ruft der Agent `Config.adjust_for_word_count`, um Kontextlänge und Tokenlimit proportional zur Zielwortzahl zu skalieren. Außerdem werden Log‑ und Ausgabeverzeichnisse erstellt.

## Verbesserung der Idee
1. Mit `IDEA_IMPROVEMENT_PROMPT` wird der ursprüngliche Inhalt sprachlich überarbeitet und bei Fehlern korrigiert.
2. Die überarbeitete Idee ersetzt den ursprünglichen Inhalt.

## Outline erzeugen und verfeinern
1. `OUTLINE_PROMPT` erstellt anhand von Titel, Textart, Inhalt und Wortzahl eine nummerierte Gliederung inklusive Wortbudget für jeden Abschnitt und einer Figurenliste.
2. `OUTLINE_IMPROVEMENT_PROMPT` verfeinert diese Gliederung und die Charakterisierungen der Figuren.
3. Die Outline wird bereinigt (`_clean_outline`) und in `output/outline.txt` gespeichert. Gleichzeitig wird sie als `iteration_00.txt` abgelegt.

## Abschnittsweise Textgenerierung
1. `_parse_outline` zerlegt die Outline in Titel/Wortzahl‑Paare. Negative oder fehlende Wortbudgets werden auf mindestens 1 gesetzt; das letzte Element erhält Restwörter, damit die Gesamtzahl exakt ist.
2. Für jeden Abschnitt wird ein `SECTION_PROMPT` erstellt. Der Agent ruft das LLM auf, beschränkt das Ergebnis mit `_truncate_words` auf das vorgesehene Wortbudget und fügt den Abschnitt an.
3. Nach jeder Sektion werden `output/current_text.txt` und `iteration_01.txt` aktualisiert, sodass der aktuelle Stand jederzeit auf der Festplatte liegt.

## Texttyp‑Prüfung und automatische Korrektur
1. Nachdem alle Abschnitte generiert wurden, werden sie zu einem Text zusammengefügt und ggf. auf die Zielwortzahl gekürzt (`_truncate_text`).
2. Mit `TEXT_TYPE_CHECK_PROMPT` prüft das LLM, ob der Text die Anforderungen der angegebenen Textart erfüllt.
3. Bei erkannter Abweichung erzeugt `TEXT_TYPE_FIX_PROMPT` eine korrigierte Fassung. Wenn die Änderungen mehrheitlich übereinstimmen (≥80 % gemeinsamer Wörter und ≥0,9 Sequenzähnlichkeit), wird der Text ersetzt und gespeichert.
4. Der so entstandene Text bildet die Ausgangsbasis für Überarbeitungen und liegt als `iteration_01.txt` vor.

## Iterative Überarbeitung
1. Für jede weitere Iteration `i` (1 … `iterations`):
    - Der Agent lädt den Text der vorherigen Iteration (`_load_iteration_text`).
    - `REVISION_PROMPT` erzeugt eine überarbeitete Version basierend auf Outline, Inhalt und Zielwortzahl.
    - Weicht das Ergebnis vom Ausgangstext ab, wird es auf die Wortzahl gekürzt, als neue Version gespeichert (`output/current_text.txt` und `iteration_{i+1:02d}.txt`) und der Fortschritt auf der Konsole angezeigt.
2. Nach Abschluss der letzten Iteration liefert die Methode den finalen, gekürzten Text zurück.

## Logging und Dateiausgaben
- Strukturierte Logs aller Schritte liegen in `logs/run.log`.
- Für jede LLM‑Anfrage wird in `logs/llm.log` ein JSON‑Eintrag mit Prompt und Antwort geschrieben.
- Der jeweils aktuelle Textstand befindet sich in `output/current_text.txt`; Zwischenstände werden als `iteration_XX.txt` abgelegt.

Mit diesen Informationen lässt sich der Automatikmodus des Projekts vollständig nachvollziehen und implementieren.

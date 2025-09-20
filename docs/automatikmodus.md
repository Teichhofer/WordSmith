# Automatikmodus (Stand der Codebasis)

Dieser Leitfaden dokumentiert den tatsächlichen Ablauf des Automatikmodus
in der aktuellen WordSmith-Codebasis. Ziel ist es, den Entwicklungsstand
präzise wiederzugeben und alle LLM-Interaktionen, Prüfungen sowie erzeugten
Artefakte nachvollziehbar zu machen.

## Qualitätsziele

Der WriterAgent steuert die LLM-Aufrufe so, dass der finale Text

1. das angegebene Zielpublikum adressiert,
2. keine Fakten erfindet (fehlende Daten → Platzhalter wie `[KLÄREN: …]`,
   `[QUELLE]`, `[DATUM]`),
3. den gewünschten Texttyp respektiert,
4. dem Zielumfang möglichst nahekommt und
5. stilistisch zu Ton, Register und Sprachvariante passt.

Diese Kriterien werden über Prompt-Vorgaben, den Rubrik-Check und das
Compliance-Logging abgesichert.

## Architekturüberblick

* Die CLI (`cli.py`) sammelt Argumente, lädt `Config`, setzt optionale
  Pfad-Overrides und sorgt dafür, dass ein Ollama-Modell ausgewählt ist.
* `wordsmith.agent.WriterAgent` orchestriert die komplette Pipeline. Jeder
  Schritt wird als Ereignis protokolliert; bei Bedarf schreibt der Agent
  Zwischenstände ins Ausgabeverzeichnis.
* `wordsmith.prompts` lädt beim Programmstart die Texte aus
  `prompts_config.json`. Laufzeit-Overrides sind über
  `prompts.set_system_prompt()` möglich.

## Eingabe-Normalisierung

Der WriterAgent überprüft alle Eingaben und ergänzt Defaults, bevor die
LLM-Pipeline startet:

* Leere Titel oder `text_type` führen zu einem Abbruch mit
  `WriterAgentError`.
* `audience`, `tone`, `register`, `variant` und `constraints` erhalten bei
  leeren Werten die Defaults aus `wordsmith.defaults`.
* Register und Varianten werden normalisiert; unbekannte Werte lösen
  Hinweise im Log aus und fallen auf die Defaults zurück.
* SEO-Keywords werden bereinigt (Trimmen, Entfernen von Duplikaten).

Diese Hinweise erscheinen als `input_defaults`-Events in `logs/run.log`.

## Schritt 1: Briefing erzeugen

`_generate_briefing()` ruft das `BRIEFING_PROMPT` auf, das ein strikt
valide JSON-Objekt erwartet. Das Ergebnis wird geparst und um fehlende
Felder ergänzt (z. B. `goal`, `audience`, `tone`). Der Agent speichert die
Datei als `briefing.json`.

## Schritt 2: Idee verdichten

`_improve_idea_with_llm()` nutzt das `IDEA_IMPROVEMENT_PROMPT`. Die Antwort
enthält einen überarbeiteten Fließtext, eine Unklarheiten-Liste, die
Kernaussagen sowie eine Summary. Die komplette Ausgabe landet in `idea.txt`;
Kernaussagen werden intern für spätere Prompts zwischengespeichert.

## Schritt 3: Outline aufbauen

1. `_create_outline_with_llm()` erstellt eine erste Gliederung auf Basis
   des Briefings.
2. `_refine_outline_with_llm()` verfeinert diese Struktur.
3. `_clean_outline_sections()` säubert Titel, Rollen, Budgets und
   Liefergegenstände. Fehlt ein Budget, wird es aufgefüllt und die Differenz
   zum Zielumfang im letzten Abschnitt ausgeglichen.

Die Outline wird in `outline.txt` abgelegt; zusätzlich dient sie als
`iteration_00.txt`.

## Schritt 4: Abschnittstexte generieren

Für jeden Outline-Eintrag erzeugt `_build_section_prompt()` einen Prompt,
der enthält

* das Briefing (als JSON),
* die Outline (Textform),
* die Kernaussagen aus Schritt 2,
* Stilrichtlinien mit Ton, Register, Sprachvariante, Constraints,
  SEO-Keywords und Quellenmodus sowie
* einen Recap des vorherigen Abschnitts (die letzten ca. 60 Tokens).

`_generate_draft_from_outline()` ruft daraufhin das LLM je Abschnitt auf.
Die Ergebnisse werden mit Markdown-Überschriften kombiniert und laufend in
`current_text.txt` geschrieben.

## Schritt 5: Rubrik-Prüfung & Korrektur

Der vollständige Entwurf wird vom `TEXT_TYPE_CHECK_PROMPT` geprüft.
* Die Antwort wird in `text_type_check.txt` gespeichert.
* Enthält der Bericht keine Formulierungen wie „keine Abweichung“ oder
  „alles erfüllt“, ruft der Agent das `TEXT_TYPE_FIX_PROMPT` auf, schreibt
  die korrigierte Fassung in `text_type_fix.txt` und verwendet sie für den
  weiteren Verlauf.

Das Flag `_rubric_passed` im Agenten spiegelt wider, ob eine Korrektur
nötig war.

## Schritt 6: Revisionen & Reflexion

Für jede zusätzliche Iteration (Argument `--iterations`) ruft der Agent
`_revise_with_llm()` mit dem vollständigen Text auf. Der verwendete
Systemprompt stammt aus `prompts.REVISION_SYSTEM_PROMPT`; zusätzlich hängen
System-Hinweise die Wortzahlgrenzen sowie – falls `--compliance-hint`
aktiv ist – die Vorgabe für Compliance-Hinweise an. Optionale Reflexionen
werden mit `_generate_reflection()` erstellt und als `reflection_XX.txt`
behalten.

## Compliance-Prüfung

Nach dem Erstentwurf und jeder Revision läuft `_run_compliance()`:

* Sensible Begriffe werden anhand fest kodierter Regexe maskiert und durch
  `[ENTFERNT: …]` ersetzt.
* Compliance-Hinweise (`[COMPLIANCE-…]`) werden standardmäßig entfernt,
  bleiben bei gesetztem CLI-Flag erhalten.
* Platzhalter wie `[KLÄREN]` oder `[QUELLE]` werden gezählt.
* Alle Ergebnisse landen im internen Audit-Log, das später in
  `compliance.json` geschrieben wird.

## Abschluss & Artefakte

Nach der letzten Revision

1. wird der finale Text in `Final-<timestamp>.txt` gespeichert,
2. schreibt `_write_metadata()` die Metadaten (inklusive LLM-Informationen
   und Compliance-Ergebnis) in `metadata.json`,
3. erzeugt `_write_compliance_report()` das Compliance-Protokoll und
4. legt `_write_logs()` die Dateien `logs/run.log` und `logs/llm.log` an.

`run.log` enthält eine Sequenz aller Pipeline-Ereignisse. `llm.log` fasst
zusätzlich die Outline, verwendeten Prompts, Parameter sowie Telemetrie
(z. B. Token-Schätzungen und Rückmeldungen pro LLM-Call) zusammen.

## Konfiguration & LLM-Parameter

`Config.adjust_for_word_count()` stellt sicher, dass Kontextlänge und
Tokenlimit proportional zum Zielumfang wachsen (mindestens 8192 Tokens).
Zudem werden deterministische Parameter gesetzt (`temperature=0.7`,
`top_p=1.0`, `presence_penalty=0.05`, `frequency_penalty=0.05`, Seed 42).
Falls verfügbar, wird `num_predict` auf das Tokenlimit gesetzt.

`WriterAgent._call_llm_stage()` lehnt Aufrufe ab, deren geschätzter
Tokenbedarf 85 % des Limits überschreitet, und protokolliert Fehler oder
leere Antworten. Unterstützt wird ausschließlich Ollama; ohne ausgewähltes
Modell bricht der Agent mit einem Fehler ab.

## Prompt-Konfiguration

Die Standardprompts und Parameter liegen in
`wordsmith/prompts_config.json`. Jede Prompt-Stufe besitzt einen eigenen
Systemprompt sowie Parameter (Temperatur, Top-P, Penalties, optional
`num_predict`). Die Datei organisiert diese Werte unter dem Schlüssel
`stages`, sodass für jede Stufe (`briefing`, `outline`, `final_draft` …)
ein Objekt mit `system_prompt`, `prompt` und `parameters` vorliegt.
Änderungen an dieser Datei wirken sich nach einem Neustart auf alle Läufe
aus; zur Laufzeit können Systemprompts gezielt über
`prompts.set_system_prompt()` überschrieben werden.


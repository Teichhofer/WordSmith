# WordSmith

WordSmith bündelt die komplette Textproduktion im **Automatikmodus**. Die
Kommandozeile instanziiert `wordsmith.agent.WriterAgent`, der die Pipeline
aus Briefing-Aufbereitung, Outline-Generierung, Abschnittstexten,
Rubrik-Prüfung und optionalen Revisionen durchläuft. Details zum Ablauf
finden sich in [`docs/automatikmodus.md`](docs/automatikmodus.md).

## Voraussetzungen

Die aktuelle Implementierung spricht ausschließlich einen lokal verfügbaren
Ollama-Dienst an. Das CLI ermittelt beim Start das gewünschte Modell oder
fragt interaktiv nach, falls keines angegeben wurde. Vor dem Start sollten

* der Ollama-Dienst laufen (`ollama serve`),
* mindestens ein Modell installiert sein (`ollama list`), und
* die Modellwahl zur gewünschten Textproduktion passen.

## CLI-Referenz

Der Automatikmodus wird über das Unterkommando `automatikmodus`
gestartet. Alle vom Code unterstützten Optionen lassen sich mit folgendem
Aufruf übergeben:

```bash
python cli.py automatikmodus \
  --title "Arbeitstitel" \
  --content "Briefingtext" \
  --text-type "Blogartikel" \
  --word-count 900 \
  --iterations 1 \
  --llm-provider ollama \
  --audience "Marketing-Team" \
  --tone "sachlich" \
  --register Sie \
  --variant DE-DE \
  --constraints "Keine Zahlen erfinden" \
  --sources-allowed false \
  --seo-keywords "KI, Textautomatisierung" \
  --compliance-hint \
  --config config.json \
  --output-dir output \
  --logs-dir logs \
  --ollama-model mistral \
  --ollama-base-url http://localhost:11434
```

Alternativ können die Einstellungen gesammelt in einer JSON-Datei liegen
und per `--input-file` geladen werden:

```bash
python cli.py automatikmodus --input-file lauf.json
```

Im Repository liegt mit `docs/examples/automatikmodus-input.json` ein
vollständig befülltes Beispiel. Pfade dürfen absolut oder relativ zum
aktuellen Arbeitsverzeichnis angegeben werden.

Die Optionen im Überblick:

| Option | Pflicht? | Beschreibung |
| ------ | -------- | ------------ |
| `--title` | ✓ | Arbeitstitel für den Text. |
| `--content` | ✓ | Briefing oder Notizen, die in Schritt 1 normalisiert werden. |
| `--text-type` | ✓ | Texttyp (z. B. Blogartikel, Pressemitteilung). |
| `--word-count` | ✓ | Zielwortzahl des Endtexts. Muss > 0 sein. |
| `--iterations` |   | Anzahl optionaler Revisionen nach dem Erstentwurf (Default: 1; `0` erlaubt). |
| `--llm-provider` |   | Kennung des LLM-Anbieters. Aktuell wird nur `ollama` unterstützt. |
| `--audience` |   | Zielgruppe; Default siehe `wordsmith.defaults.DEFAULT_AUDIENCE`. |
| `--tone` |   | Tonalität; Default siehe `DEFAULT_TONE`. |
| `--register` |   | Anrede/Sprachregister (`Du`/`Sie`), Normalisierung über `REGISTER_ALIASES`. |
| `--variant` |   | Sprachvariante (`DE-DE`, `DE-AT`, `DE-CH`). |
| `--constraints` |   | Zusätzliche Muss-/Kann-Vorgaben. |
| `--sources-allowed` |   | `true`/`false`, ob Quellenangaben erlaubt sind. |
| `--seo-keywords` |   | Kommagetrennte Liste; Duplikate werden entfernt. |
| `--compliance-hint` |   | Flag ohne Parameter; sorgt dafür, dass ein vorhandener Compliance-Hinweis im Ergebnis verbleibt. |
| `--config` |   | Pfad zu einer optionalen JSON-Konfiguration; Werte überschreiben Defaults. |
| `--output-dir` |   | Zielverzeichnis für Artefakte wie `Final-*.txt` oder `metadata.json`. |
| `--logs-dir` |   | Verzeichnis für Lauf- und Prompt-Logs. |
| `--ollama-model` |   | Name des Ollama-Modells; ohne Angabe wird interaktiv (TTY) oder automatisch das erste Modell gewählt. |
| `--ollama-base-url` |   | Basis-URL der Ollama-API (Default: `http://localhost:11434`). |
| `--input-file` |   | Pfad zu einer JSON-Datei, die alle oben genannten Argumente enthalten kann. CLI-Argumente überschreiben diese Werte. |

### Eingabedatei

Die Eingabedatei muss ein JSON-Objekt enthalten. Die Schlüssel entsprechen
den CLI-Optionen, jedoch in Snake-Case (z. B. `text_type`). Werte werden wie
auf der Kommandozeile validiert. Ein Minimalbeispiel:

```json
{
  "title": "Strategische Roadmap",
  "content": "Wir planen die nächsten Schritte.",
  "text_type": "Strategiepapier",
  "word_count": 400,
  "llm_provider": "ollama",
  "iterations": 1,
  "sources_allowed": false,
  "seo_keywords": ["Roadmap", "Strategie"]
}
```

Optional lassen sich u. a. `output_dir`, `logs_dir`, `ollama_model` oder
`config` definieren. CLI-Argumente haben stets Vorrang vor den Werten aus
der Datei. Boolesche Werte dürfen als `true`/`false` oder `"ja"`/`"nein"`
angegeben werden.

Die CLI gibt den finalen Text auf `stdout` aus, schreibt Statusmeldungen
auf `stderr` und beendet sich mit

* `0` bei Erfolg,
* `1` bei Fehlern im WriterAgent oder Benutzungsfehlern,
* `2` für Konfigurationsprobleme und
* `3` bei Ollama-spezifischen Fehlern.

## Ablauf des Automatikmodus

1. **Initialisierung:** Die CLI lädt `Config`, setzt optionale
   Pfad-Overrides und sorgt für ein gewähltes Ollama-Modell. Anschließend
   erstellt sie einen `WriterAgent` mit allen Eingaben. Fehlende Felder wie
   Zielgruppe, Ton oder Register werden innerhalb des Agents auf sinnvolle
   Defaults ergänzt und in den Logs vermerkt.
2. **Briefing-Phase:** Der Agent ruft das `BRIEFING_PROMPT` auf und
   speichert das Ergebnis als `briefing.json`. Fehlende Felder werden auf
   Basis der Eingaben bzw. Defaults ergänzt.
3. **Ideen-Phase:** Das `IDEA_IMPROVEMENT_PROMPT` erzeugt eine überarbeitete
   Briefingfassung (Markdown mit Abschnitten). Die Datei `idea.txt` dient
   als spätere Kontextquelle.
4. **Outline:** Zunächst wird eine Outline erstellt, anschließend mit einem
   Verbesserungs-Prompt verfeinert und durch `_clean_outline_sections`
   bereinigt. Ergebnis sind strukturierte Abschnittsdaten mit Wortbudgets,
   gespeichert in `outline.txt` sowie als Ausgangspunkt `iteration_00.txt`.
5. **Abschnittsweise Generierung:** Für jeden Outline-Abschnitt wird ein
   Prompt erstellt, der Briefing, Outline, Kernaussagen, Stilvorgaben,
   SEO-Keywords und einen Recap des vorherigen Abschnitts kombiniert. Die
   generierten Abschnitte werden laufend in `current_text.txt`
   zusammengeführt.
6. **Rubrik-Prüfung:** Der vollständige Entwurf wird mit
   `TEXT_TYPE_CHECK_PROMPT` geprüft. Liefert der Bericht keine Hinweise auf
   „keine Abweichungen“, folgt eine Korrektur mittels
   `TEXT_TYPE_FIX_PROMPT`. Beide Antworten landen in separaten Dateien.
7. **Revisionen:** Für jede zusätzliche Iteration ruft der Agent den Text
   erneut auf dem `REVISION_SYSTEM_PROMPT` (plus optionalem
   Compliance-Hinweis) auf. Optional erzeugte Reflexionen werden als
   `reflection_XX.txt` abgelegt.
8. **Compliance & Abschluss:** Jeder Textdurchlauf wird auf sensible
   Begriffe, Platzhalter und Compliance-Hinweise geprüft. Das finale Ergebnis
   landet in `Final-<timestamp>.txt`, Metadaten in `metadata.json`, das
   Compliance-Protokoll in `compliance.json`.

## Konfiguration

`wordsmith.config.Config` kapselt alle Laufzeitoptionen. Eine optionale
JSON-Datei kann diese Werte überschreiben. Unterstützte Schlüssel
entsprechen den Attributen des `Config`-Dataclasses, u. a.:

* `output_dir`, `logs_dir`
* `llm_provider`, `llm_model`, `ollama_base_url`
* `system_prompt`, `context_length`, `token_limit`
* `prompt_config_path` – Pfad zur JSON-Datei mit den Prompt-Templates
* `llm` (Objekt mit Parametern wie `temperature`, `top_p`, `seed`)

Ohne weitere Anpassung generiert WordSmith bis zu 900 Tokens pro Aufruf
(`llm.num_predict`, alias `llm.max_tokens`), wobei der Wert vollständig
konfigurierbar bleibt.

`Config.adjust_for_word_count(word_count)` setzt den gewünschten Umfang,
skalieren `context_length` auf mindestens `word_count * 4` (mindestens
8192) und `token_limit` auf mindestens `word_count * 1,9` (ebenfalls
mindestens 8192). Gleichzeitig werden deterministische LLM-Parameter
für `presence_penalty`, `frequency_penalty` und die Seed-Einstellung
vereinheitlicht; `temperature` und `top_p` behalten die in der
Konfiguration definierten Werte. Falls verfügbar, wird `num_predict`
auf das Token-Limit angepasst, sofern kein eigener Wert konfiguriert
wurde. `ensure_directories()` erstellt Output- und Log-Ordner,
`cleanup_temporary_outputs()` entfernt Artefakte früherer Läufe.

Die mitgelieferte Datei `wordsmith/prompts_config.json` enthält alle
Prompt-Templates. Wird ein eigener Satz benötigt, kann `prompt_config_path`
auf eine alternative JSON-Datei zeigen. `prompts.set_system_prompt()`
ermöglicht Laufzeit-Overrides für den globalen oder stufenweisen
Systemprompt.

Die JSON-Datei bündelt die Stufen unter dem Schlüssel `stages`. Jede Stufe
(`briefing`, `section`, `final_draft` usw.) besitzt ein Objekt mit den Feldern
`system_prompt`, `prompt` und `parameters`. Beispiel:

```json
{
  "system_prompt": "…",
  "stages": {
    "briefing": {
      "system_prompt": "…",
      "prompt": "…",
      "parameters": {"temperature": 0.65, "top_p": 1.0, "presence_penalty": 0.05, "frequency_penalty": 0.05}
    }
  }
}
```

So lassen sich Texte, Systemprompts und LLM-Parameter pro Pipeline-Schritt
gemeinsam anpassen.

## Artefakte & Logging

Während `WriterAgent.run()` entstehen im Ausgabeverzeichnis u. a. folgende
Dateien:

* `Final-<timestamp>.txt` – finaler Text (zusätzlich auf `stdout`).
* `current_text.txt` – jeweils letzter Zwischenstand.
* `briefing.json`, `idea.txt`, `outline.txt` – Ergebnisse der frühen Pipeline.
* `iteration_XX.txt` – Versionen nach jeder Überarbeitung (inklusive `iteration_00.txt` mit der Outline).
* `text_type_check.txt` und `text_type_fix.txt` – Rubrik-Report bzw. ggf. korrigierte Fassung.
* `metadata.json` – Eckdaten wie Zielgruppe, finales Wortzählungsergebnis,
  verwendetes Modell und Rubrik-Ergebnis.
* `compliance.json` – Audit-Log zu Platzhaltern, sensiblen Begriffen und Quellenmodus.

Das Log-Verzeichnis enthält `run.log` (chronologische Ereignisse) und
`llm.log` (Systemprompts, Outline, Parameter und Telemetrie).

Alle erzeugten Dateien und Prüfungen sind in
[`docs/automatikmodus.md`](docs/automatikmodus.md) detailliert beschrieben.

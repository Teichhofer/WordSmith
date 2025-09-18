# WordSmith

WordSmith operates exclusively in the **Automatikmodus** and exposes the
full workflow through a single CLI command. The core pipeline is
implemented in `wordsmith.agent.WriterAgent` and orchestrated by
`cli.py`.

The German-language production guidelines – including every
LLM-interaction and quality gate – are documented in
[`docs/automatikmodus.md`](docs/automatikmodus.md).

## Voraussetzungen

WordSmith setzt auf ein lokal verfügbares LLM. Standardmäßig wird ein
Ollama-Dienst angesprochen und das CLI erfragt ein installiertes Modell,
falls keines vorgegeben ist. Stellen Sie daher sicher, dass

* der Ollama-Dienst läuft (`ollama serve`),
* mindestens ein Modell installiert ist (`ollama list`), und
* das Modell für die gewünschte Textproduktion geeignet ist.

## CLI-Referenz

Der Automatikmodus wird über das Unterkommando `automatikmodus`
gestartet. Die folgenden Parameter decken sämtliche vom Code
unterstützten Funktionen ab:

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
  --config config.json \
  --output-dir output \
  --logs-dir logs \
  --ollama-model mistral \
  --ollama-base-url http://localhost:11434
```

Die Optionen im Einzelnen:

| Option | Pflicht? | Beschreibung |
| ------ | -------- | ------------ |
| `--title` | ✓ | Arbeitstitel für den Text. |
| `--content` | ✓ | Briefing oder Notizen, die in Schritt 1 normalisiert werden. |
| `--text-type` | ✓ | Texttyp (z. B. Blogartikel, Pressemitteilung). |
| `--word-count` | ✓ | Zielwortzahl des Endtexts. Muss > 0 sein. |
| `--iterations` |   | Anzahl der Revisionen nach dem ersten Entwurf (Default: 1). |
| `--llm-provider` |   | Kennung des LLM-Anbieters. Der Code erwartet aktuell `ollama`. |
| `--audience` |   | Zielgruppe; Default siehe `wordsmith.defaults.DEFAULT_AUDIENCE`. |
| `--tone` |   | Tonalität; Default siehe `DEFAULT_TONE`. |
| `--register` |   | Anrede/Sprachregister (`Du`/`Sie`). Werte werden anhand `REGISTER_ALIASES` normalisiert. |
| `--variant` |   | Sprachvariante (`DE-DE`, `DE-AT`, `DE-CH`). |
| `--constraints` |   | Zusätzliche Muss-/Kann-Vorgaben für den Text. |
| `--sources-allowed` |   | `true`/`false`, ob Quellen im Text erlaubt sind. |
| `--seo-keywords` |   | Kommagetrennte Liste eindeutiger SEO-Schlüsselwörter. |
| `--config` |   | Pfad zu einer optionalen JSON-Konfiguration; Werte überschreiben Defaults. |
| `--output-dir` |   | Zielverzeichnis für Dateien wie `Final-*.txt` oder `metadata.json`. |
| `--logs-dir` |   | Verzeichnis für Lauf- und Prompt-Logs. |
| `--ollama-model` |   | Name des Ollama-Modells. Ohne Angabe startet eine interaktive Auswahl (sofern TTY). |
| `--ollama-base-url` |   | Basis-URL der Ollama-API (Default: `http://localhost:11434`). |

Die CLI gibt den finalen Text auf `stdout` aus, schreibt Statusmeldungen
auf `stderr` und beendet sich mit

* `0` bei Erfolg,
* `1` bei Fehlern im WriterAgent oder Benutzungsfehlern,
* `2` für Konfigurationsprobleme und
* `3` bei Ollama-spezifischen Fehlern.

## Konfiguration

`wordsmith.config.Config` kapselt alle Laufzeitoptionen. Eine optionale
JSON-Datei kann diese Werte überschreiben. Unterstützte Schlüssel
entsprechen den Attributen des `Config`-Dataclasses, u. a.:

* `output_dir`, `logs_dir`
* `llm_provider`, `llm_model`, `ollama_base_url`
* `system_prompt`, `context_length`, `token_limit`
* `llm` (Objekt mit Parametern wie `temperature`, `top_p`, `seed`)

Vor jedem Lauf sorgt `Config.adjust_for_word_count` für sinnvolle
Fenstergrößen und setzt deterministische LLM-Parameter (Seed 42). Die
Methoden `ensure_directories()` und `cleanup_temporary_outputs()` legen
benötigte Verzeichnisse an und entfernen temporäre Artefakte früherer
Durchläufe.

## Ausgaben & Artefakte

Während `WriterAgent.run()` den Automatikmodus ausführt, entstehen im
Ausgabeverzeichnis mehrere Dateien:

* `Final-<timestamp>.txt` – finaler Text (zusätzlich auf `stdout`).
* `current_text.txt` – jeweils letzter Zwischenstand.
* `briefing.json`, `idea.txt`, `outline.txt` – Ergebnisse der frühen Pipeline-Schritte.
* `iteration_XX.txt` – Versionen nach jeder Überarbeitung.
* `metadata.json` – Eckdaten wie Zielgruppe, finaler Wortcount,
  verwendetes Modell und Rubrik-Ergebnis.
* `compliance.json` – Audit-Log zu Platzhaltern, sensiblen Begriffen und Quellenprüfung.

Das Log-Verzeichnis enthält ergänzend `run.log` (Ereignisse der
Pipeline) und `llm.log` (Systemprompt, Outline, LLM-Parameter und
Zusammenfassung der Aufrufe).

Alle erzeugten Dateien und Prüfungen entsprechen den in
`docs/automatikmodus.md` beschriebenen Funktionen und Qualitätskriterien.

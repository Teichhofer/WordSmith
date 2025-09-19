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
  --compliance-hint \
  --config config.json \
  --output-dir output \
  --logs-dir logs \
  --ollama-model mistral \
  --ollama-base-url http://localhost:11434
```

Alternativ können alle Parameter in einer JSON-Datei hinterlegt und per
`--input-file` geladen werden:

```bash
python cli.py automatikmodus --input-file lauf.json
```

Im Repository liegt unter `docs/examples/automatikmodus-input.json` eine
vollständig befüllte Beispiel-Datei. Der über `--input-file` angegebene
Pfad kann entweder relativ zum aktuellen Arbeitsverzeichnis oder als
absoluter Pfad angegeben werden.

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
| `--compliance-hint` |   | Flag ohne Parameter; hängt den COMPLIANCE-HINWEIS ans Textende an (Default: deaktiviert). |
| `--config` |   | Pfad zu einer optionalen JSON-Konfiguration; Werte überschreiben Defaults. |
| `--output-dir` |   | Zielverzeichnis für Dateien wie `Final-*.txt` oder `metadata.json`. |
| `--logs-dir` |   | Verzeichnis für Lauf- und Prompt-Logs. |
| `--ollama-model` |   | Name des Ollama-Modells. Ohne Angabe startet eine interaktive Auswahl (sofern TTY). |
| `--ollama-base-url` |   | Basis-URL der Ollama-API (Default: `http://localhost:11434`). |
| `--input-file` |   | Pfad zu einer JSON-Datei, die alle oben genannten Argumente enthalten kann. Angaben auf der CLI überschreiben die Datei. |

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

Optional lassen sich auch `output_dir`, `logs_dir`, `ollama_model` oder
`config` definieren. CLI-Argumente haben stets Vorrang vor den Werten aus der
Datei.

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
* `prompt_config_path` – Pfad zur JSON-Datei mit den Prompt-Templates
* `llm` (Objekt mit Parametern wie `temperature`, `top_p`, `seed`)

Die mitgelieferte Datei `wordsmith/prompts_config.json` enthält alle
Prompt-Templates. Wird ein abweichender Satz an Prompts benötigt, kann
`prompt_config_path` auf eine eigene JSON-Datei zeigen. Vor jedem Lauf
lädt die CLI diese Datei und nutzt `system_prompt` weiterhin als
Laufzeitüberschreibung.

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

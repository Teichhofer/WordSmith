# Automatikmodus (überarbeitet für bessere Textqualität)

Dieser Leitfaden beschreibt den **Automatikmodus** so, dass eine Entwicklerin die Funktionalität nachbauen **und** hochwertige Texte reproduzierbar erzeugen kann. Er ergänzt den bisherigen Ablauf um eindeutige Qualitätskriterien, robuste Prompts, Stil-Regeln, Anti-Halluzinations-Vorgaben und deterministische Parameter.

---

## Ziele & Qualitätskriterien (Akzeptanzkriterien)

Ein Durchlauf gilt als erfolgreich, wenn der finale Text:

1. **Ziel & Publikum** klar adressiert (Wer liest? Welches Ziel?).  
2. **Fakten** nicht erfindet (bei Lücken: Platzhalter wie `[QUELLE]`, `[DATUM]` statt Halluzinationen).  
3. **Struktur** logisch und vollständig ist (keine Überschneidungen zwischen Abschnitten).  
4. **Stil & Ton** passend zur `text_type`-Spezifikation ist (siehe Rubrik).  
5. **Länge** innerhalb ±3 % der Zielwortzahl liegt (nach sinnvoller Verdichtung, nicht bloßem Abschneiden).  
6. **Lesbarkeit** gewährleistet (aktive Verben, konkrete Substantive, variiertes Satztempo, klare Übergänge).  
7. **Kohärenz** zwischen Abschnitten hat (Begriffe, Perspektive, Zeitform konsistent).  
8. **Wiederholungen** und Füllwörter vermeidet.

---

## Eingaben & Initialisierung

1. **CLI erfragt**  
   - `title` (Arbeitstitel), `content` (Briefing/Notizen), `text_type`, `word_count`, `iterations`, `llm_provider`.  
   - **Neu:** `audience` (Zielgruppe), `tone` (z. B. sachlich, lebendig), `register` (Du/Sie), `variant` (DE-DE/DE-AT/DE-CH), `constraints` (Muss/Muss-nicht), `sources_allowed` (ja/nein), `seo_keywords` (optional).

2. **Agent-Erzeugung**  
   `WriterAgent(topic, word_count, steps=[], iterations, config, content, text_type, audience, tone, register, variant, constraints, sources_allowed, seo_keywords)`.

3. **Konfiguration**  
   - `Config.adjust_for_word_count()` skaliert Kontextlänge/Tokenlimit.  
   - **Determinismus:**  
     - `temperature=0.2` (0.0–0.3 für Präzision), `top_p=0.9`, `presence_penalty=0`, `frequency_penalty=0.3`.  
     - Falls unterstützt: `seed` setzen.  
   - Logs- und Output-Verzeichnisse anlegen.

4. **System-/Rollenprompt (global)**  
   „Du bist ein präziser deutschsprachiger Fachtexter. Du erfindest **keine** Fakten. Bei fehlenden Daten nutzt du **Platzhalter** in eckigen Klammern. Deine Texte sind klar strukturiert, aktiv formuliert, redundanzarm und adressatengerecht.“

---

## Schritt 1: Briefing normalisieren (neuer Schritt)

**Ziel:** Aus verstreuten Eingaben ein **Arbeitsbriefing** erzeugen, das alle späteren Prompts speist.

- **PROMPT `BRIEFING_PROMPT`**  
  _Eingaben:_ `title, content, text_type, audience, tone, register, variant, constraints, seo_keywords`  
  _Ausgabe:_ kompaktes JSON (Ziel, Kernaussagen, definierte Begriffe, Stilvorgaben, SEO-Begriffe).
- Dieses JSON wird in `output/briefing.json` gespeichert und in allen Folge-Prompts eingebettet.

---

## Schritt 2: Idee verbessern (präzisiert)

1. **`IDEA_IMPROVEMENT_PROMPT`**  
   Anforderungen:  
   - Inhalt sprachlich straffen, **ohne neue Fakten**.  
   - Unklare Stellen markieren (`[KLÄREN: …]`), Widersprüche auflösen oder kenntlich machen.  
   - Kernaussagen als Bullet-Liste + kurze Zusammenfassung (1–2 Sätze).  
2. Ergebnis ersetzt den ursprünglichen `content` und wird als `output/idea.txt` gespeichert.

---

## Schritt 3: Outline erzeugen & verfeinern (robust)

1. **`OUTLINE_PROMPT`**  
   Erzeuge eine **hierarchische**, nummerierte Gliederung (1, 1.1, …) mit:  
   - Abschnittstitel, **Rollenfunktion** (z. B. Hook, Kontext, Argument, Gegenargument, Fazit, CTA),  
   - **Wortbudget** je Abschnitt (Summe = `word_count`),  
   - **Liefergegenstand/Ergebnis** je Abschnitt (welche Frage wird beantwortet?),  
   - **Für Fiktion:** Figurenliste mit Rolle, Ziel, Konflikt. **Für Sachtexte:** Schlüsselbegriffe/Definitionen.

2. **`OUTLINE_IMPROVEMENT_PROMPT`**  
   - Entfernt Überschneidungen, schärft Reihenfolge, fügt fehlende Brückenabschnitte ein, balanciert Wortbudgets.  
   - Keine Fakten hinzufügen; bei Bedarf Platzhalter setzen.

3. **Bereinigung**  
   `_clean_outline()` stellt sicher:  
   - keine leeren/negativen Budgets; Rest ins letzte sinnvolle Segment,  
   - alle Abschnittsrollen vergeben,  
   - Zählung konsistent.  
   Speichern als `output/outline.txt` + `iteration_00.txt`.

---

## Schritt 4: Abschnittsweise Textgenerierung (qualitätsgesichert)

1. `_parse_outline()` liefert `(title, role, budget, brief)`-Paare.  
2. **`SECTION_PROMPT`** pro Abschnitt:  
   - Nutzt `briefing.json`, verbesserte Idee und Outline-Brief.  
   - Regeln:  
     - **Kein** neues Wissen erfinden; bei Bedarf `[QUELLE]`/`[DATUM]`.  
     - **Transitionsatz** zum vorherigen Abschnitt (außer beim ersten).  
     - **Stilregeln**: aktive Verben, spezifische Substantive, Varianz in Satzlängen, keine Füllwörter, keine Phrasen wie „In diesem Abschnitt werden wir…“.  
     - **Terminologie** aus `briefing.json` verwenden.  
   - Post-Processing: `_truncate_words()` nur, wenn > Budget; zuvor **verdichten**: Redundanzen kürzen, Füllwörter entfernen, Beispiele straffen.  
3. Nach jeder Sektion: Append, `output/current_text.txt` + `iteration_01.txt` aktualisieren.

---

## Schritt 5: Texttyp-Prüfung & Korrektur (mit Rubrik)

1. Zusammenfügen; `_truncate_text()` nur nach **Verdichtung**.  
2. **`TEXT_TYPE_CHECK_PROMPT`** mit **Rubrik** (Beispiele):  
   - **Blog/Artikel:** klare These, Zwischenüberschriften, Beispiele/Belege, Fazit + CTA, SEO-Begriffe natürlich eingebunden.  
   - **Pressemitteilung:** Headline, Subline, Lead-Absatz (W-Fragen), Zitate, Boilerplate, Kontakt.  
   - **Produktbeschreibung:** Nutzen vor Features, Spezifikationen, Einwandbehandlung, klare CTA.  
   - **Whitepaper/Report:** Executive Summary, Methodik, Ergebnisse, Implikationen, Limitierungen, Quellen.  
   - **Story (Fiktion):** Perspektive konsistent, Ziel/Konflikt, Szene-Struktur, „Show, don’t tell“, sinnvolles Ende.  
   - **Sonstige**: projektspezifisch erweiterbar.

3. Bei Abweichung: **`TEXT_TYPE_FIX_PROMPT`**  
   - Korrigiere minimal-invasiv, **ohne** Faktenzuwachs.  
   - Akzeptiere Ersatz nur, wenn **Ähnlichkeits-Gate** erfüllt: ≥ 80 % gemeinsame Tokens & ≥ 0,9 Sequenzähnlichkeit.  
   - Sonst: kombiniere Fix mit Original und starte erneute Prüfung.

4. Speichern als `iteration_01.txt` (Basis für Revisionen).

---

## Schritt 6: Iterative Überarbeitung (zielgerichtet)

Für `i` in `1…iterations`:

- Lade `iteration_{i:02d}.txt`.  
- **`REVISION_PROMPT`** (Targeted Editing):  
  1) Klarheit & Prägnanz, 2) Flow & Übergänge, 3) Terminologie-Konsistenz,  
  4) Wiederholungen/N-Gram-Dopplungen tilgen, 5) Rhythmus variieren,  
  6) spezifische Verben/Nomen stärken, 7) Schlussteil schärfen (CTA/Resolution),  
  8) Registersicherheit (Du/Sie), 9) Variantenspezifika (z. B. ß/ss).  
- Prüfe Differenz zum Ausgang (Levenshtein/Ähnlichkeits-Schwelle),  
  verdichte vor `_truncate_words()`, speichere als `output/current_text.txt` und `iteration_{i+1:02d}.txt`.  
- Optional: **`REFLECTION_PROMPT`** → kurze Selbstkritik (3 Punkte) in `output/reflection_{i+1:02d}.txt`.

Nach der letzten Iteration: finaler Text zurückgeben (Länge ±3 %).

---

## Anti-Halluzinations- & Compliance-Regeln (durchgängig)

- Keine Tatsachen erfinden; stattdessen **Platzhalter** `[QUELLE]`, `[DATUM]`, `[ZAHL]`.  
- Wenn `sources_allowed=false`: keine Quellenangaben generieren, nur Platzhalter.  
- Wenn `sources_allowed=true`: formatiere Quellen konsistent (z. B. Kurzbeleg im Text, Literaturliste).  
- Keine sensiblen oder verbotenen Inhalte; Markierungen `[ENTFERNT: …]` statt problematischem Text.

---

## SEO (optional, falls `seo_keywords` gesetzt)

- Keywords natürlich, nicht erzwungen einbinden; Synonyme erlaubt.  
- Ein **Snippet** (max. 155 Zeichen) und **Titel-Tag-Vorschlag** generieren.  
- Slug-Vorschlag aus `title` ableiten.

---

## Ausgabe-Artefakte & Logging

- `logs/run.log`: strukturierte Schritt-Logs.  
- `logs/llm.log`: JSON je LLM-Call (Prompt, Parameter, Antwort-Metadaten).  
- `output/briefing.json`, `output/idea.txt`, `output/outline.txt`, `output/current_text.txt`, `output/iteration_XX.txt`, optional `output/reflection_XX.txt`.  
- **Neu:** `output/metadata.json` (title, audience, tone, register, keywords, final_word_count, rubric_passed: bool).

---

## Fehlerbehandlung & Defaults

- Fehlende Eingaben → sinnvolle Defaults:  
  - `audience`: „Allgemeine Leserschaft mit Grundkenntnissen“  
  - `tone`: „sachlich-lebendig“  
  - `register`: „Sie“  
  - `variant`: „DE-DE“  
- Bei Wortbudget-Unterlauf einzelner Abschnitte: proportionaler **Re-Balance**-Pass.  
- Bei zu knapper Kontextlänge: Abschnitte in **Batches** generieren; jeweils letzter Absatz rekaptuliert (`Recap-Satz`) für kohärente Übergänge.

---

## Prompt-Vorlagen (Platzhalter in `{…}`)

### `BRIEFING_PROMPT`
> Verdichte folgende Angaben zu einem Arbeitsbriefing als kompaktes JSON mit Schlüsseln: goal, audience, tone, register, variant, constraints, key_terms, messages, seo_keywords (optional).
> **Eingaben:**  
> title: {title}  
> text_type: {text_type}  
> audience: {audience}  
> tone: {tone}  
> register: {register}  
> variant: {variant}  
> constraints: {constraints}  
> seo_keywords: {seo_keywords}  
> notes: {content}

### `IDEA_IMPROVEMENT_PROMPT`
> Überarbeite diesen Rohinhalt **ohne neue Fakten**.  
> 1) Straffe Sprache, 2) markiere Unklarheiten `[KLÄREN: …]`, 3) gib Kernaussagen als Bullets + 1-Satz-Summary.  
> **Rohinhalt:** {content}

### `OUTLINE_PROMPT`
> Erzeuge eine hierarchische Gliederung für `{text_type}` zu `{title}` basierend auf dem Briefing:  
> {briefing_json}  
> Für jeden Abschnitt: Nummer, Titel, **Rollenfunktion**, **Wortbudget**, **Liefergegenstand**.  
> Gesamtwortzahl: {word_count}. Keine Fakten erfinden.

### `OUTLINE_IMPROVEMENT_PROMPT`
> Prüfe und verbessere die Outline: entferne Überschneidungen, füge fehlende Brücken, balanciere Budgets (Summe = {word_count}). Behalte Faktenneutralität.

### `SECTION_PROMPT`
> Schreibe Abschnitt {section_number} „{section_title}“ (Rolle: {role}) mit Ziel `{deliverable}`.  
> Nutze Briefing und bisherige Abschnitte (Kohärenz, Terminologie).  
> Regeln: aktive Verben, keine Füllphrasen, natürliche Übergänge, **keine** erfundenen Fakten (Platzhalter bei Lücken).  
> Zielwortzahl: {budget}.  
> **Bisheriger Kontext (Kurz-Recap)**: {previous_section_recap}

### `TEXT_TYPE_CHECK_PROMPT`
> Prüfe den Text gegen die Rubrik für `{text_type}` (Kriterienliste siehe oben). Liste **konkrete** Abweichungen und betroffene Stellen.

### `TEXT_TYPE_FIX_PROMPT`
> Korrigiere nur die genannten Abweichungen **minimal-invasiv**, ohne Faktenzuwachs. Erhalte Ton, Terminologie, Struktur.

### `REVISION_PROMPT`
> Überarbeite zielgerichtet nach diesen Prioritäten: Klarheit, Flow, Terminologie, Wiederholungen, Rhythmus, starke Verben, Abschluss, Register, Variantenspezifika. Bei fehlenden Daten: Platzhalter.

### `REFLECTION_PROMPT` (optional)
> Nenne die 3 wirksamsten nächsten Verbesserungen (knapp, umsetzbar).

---

## Implementierungs-Notizen

- **Ähnlichkeits-Gate:** Verwende Token-Overlap & Sequenz-Ähnlichkeit (z. B. Jaccard & normalized Levenshtein).  
- **Wortzahl-Kontrolle:** Vor hartem Trimmen stets **Verdichten** (Satzebene → Absatzebene → Abschnittsebene).  
- **Übergänge:** Jeder Abschnitt beginnt (außer der erste) mit einem 1-Satz-Anschluss, endet mit einem 1-Satz-Vorspann.  
- **Terminologie-Cache:** Aus `briefing.json/key_terms` generieren; in jedem Schritt injizieren.  
- **Register/Variante:** Bei „Sie“ keine Du-Formen; ß/ss gemäß `variant`.  
- **SEO:** Nur, wenn gesetzt; Keyword-Dichte nie erzwingen.

---

Mit dieser Fassung erhält der Automatikmodus klare Qualitätsziele, präzise Prompts, belastbare Prüfungen und deterministische Einstellungen – damit der `WriterAgent` seine Kernaufgabe, **bessere Texte zu schreiben**, konsistent und reproduzierbar erfüllt.


"""Command line interface for the WordSmith automatikmodus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, TextIO

from wordsmith import prompts
from wordsmith.agent import WriterAgent, WriterAgentError
from wordsmith.config import DEFAULT_LLM_PROVIDER, ConfigError, load_config
from wordsmith.ollama import OllamaClient, OllamaError
from wordsmith.defaults import (
    DEFAULT_AUDIENCE,
    DEFAULT_CONSTRAINTS,
    DEFAULT_REGISTER,
    DEFAULT_SOURCES_ALLOWED,
    DEFAULT_TONE,
    DEFAULT_VARIANT,
    REGISTER_ALIASES,
    VALID_VARIANTS,
)

DEFAULT_SEO_KEYWORDS: tuple[str, ...] = ()


class _InputFileError(Exception):
    """Raised when the CLI input settings file is invalid."""


_CLI_OPTION_MAP: dict[str, str] = {
    "title": "--title",
    "content": "--content",
    "text_type": "--text-type",
    "word_count": "--word-count",
    "iterations": "--iterations",
    "llm_provider": "--llm-provider",
    "audience": "--audience",
    "tone": "--tone",
    "register": "--register",
    "variant": "--variant",
    "constraints": "--constraints",
    "sources_allowed": "--sources-allowed",
    "seo_keywords": "--seo-keywords",
    "include_compliance_note": "--compliance-hint",
    "config": "--config",
    "output_dir": "--output-dir",
    "logs_dir": "--logs-dir",
    "ollama_model": "--ollama-model",
    "ollama_base_url": "--ollama-base-url",
}

VALID_REGISTERS = dict(REGISTER_ALIASES)


class _ProgressPrinter:
    def __init__(self, total_steps: int, stream: TextIO | None = None) -> None:
        self.total_steps = max(1, total_steps)
        self.stream = stream or sys.stderr
        self.completed = 0

    def __call__(self, event: dict[str, object]) -> None:
        status = str(event.get("status", ""))
        message = str(event.get("message", ""))
        if status == "started":
            self._write(f"[0/{self.total_steps}] {message}")
            return
        if status in {"completed", "succeeded"}:
            self.completed = min(self.completed + 1, self.total_steps)
            self._write(f"[{self.completed}/{self.total_steps}] {message}")
            return
        if status == "failed":
            self._write(f"[FEHLER] {message}")
            return
        if status == "warning":
            self._write(f"[WARNUNG] {message}")

    def _write(self, text: str) -> None:
        print(text, file=self.stream)
        try:
            self.stream.flush()
        except Exception:  # pragma: no cover - defensive
            pass


def _format_runtime(runtime_seconds: float) -> str:
    if runtime_seconds < 60:
        return f"{runtime_seconds:.2f} Sekunden"

    hours = int(runtime_seconds // 3600)
    minutes = int((runtime_seconds % 3600) // 60)
    seconds = runtime_seconds - hours * 3600 - minutes * 60

    def _format_unit(value: int, singular: str, plural: str) -> str:
        return f"{value} {singular if value == 1 else plural}"

    parts: list[str] = []
    if hours:
        parts.append(_format_unit(hours, "Stunde", "Stunden"))
    if hours or minutes:
        parts.append(_format_unit(minutes, "Minute", "Minuten"))
    parts.append(f"{seconds:.2f} Sekunden")

    formatted = " ".join(parts)
    return f"{formatted} ({runtime_seconds:.2f} Sekunden)"


def _print_runtime(runtime_seconds: float | None, stream: TextIO | None = None) -> None:
    if runtime_seconds is None:
        return
    target_stream = stream or sys.stderr
    print(f"Gesamtlaufzeit: {_format_runtime(runtime_seconds)}", file=target_stream)


def _parse_bool(value: str) -> bool:
    truthy = {"true", "1", "yes", "ja"}
    falsy = {"false", "0", "no", "nein"}
    value_normalised = value.strip().lower()
    if value_normalised in truthy:
        return True
    if value_normalised in falsy:
        return False
    raise argparse.ArgumentTypeError(
        "Wert muss 'ja'/'nein' beziehungsweise 'true'/'false' sein."
    )


def _parse_keywords(value: str) -> List[str]:
    if not value:
        return []
    keywords: List[str] = []
    seen = set()
    for keyword in value.split(","):
        cleaned = keyword.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        keywords.append(cleaned)
    return keywords


def _parse_audience(value: str) -> str:
    value = value.strip()
    return value


def _parse_tone(value: str) -> str:
    value = value.strip()
    return value


def _parse_register(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    normalised = value.lower()
    if normalised not in VALID_REGISTERS:
        valid_values = ", ".join(sorted(VALID_REGISTERS.values()))
        raise argparse.ArgumentTypeError(
            f"Ungültiges Register '{value}'. Erlaubt sind: {valid_values}."
        )
    return VALID_REGISTERS[normalised]


def _parse_variant(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    normalised = value.upper()
    if normalised not in VALID_VARIANTS:
        valid_values = ", ".join(sorted(VALID_VARIANTS))
        raise argparse.ArgumentTypeError(
            f"Ungültige Sprachvariante '{value}'. Erlaubt sind: {valid_values}."
        )
    return normalised


def _parse_constraints(value: str) -> str:
    value = value.strip()
    return value


def _parse_iterations(value: str) -> int:
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError(
            "Anzahl der Iterationen darf nicht leer sein."
        )
    try:
        iterations = int(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise argparse.ArgumentTypeError(
            "Anzahl der Iterationen muss eine Ganzzahl sein."
        ) from exc
    if iterations < 0:
        raise argparse.ArgumentTypeError(
            "Anzahl der Iterationen darf nicht negativ sein."
        )
    return iterations


_REQUIRED_SETTINGS: frozenset[str] = frozenset({
    "title",
    "content",
    "text_type",
    "word_count",
})


def _coerce_bool_from_input(key: str, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _parse_bool(value)
    raise _InputFileError(
        f"Wert für '{key}' muss boolesch sein (true/false)."
    )


def _format_keywords_argument(value: object) -> str:
    if isinstance(value, str):
        keywords = _parse_keywords(value)
    elif isinstance(value, Iterable):
        keywords = _parse_keywords(",".join(str(item) for item in value))
    else:
        raise _InputFileError(
            "SEO-Schlüsselwörter müssen als String oder Liste angegeben werden."
        )
    return ", ".join(keywords)


def _build_setting_tokens(key: str, value: object) -> List[str]:
    if key not in _CLI_OPTION_MAP:
        raise _InputFileError(f"Unbekannte Einstellung '{key}'.")

    option = _CLI_OPTION_MAP[key]

    if value is None:
        if key in _REQUIRED_SETTINGS:
            raise _InputFileError(f"Einstellung '{key}' darf nicht leer sein.")
        # Optional Parameter werden bei None ignoriert.
        return []

    if key == "include_compliance_note":
        return [option] if _coerce_bool_from_input(key, value) else []
    if key == "sources_allowed":
        allowed = _coerce_bool_from_input(key, value)
        return [option, "true" if allowed else "false"]
    if key == "seo_keywords":
        formatted = _format_keywords_argument(value)
        return [option, formatted]

    # Für numerische Werte vertraut der Parser auf die eigentliche Validierung.
    return [option, str(value)]


def _load_input_file(path: Path) -> List[str]:
    if not path.exists():
        raise _InputFileError(
            f"Einstellungsdatei '{path}' wurde nicht gefunden."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise _InputFileError(
            f"Einstellungsdatei konnte nicht gelesen werden: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise _InputFileError(
            "Einstellungsdatei muss ein JSON-Objekt enthalten."
        )

    tokens: List[str] = []
    for key, value in data.items():
        tokens.extend(_build_setting_tokens(key, value))

    return tokens


def _expand_with_input_file(arguments: Sequence[str]) -> List[str]:
    values = list(arguments)
    if not values:
        return values

    indices = [index for index, item in enumerate(values) if item == "--input-file"]
    if not indices:
        return values
    if len(indices) > 1:
        raise _InputFileError("--input-file darf nur einmal angegeben werden.")

    index = indices[0]
    if index + 1 >= len(values):  # Fehlende Angabe; argparse meldet den Fehler.
        return values

    path_argument = values[index + 1]
    try:
        settings_tokens = _load_input_file(Path(path_argument))
    except _InputFileError:
        raise

    values[1:1] = settings_tokens
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordsmith",
        description="Automatisierte Textproduktion gemäß Automatikmodus-Dokumentation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    automatik_parser = subparsers.add_parser(
        "automatikmodus",
        help="Starte den Automatikmodus und schreibe alle Ausgabedateien.",
    )
    automatik_parser.add_argument("--title", required=True, help="Arbeitstitel des Textes.")
    automatik_parser.add_argument(
        "--content",
        required=True,
        help="Briefing oder Notizen, die in den Prozess einfließen.",
    )
    automatik_parser.add_argument(
        "--text-type",
        required=True,
        dest="text_type",
        help="Texttyp, z. B. Blogartikel, Pressemitteilung, Produktbeschreibung.",
    )
    automatik_parser.add_argument(
        "--word-count",
        required=True,
        type=int,
        dest="word_count",
        help="Zielwortzahl für den finalen Text.",
    )
    automatik_parser.add_argument(
        "-n",
        "--iterations",
        type=_parse_iterations,
        default=1,
        help="Anzahl der Überarbeitungsdurchläufe.",
    )
    automatik_parser.add_argument(
        "--llm-provider",
        default=DEFAULT_LLM_PROVIDER,
        dest="llm_provider",
        help="Bezeichner des verwendeten LLM-Anbieters.",
    )
    automatik_parser.add_argument(
        "--audience",
        type=_parse_audience,
        default=DEFAULT_AUDIENCE,
        help="Adressierte Zielgruppe (Default: allgemeine Leserschaft).",
    )
    automatik_parser.add_argument(
        "--tone",
        type=_parse_tone,
        default=DEFAULT_TONE,
        help="Gewünschter Tonfall, z. B. sachlich, lebendig.",
    )
    automatik_parser.add_argument(
        "--register",
        type=_parse_register,
        default=DEFAULT_REGISTER,
        help="Sprachregister bzw. Anrede (Du/Sie).",
    )
    automatik_parser.add_argument(
        "--variant",
        type=_parse_variant,
        default=DEFAULT_VARIANT,
        help="Sprachvariante, z. B. DE-DE, DE-AT oder DE-CH.",
    )
    automatik_parser.add_argument(
        "--constraints",
        type=_parse_constraints,
        default=DEFAULT_CONSTRAINTS,
        help="Zusätzliche Muss-/Kann-Vorgaben für den Text.",
    )
    automatik_parser.add_argument(
        "--sources-allowed",
        type=_parse_bool,
        default=DEFAULT_SOURCES_ALLOWED,
        dest="sources_allowed",
        help="Ob Quellenangaben erlaubt sind (ja/nein).",
    )
    automatik_parser.add_argument(
        "--seo-keywords",
        type=_parse_keywords,
        default=DEFAULT_SEO_KEYWORDS,
        dest="seo_keywords",
        help="Kommagetrennte Liste relevanter SEO-Schlüsselwörter.",
    )
    automatik_parser.add_argument(
        "--compliance-hint",
        action="store_true",
        dest="include_compliance_note",
        help="Fügt den COMPLIANCE-HINWEIS ans Textende an (Standard: deaktiviert).",
    )
    automatik_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Pfad zu einer optionalen JSON-Konfigurationsdatei.",
    )
    automatik_parser.add_argument(
        "--input-file",
        type=Path,
        dest="input_file",
        default=None,
        help="Pfad zu einer JSON-Datei mit allen Eingabeparametern.",
    )
    automatik_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Ausgabeverzeichnis (überschreibt Konfiguration).",
    )
    automatik_parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="Log-Verzeichnis (überschreibt Konfiguration).",
    )
    automatik_parser.add_argument(
        "--ollama-model",
        dest="ollama_model",
        default=None,
        help="Name des Ollama-Modells, das für den Lauf genutzt werden soll.",
    )
    automatik_parser.add_argument(
        "--ollama-base-url",
        dest="ollama_base_url",
        default="http://localhost:11434",
        help="Basis-URL der lokalen Ollama-API (Default: http://localhost:11434).",
    )
    automatik_parser.set_defaults(func=_run_automatikmodus)
    return parser


def _interactive_model_choice(models: Sequence[str]) -> str:
    if not models:
        raise ValueError("Es wurden keine Modelle gefunden.")

    interactive = all(
        hasattr(stream, "isatty") and stream.isatty()
        for stream in (sys.stdin, sys.stdout)
    )
    if not interactive:
        return models[0]

    print("Verfügbare Ollama-Modelle:")
    for index, name in enumerate(models, start=1):
        print(f"  [{index}] {name}")

    while True:
        try:
            choice = input("Modell auswählen [1]: ").strip()
        except EOFError:
            choice = ""

        if not choice:
            return models[0]

        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(models):
                return models[index - 1]

        print("Ungültige Auswahl. Bitte eine Zahl eingeben.", file=sys.stderr)


def _configure_ollama(args: argparse.Namespace, config: "Config") -> Optional[int]:
    config.ollama_base_url = str(args.ollama_base_url)
    client = OllamaClient(base_url=config.ollama_base_url)
    try:
        models = client.list_models()
    except OllamaError as exc:
        print(f"Ollama-Modelle konnten nicht geladen werden: {exc}", file=sys.stderr)
        return 3

    if not models:
        print("Keine Ollama-Modelle gefunden. Bitte zunächst Modelle installieren.", file=sys.stderr)
        return 3

    model_names = [model.name for model in models]

    if args.ollama_model:
        if args.ollama_model not in model_names:
            available = ", ".join(model_names)
            print(
                (
                    f"Ollama-Modell '{args.ollama_model}' nicht gefunden. "
                    f"Verfügbare Modelle: {available}."
                ),
                file=sys.stderr,
            )
            return 2
        selected = args.ollama_model
    else:
        selected = _interactive_model_choice(model_names)

    config.llm_model = selected
    print(f"Verwende Ollama-Modell: {selected}", file=sys.stderr)
    return None


def _run_automatikmodus(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Konfiguration konnte nicht geladen werden: {exc}", file=sys.stderr)
        return 2

    if args.output_dir is not None:
        config.output_dir = Path(args.output_dir)
    if args.logs_dir is not None:
        config.logs_dir = Path(args.logs_dir)
    config.llm_provider = args.llm_provider
    config.llm_model = None
    config.ollama_base_url = None

    if config.llm_provider.lower() == "ollama":
        result = _configure_ollama(args, config)
        if result is not None:
            return result
    elif args.ollama_model:
        config.llm_model = args.ollama_model
        config.ollama_base_url = str(args.ollama_base_url)

    try:
        config.adjust_for_word_count(args.word_count)
    except ConfigError as exc:
        print(f"Ungültige Einstellung: {exc}", file=sys.stderr)
        return 2

    try:
        prompts.load_prompt_config(config.prompt_config_path)
    except prompts.PromptConfigurationError as exc:
        print(f"Prompt-Konfiguration konnte nicht geladen werden: {exc}", file=sys.stderr)
        return 2

    prompts.set_system_prompt(config.system_prompt)

    # The pipeline records six baseline completions plus revisions and reflections.
    total_steps = 7 + max(args.iterations, 0) * 2
    progress_printer = _ProgressPrinter(total_steps)

    agent = WriterAgent(
        topic=args.title,
        word_count=args.word_count,
        steps=[],
        iterations=args.iterations,
        config=config,
        content=args.content,
        text_type=args.text_type,
        audience=args.audience,
        tone=args.tone,
        register=args.register,
        variant=args.variant,
        constraints=args.constraints,
        sources_allowed=args.sources_allowed,
        seo_keywords=args.seo_keywords,
        include_compliance_note=args.include_compliance_note,
        progress_callback=progress_printer,
    )

    try:
        final_text = agent.run()
    except WriterAgentError as exc:
        print(f"Automatikmodus konnte nicht abgeschlossen werden: {exc}", file=sys.stderr)
        _print_runtime(agent.runtime_seconds, stream=sys.stderr)
        return 1

    print(final_text)
    _print_runtime(agent.runtime_seconds, stream=sys.stderr)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if not arguments:
        parser.print_help()
        return 1
    try:
        if arguments and arguments[0] == "automatikmodus":
            try:
                arguments = _expand_with_input_file(arguments)
            except _InputFileError as exc:
                print(f"Eingabedatei konnte nicht verwendet werden: {exc}", file=sys.stderr)
                return 2
        parsed = parser.parse_args(arguments)
        if hasattr(parsed, "func"):
            return parsed.func(parsed)
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer.", file=sys.stderr)
        return 130
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

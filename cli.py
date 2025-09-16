"""Command line interface for the WordSmith automatikmodus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from wordsmith import prompts
from wordsmith.agent import WriterAgent, WriterAgentError
from wordsmith.config import ConfigError, load_config

DEFAULT_AUDIENCE = "Allgemeine Leserschaft mit Grundkenntnissen"
DEFAULT_TONE = "sachlich-lebendig"
DEFAULT_REGISTER = "Sie"
DEFAULT_VARIANT = "DE-DE"


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
    return [keyword.strip() for keyword in value.split(",") if keyword.strip()]


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
        "--iterations",
        type=int,
        default=1,
        help="Anzahl der Überarbeitungsdurchläufe.",
    )
    automatik_parser.add_argument(
        "--llm-provider",
        default="mock-provider",
        dest="llm_provider",
        help="Bezeichner des verwendeten LLM-Anbieters.",
    )
    automatik_parser.add_argument(
        "--audience",
        default=DEFAULT_AUDIENCE,
        help="Adressierte Zielgruppe (Default: allgemeine Leserschaft).",
    )
    automatik_parser.add_argument(
        "--tone",
        default=DEFAULT_TONE,
        help="Gewünschter Tonfall, z. B. sachlich, lebendig.",
    )
    automatik_parser.add_argument(
        "--register",
        default=DEFAULT_REGISTER,
        help="Sprachregister bzw. Anrede (Du/Sie).",
    )
    automatik_parser.add_argument(
        "--variant",
        default=DEFAULT_VARIANT,
        help="Sprachvariante, z. B. DE-DE, DE-AT oder DE-CH.",
    )
    automatik_parser.add_argument(
        "--constraints",
        default="",
        help="Zusätzliche Muss-/Kann-Vorgaben für den Text.",
    )
    automatik_parser.add_argument(
        "--sources-allowed",
        type=_parse_bool,
        default=False,
        dest="sources_allowed",
        help="Ob Quellenangaben erlaubt sind (ja/nein).",
    )
    automatik_parser.add_argument(
        "--seo-keywords",
        type=_parse_keywords,
        default=[],
        dest="seo_keywords",
        help="Kommagetrennte Liste relevanter SEO-Schlüsselwörter.",
    )
    automatik_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Pfad zu einer optionalen JSON-Konfigurationsdatei.",
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
    automatik_parser.set_defaults(func=_run_automatikmodus)
    return parser


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

    try:
        config.adjust_for_word_count(args.word_count)
    except ConfigError as exc:
        print(f"Ungültige Einstellung: {exc}", file=sys.stderr)
        return 2

    prompts.set_system_prompt(config.system_prompt)

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
    )

    try:
        final_text = agent.run()
    except WriterAgentError as exc:
        print(f"Automatikmodus konnte nicht abgeschlossen werden: {exc}", file=sys.stderr)
        return 1

    print(final_text)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if not arguments:
        parser.print_help()
        return 1
    parsed = parser.parse_args(arguments)
    if hasattr(parsed, "func"):
        return parsed.func(parsed)
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

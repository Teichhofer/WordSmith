from __future__ import annotations

import io
import json
import re
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

import cli
from cli import (
    DEFAULT_AUDIENCE,
    DEFAULT_CONSTRAINTS,
    DEFAULT_REGISTER,
    DEFAULT_TONE,
    DEFAULT_VARIANT,
    main,
)
from wordsmith import llm
from wordsmith.ollama import OllamaModel
from wordsmith.config import Config


def test_print_runtime_formats_minutes_and_seconds() -> None:
    buffer = io.StringIO()
    cli._print_runtime(125.5, stream=buffer)
    assert (
        buffer.getvalue().strip()
        == "Gesamtlaufzeit: 2 Minuten 5.50 Sekunden (125.50 Sekunden)"
    )


def test_print_runtime_formats_hours_minutes_and_seconds() -> None:
    buffer = io.StringIO()
    cli._print_runtime(3723.5, stream=buffer)
    assert (
        buffer.getvalue().strip()
        == "Gesamtlaufzeit: 1 Stunde 2 Minuten 3.50 Sekunden (3723.50 Sekunden)"
    )


def test_automatikmodus_requires_arguments() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["automatikmodus"])
    assert exc.value.code == 2


def test_cli_can_be_interrupted_with_keyboard_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config(output_dir=tmp_path / "output", logs_dir=tmp_path / "logs")

    monkeypatch.setattr("cli.load_config", lambda _: config)
    monkeypatch.setattr("cli.prompts.set_system_prompt", lambda prompt: None)

    class InterruptingAgent:
        runtime_seconds = None

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def run(self) -> str:
            raise KeyboardInterrupt

    monkeypatch.setattr("cli.WriterAgent", InterruptingAgent)

    args = [
        "automatikmodus",
        "--title",
        "Abbruch",
        "--content",
        "Test",
        "--text-type",
        "Blog",
        "--word-count",
        "150",
        "--llm-provider",
        "openai",
    ]

    exit_code = main(args)
    captured = capsys.readouterr()

    assert exit_code == 130
    assert "Abbruch durch Benutzer" in captured.err


def test_automatikmodus_runs_and_creates_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"

    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    stale_iteration = output_dir / "iteration_99.txt"
    stale_iteration.write_text("veraltet", encoding="utf-8")

    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="llama2")],
    )

    briefing_payload = {"messages": ["Schritte"], "key_terms": ["Roadmap"]}
    idea_text = "- Klarer Fokus"
    outline_text = (
        "1. Auftakt (Rolle: Hook, Wortbudget: 60 Wörter) -> Kontext schaffen.\n"
        "2. Umsetzung (Rolle: Argument, Wortbudget: 120 Wörter) -> Handlung empfehlen."
    )
    section_one = "Der Auftakt benennt vertrauliche Themen und schafft Klarheit."
    section_two = "Die Umsetzung verweist auf vertrauliche Kennzahlen und Prioritäten."
    text_type_check = "Keine Abweichungen festgestellt."
    revision_text = (
        "## Überarbeitung\n"
        "Die Revision blendet vertrauliche Hinweise aus und fokussiert Umsetzung."
    )

    responses = deque(
        [
            llm.LLMResult(text=json.dumps(briefing_payload)),
            llm.LLMResult(text=idea_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=section_one),
            llm.LLMResult(text=section_two),
            llm.LLMResult(text=text_type_check),
            llm.LLMResult(text=revision_text),
        ]
    )

    def fake_generate_text(**_: object) -> llm.LLMResult:
        return responses.popleft()

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    iterations = 1

    args = [
        "automatikmodus",
        "--title",
        "Strategische Roadmap",
        "--content",
        "Wir planen die nächsten Schritte.",
        "--text-type",
        "Strategiepapier",
        "--word-count",
        "400",
        "--iterations",
        str(iterations),
        "--llm-provider",
        "ollama",
        "--ollama-model",
        "llama2",
        "--audience",
        "Vorstand",
        "--tone",
        "präzise",
        "--register",
        "Sie",
        "--variant",
        "DE-DE",
        "--constraints",
        "Keine Geheimnisse",
        "--sources-allowed",
        "nein",
        "--seo-keywords",
        "roadmap",
        "--output-dir",
        str(output_dir),
        "--logs-dir",
        str(logs_dir),
    ]

    exit_code = main(args)
    captured = capsys.readouterr()

    assert not stale_iteration.exists()

    assert exit_code == 0
    assert "[ENTFERNT: vertrauliche]" in captured.out
    assert "Gesamtlaufzeit" not in captured.out
    runtime_match = re.search(r"Gesamtlaufzeit: ([0-9]+\.[0-9]{2}) Sekunden", captured.err)
    assert runtime_match
    runtime_seconds_cli = float(runtime_match.group(1))

    total_steps = 7 + iterations
    progress_lines = [line for line in captured.err.splitlines() if line.strip()]
    assert progress_lines[0].startswith(f"[0/{total_steps}] Automatikmodus gestartet")
    assert any(
        line.startswith(f"[{total_steps}/{total_steps}] Automatikmodus erfolgreich abgeschlossen")
        for line in progress_lines
    )

    current_text = (output_dir / "current_text.txt").read_text(encoding="utf-8")
    final_files = list(output_dir.glob("Final-*.txt"))
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    compliance = json.loads((output_dir / "compliance.json").read_text(encoding="utf-8"))

    assert "[ENTFERNT: vertrauliche]" in current_text
    assert len(final_files) == 1
    final_file = final_files[0]
    assert re.fullmatch(r"Final-\d{8}-\d{6}\.txt", final_file.name)
    assert final_file.read_text(encoding="utf-8").strip() == current_text.strip()
    assert metadata["audience"] == "Vorstand"
    assert metadata["llm_model"] == "llama2"
    assert compliance["checks"]
    assert not responses

    run_entries = [
        json.loads(line)
        for line in (logs_dir / "run.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all("timestamp" in entry for entry in run_entries)
    for entry in run_entries:
        datetime.fromisoformat(entry["timestamp"])
    assert any(entry["step"] == "briefing" for entry in run_entries)
    assert any(entry["step"] == "revision_01" for entry in run_entries)
    complete_entry = next(entry for entry in run_entries if entry["step"] == "complete")
    runtime_seconds_log = complete_entry["data"]["runtime_seconds"]
    assert runtime_seconds_log >= 0
    assert runtime_seconds_cli == pytest.approx(runtime_seconds_log, rel=0.1, abs=0.1)

    llm_entries = [
        json.loads(line)
        for line in (logs_dir / "llm.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert llm_entries and llm_entries[0]["llm_generation"]["status"] == "success"
    assert "runtime_seconds" in llm_entries[0]
    assert llm_entries[0]["runtime_seconds"] == pytest.approx(runtime_seconds_log, rel=0.01, abs=0.01)


def test_cli_reports_llm_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="llama2")],
    )

    responses = deque(
        [
            llm.LLMResult(text=json.dumps({"messages": []})),
            llm.LLMResult(text="- Punkt"),
            llm.LLMResult(text="1. Eintrag (Rolle: Hook, Wortbudget: 50 Wörter) -> Test."),
            llm.LLMResult(text="1. Eintrag (Rolle: Hook, Wortbudget: 50 Wörter) -> Test."),
        ]
    )

    def failing_generate_text(**kwargs: object) -> llm.LLMResult:
        if responses:
            return responses.popleft()
        raise llm.LLMGenerationError("Fehler")

    monkeypatch.setattr("wordsmith.llm.generate_text", failing_generate_text)

    args = [
        "automatikmodus",
        "--title",
        "Fehler",
        "--content",
        "Hinweis",
        "--text-type",
        "Memo",
        "--word-count",
        "200",
        "--llm-provider",
        "ollama",
        "--ollama-model",
        "llama2",
        "--output-dir",
        str(output_dir),
        "--logs-dir",
        str(logs_dir),
    ]

    exit_code = main(args)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "konnte nicht abgeschlossen" in captured.err
    assert any(line.startswith("[FEHLER]") for line in captured.err.splitlines())
    runtime_match = re.search(r"Gesamtlaufzeit: ([0-9]+\.[0-9]{2}) Sekunden", captured.err)
    assert runtime_match
    runtime_seconds_cli = float(runtime_match.group(1))

    run_log = logs_dir / "run.log"
    assert run_log.exists()
    run_entries = [
        json.loads(line)
        for line in run_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all("timestamp" in entry for entry in run_entries)
    for entry in run_entries:
        datetime.fromisoformat(entry["timestamp"])
    assert any(entry["step"] == "error" and entry["status"] == "failed" for entry in run_entries)
    error_entry = next(entry for entry in run_entries if entry["step"] == "error")
    runtime_seconds_log = error_entry["data"]["runtime_seconds"]
    assert runtime_seconds_log >= 0
    assert runtime_seconds_cli == pytest.approx(runtime_seconds_log, rel=0.1, abs=0.1)

    llm_log = logs_dir / "llm.log"
    assert llm_log.exists()
    llm_entries = [
        json.loads(line)
        for line in llm_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert llm_entries
    assert "runtime_seconds" in llm_entries[0]
    assert llm_entries[0]["runtime_seconds"] == pytest.approx(runtime_seconds_log, rel=0.01, abs=0.01)


def test_iterations_argument_rejects_negative_value() -> None:
    args = [
        "automatikmodus",
        "--title",
        "Negativ",
        "--content",
        "Inhalt",
        "--text-type",
        "Blog",
        "--word-count",
        "200",
        "--iterations",
        "-1",
    ]

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 2


def test_invalid_register_value_causes_error() -> None:
    args = [
        "automatikmodus",
        "--title",
        "Test",
        "--content",
        "Inhalt",
        "--text-type",
        "Blog",
        "--word-count",
        "500",
        "--register",
        "freundschaftlich",
    ]

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 2


def test_invalid_variant_value_causes_error() -> None:
    args = [
        "automatikmodus",
        "--title",
        "Test",
        "--content",
        "Inhalt",
        "--text-type",
        "Blog",
        "--word-count",
        "500",
        "--variant",
        "de-lu",
    ]

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 2


def test_defaults_applied_for_missing_extended_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="llama2")],
    )

    responses = deque(
        [
            llm.LLMResult(
                text=json.dumps(
                    {
                        "messages": [],
                        "key_terms": [],
                    }
                )
            ),
            llm.LLMResult(text="- Hinweis"),
            llm.LLMResult(text="1. Abschnitt (Rolle: Hook, Wortbudget: 80 Wörter) -> Kontext."),
            llm.LLMResult(text="1. Abschnitt (Rolle: Hook, Wortbudget: 80 Wörter) -> Kontext."),
            llm.LLMResult(text="Der Text bleibt allgemein."),
            llm.LLMResult(text="Keine Abweichungen festgestellt."),
        ]
    )

    def fake_generate_text(**_: object) -> llm.LLMResult:
        return responses.popleft()

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    args = [
        "automatikmodus",
        "--title",
        "Default-Test",
        "--content",
        "Kurzer Hinweis.",
        "--text-type",
        "Blogartikel",
        "--word-count",
        "300",
        "--iterations",
        "0",
        "--audience",
        "   ",
        "--tone",
        "",
        "--register",
        "",
        "--variant",
        "  ",
        "--constraints",
        "\t",
        "--llm-provider",
        "ollama",
        "--ollama-model",
        "llama2",
        "--output-dir",
        str(output_dir),
        "--logs-dir",
        str(logs_dir),
    ]

    exit_code = main(args)

    assert exit_code == 0

    briefing = json.loads((output_dir / "briefing.json").read_text(encoding="utf-8"))
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))

    assert briefing["audience"] == DEFAULT_AUDIENCE
    assert briefing["tone"] == DEFAULT_TONE
    assert briefing["register"] == DEFAULT_REGISTER
    assert briefing["variant"] == DEFAULT_VARIANT
    assert briefing["constraints"] == DEFAULT_CONSTRAINTS

    assert metadata["audience"] == DEFAULT_AUDIENCE
    assert metadata["register"] == DEFAULT_REGISTER
    assert metadata["variant"] == DEFAULT_VARIANT

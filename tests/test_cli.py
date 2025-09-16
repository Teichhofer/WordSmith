import io
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cli import (
    DEFAULT_AUDIENCE,
    DEFAULT_CONSTRAINTS,
    DEFAULT_REGISTER,
    DEFAULT_TONE,
    DEFAULT_VARIANT,
    main,
)
from wordsmith import llm
from wordsmith import prompts
from wordsmith.config import DEFAULT_LLM_PROVIDER
from wordsmith.ollama import OllamaModel


def test_automatikmodus_requires_arguments():
    with pytest.raises(SystemExit) as exc:
        main(["automatikmodus"])
    assert exc.value.code == 2


def test_automatikmodus_runs_and_creates_outputs(tmp_path, capsys):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
    args = [
        "automatikmodus",
        "--title",
        "Strategische Roadmap",
        "--content",
        "Wir brauchen eine klare Roadmap für das nächste Quartal.",
        "--text-type",
        "Blogartikel",
        "--word-count",
        "600",
        "--iterations",
        "2",
        "--llm-provider",
        "provider-x",
        "--audience",
        "Marketing-Team",
        "--tone",
        "faktenbasiert",
        "--register",
        "Du",
        "--variant",
        "DE-AT",
        "--constraints",
        "Keine vertraulichen Zahlen nennen.",
        "--sources-allowed",
        "ja",
        "--seo-keywords",
        "roadmap, marketing",
        "--output-dir",
        str(output_dir),
        "--logs-dir",
        str(logs_dir),
    ]

    exit_code = main(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Strategische Roadmap" in captured.out

    idea_text = (output_dir / "idea.txt").read_text(encoding="utf-8")
    assert "Überarbeitete Idee" in idea_text
    assert "-" in idea_text
    assert "[COMPLIANCE-IDEA]" in idea_text
    assert "[ENTFERNT:" in idea_text

    outline_text = (output_dir / "outline.txt").read_text(encoding="utf-8")
    assert "Budget" in outline_text
    assert "Rolle" in outline_text
    assert "[COMPLIANCE-OUTLINE]" in outline_text

    current_text = (output_dir / "current_text.txt").read_text(encoding="utf-8")
    assert "## 1." in current_text
    assert "Strategische Roadmap" in current_text
    assert "[KENNZAHL]" in current_text
    assert "Nutze die Impulse" in current_text
    assert "[COMPLIANCE-PIPELINE]" in current_text
    assert "Quellen:\n- [Quelle: Freigabe steht aus]" in current_text

    assert (output_dir / "iteration_00.txt").exists()
    assert (output_dir / "iteration_01.txt").exists()
    assert (output_dir / "iteration_02.txt").exists()
    assert (output_dir / "iteration_03.txt").exists()

    assert (output_dir / "reflection_02.txt").exists()
    assert (output_dir / "reflection_03.txt").exists()

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["title"] == "Strategische Roadmap"
    assert metadata["sources_allowed"] is True
    assert metadata["system_prompt"] == prompts.SYSTEM_PROMPT
    assert metadata["rubric_passed"] is True
    assert metadata["llm_model"] is None
    assert metadata["compliance_checks"]

    briefing = json.loads((output_dir / "briefing.json").read_text(encoding="utf-8"))
    assert "seo_keywords" in briefing
    assert "roadmap" in briefing["seo_keywords"]
    assert briefing["key_terms"]
    assert "compliance" in briefing
    assert briefing["compliance"]["sources_mode"] == "zugelassen"

    run_entries = [
        json.loads(line)
        for line in (logs_dir / "run.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(entry["step"] == "briefing" for entry in run_entries)
    briefing_entry = next(entry for entry in run_entries if entry["step"] == "briefing")
    assert "briefing.json" in briefing_entry.get("artifacts", [])

    metadata_entry = next(entry for entry in run_entries if entry["step"] == "metadata")
    assert metadata_entry["data"]["rubric_passed"] is True
    assert "metadata.json" in metadata_entry.get("artifacts", [])

    revision_steps = {
        entry["step"] for entry in run_entries if entry["step"].startswith("revision_")
    }
    assert revision_steps == {"revision_01", "revision_02"}

    completion_entry = next(entry for entry in run_entries if entry["step"] == "complete")
    assert completion_entry["status"] == "succeeded"
    assert completion_entry["data"]["iterations"] == 2

    llm_entries = [
        json.loads(line)
        for line in (logs_dir / "llm.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert llm_entries
    llm_entry = llm_entries[0]
    assert llm_entry["stage"] == "pipeline"
    assert llm_entry["prompts"]["outline"] == prompts.OUTLINE_PROMPT.strip()
    assert llm_entry["events"][0]["step"] == "start"
    assert llm_entry.get("model") is None

    compliance_report = json.loads(
        (output_dir / "compliance.json").read_text(encoding="utf-8")
    )
    assert compliance_report["topic"] == "Strategische Roadmap"
    stages = {entry["stage"] for entry in compliance_report["checks"]}
    assert {"briefing", "idea", "outline", "draft"}.issubset(stages)
    assert any(stage.startswith("revision_") for stage in stages)
    draft_entry = next(
        entry for entry in compliance_report["checks"] if entry["stage"] == "draft"
    )
    assert "Quellenliste" in draft_entry["sources"]
    assert metadata["compliance_checks"] == compliance_report["checks"]


def test_invalid_sources_allowed_value_raises_help():
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
        "--sources-allowed",
        "vielleicht",
    ]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_invalid_register_value_causes_error():
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


def test_invalid_variant_value_causes_error():
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


def test_defaults_applied_for_missing_extended_arguments(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="mistral"), OllamaModel(name="llama2")],
    )
    def _fail_generate(**_: object) -> None:
        raise llm.LLMGenerationError("nicht verfügbar")

    monkeypatch.setattr("wordsmith.llm.generate_text", _fail_generate)
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
        "400",
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
        "--output-dir",
        str(output_dir),
        "--logs-dir",
        str(logs_dir),
    ]

    exit_code = main(args)
    assert exit_code == 0

    briefing = json.loads((output_dir / "briefing.json").read_text(encoding="utf-8"))
    assert briefing["audience"] == DEFAULT_AUDIENCE
    assert briefing["tone"] == DEFAULT_TONE
    assert briefing["register"] == DEFAULT_REGISTER
    assert briefing["variant"] == DEFAULT_VARIANT
    assert briefing["constraints"] == DEFAULT_CONSTRAINTS

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["audience"] == DEFAULT_AUDIENCE
    assert metadata["register"] == DEFAULT_REGISTER
    assert metadata["variant"] == DEFAULT_VARIANT
    assert metadata["keywords"] == []
    assert metadata["llm_provider"] == DEFAULT_LLM_PROVIDER
    assert metadata["llm_model"] == "mistral"
    assert metadata["compliance_checks"]

    current_text = (output_dir / "current_text.txt").read_text(encoding="utf-8")
    assert "[COMPLIANCE-PIPELINE]" in current_text
    assert "[KLÄREN: Quellenfreigabe ausstehend]" in current_text
    assert "Quellen:" not in current_text

    compliance_report = json.loads(
        (output_dir / "compliance.json").read_text(encoding="utf-8")
    )
    assert compliance_report["sources_allowed"] is False
    assert any("block" in entry["sources"] for entry in compliance_report["checks"])

    run_entries = [
        json.loads(line)
        for line in (logs_dir / "run.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    defaults_event = next(entry for entry in run_entries if entry["step"] == "input_defaults")
    assert "audience" in defaults_event["data"]["defaults"]


def test_ollama_model_argument_is_used(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="mistral"), OllamaModel(name="llama2")],
    )

    def _fail_generate(**_: object) -> None:
        raise llm.LLMGenerationError("nicht verfügbar")

    monkeypatch.setattr("wordsmith.llm.generate_text", _fail_generate)

    args = [
        "automatikmodus",
        "--title",
        "Ollama-Test",
        "--content",
        "Kurzer Hinweis.",
        "--text-type",
        "Blogartikel",
        "--word-count",
        "300",
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

    assert exit_code == 0
    assert "Verwende Ollama-Modell: llama2" in captured.out

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["llm_provider"] == "ollama"
    assert metadata["llm_model"] == "llama2"


def test_cli_uses_llm_text_when_generation_succeeds(tmp_path, monkeypatch, capsys):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="llama2")],
    )

    llm_calls: list[dict] = []
    llm_text = (
        "## 1. Einstieg (Hook)\n"
        "Der Beitrag rahmt das Thema und markiert offene Kennzahlen als [KLÄREN: Kennzahl].\n"
        "## 2. Vertiefung (Argument)\n"
        "Er erläutert die Roadmap, adressiert Prioritäten und zeigt nächste Schritte für das Team.\n"
        "## 3. Abschluss und CTA (CTA)\n"
        "Nutzen Sie die Impulse, um die Strategie im Alltag Ihres Teams zu verankern.\n"
    )

    def _success_generate(**kwargs):
        llm_calls.append(kwargs)
        return llm.LLMResult(text=llm_text)

    monkeypatch.setattr("wordsmith.llm.generate_text", _success_generate)

    args = [
        "automatikmodus",
        "--title",
        "LLM-Test",
        "--content",
        "Wir wollen echte LLM-Texte nutzen.",
        "--text-type",
        "Blogartikel",
        "--word-count",
        "360",
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

    assert exit_code == 0
    assert "## 1. Einstieg" in captured.out
    assert llm_calls and llm_calls[0]["model"] == "llama2"

    final_text = (output_dir / "current_text.txt").read_text(encoding="utf-8")
    assert "[COMPLIANCE-PIPELINE]" in final_text
    assert "## 1. Einstieg" in final_text
    assert "Nutzen Sie die Impulse" in final_text

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["llm_model"] == "llama2"

    llm_entries = [
        json.loads(line)
        for line in (logs_dir / "llm.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert llm_entries
    assert llm_entries[0]["llm_generation"]["status"] == "success"


def test_unknown_ollama_model_returns_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "wordsmith.ollama.OllamaClient.list_models",
        lambda self: [OllamaModel(name="mistral")],
    )

    args = [
        "automatikmodus",
        "--title",
        "Fehler",
        "--content",
        "Notizen",
        "--text-type",
        "Blog",
        "--word-count",
        "200",
        "--llm-provider",
        "ollama",
        "--ollama-model",
        "nicht-vorhanden",
        "--output-dir",
        str(tmp_path / "output"),
        "--logs-dir",
        str(tmp_path / "logs"),
    ]

    exit_code = main(args)

    assert exit_code == 2

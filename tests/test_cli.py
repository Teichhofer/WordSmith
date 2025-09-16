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
from wordsmith import prompts


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


def test_defaults_applied_for_missing_extended_arguments(tmp_path):
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
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

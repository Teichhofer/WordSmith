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

    current_text = (output_dir / "current_text.txt").read_text(encoding="utf-8")
    assert "Strategische Roadmap" in current_text
    assert "Systemprompt" in current_text

    iteration_file = output_dir / "iteration_02.txt"
    assert iteration_file.exists()

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["title"] == "Strategische Roadmap"
    assert metadata["sources_allowed"] is True
    assert metadata["system_prompt"] == prompts.SYSTEM_PROMPT

    briefing = json.loads((output_dir / "briefing.json").read_text(encoding="utf-8"))
    assert "seo_keywords" in briefing
    assert "roadmap" in briefing["seo_keywords"]

    assert (logs_dir / "run.log").exists()
    assert (logs_dir / "llm.log").exists()


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

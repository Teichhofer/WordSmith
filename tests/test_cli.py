import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cli import main
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

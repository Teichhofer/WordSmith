"""Tests for the predefined prompt templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import prompts


STAGE_NAMES = [
    "briefing",
    "idea_improvement",
    "outline",
    "outline_improvement",
    "section",
    "text_type_check",
    "text_type_fix",
    "revision",
    "reflection",
    "final_draft",
]


def test_prompt_templates_match_configuration() -> None:
    """Ensure all prompt templates match the external configuration file."""

    config_data = json.loads(
        prompts.DEFAULT_PROMPT_CONFIG_PATH.read_text(encoding="utf-8")
    )

    assert prompts.SYSTEM_PROMPT == config_data["system_prompt"]
    expected_stage_systems: dict[str, str] = {}
    for stage in STAGE_NAMES:
        prefix = stage.upper()
        assert getattr(prompts, f"{prefix}_PROMPT") == config_data[f"{stage}_prompt"]
        assert getattr(prompts, f"{prefix}_SYSTEM_PROMPT") == config_data[
            f"{stage}_system_prompt"
        ]
        expected_stage_systems[stage] = config_data[f"{stage}_system_prompt"]

    assert dict(prompts.STAGE_SYSTEM_PROMPTS) == expected_stage_systems
    assert (
        prompts.COMPLIANCE_HINT_INSTRUCTION
        == config_data["compliance_hint_instruction"]
    )

    assert prompts.build_revision_prompt() == prompts.REVISION_PROMPT.strip()
    assert (
        prompts.build_revision_prompt(include_compliance_hint=True)
        == prompts.REVISION_PROMPT.strip() + "\n" + prompts.COMPLIANCE_HINT_INSTRUCTION
    )


def test_load_prompt_config_respects_custom_system_prompt(tmp_path: Path) -> None:
    """Loading a new configuration keeps an explicitly set system prompt."""

    replacement_path = tmp_path / "prompts.json"
    config_data = json.loads(
        prompts.DEFAULT_PROMPT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    config_data["system_prompt"] = "Neuer Standard"
    replacement_path.write_text(
        json.dumps(config_data, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        prompts.set_system_prompt("Individueller Prompt")
        prompts.load_prompt_config(replacement_path)

        assert prompts.SYSTEM_PROMPT == "Individueller Prompt"
        assert all(
            value == "Individueller Prompt"
            for value in prompts.STAGE_SYSTEM_PROMPTS.values()
        )

        prompts.set_system_prompt(None)
        assert prompts.SYSTEM_PROMPT == "Neuer Standard"
        expected_stage_systems = {
            stage: config_data[f"{stage}_system_prompt"] for stage in STAGE_NAMES
        }
        assert dict(prompts.STAGE_SYSTEM_PROMPTS) == expected_stage_systems
    finally:
        prompts.load_prompt_config()


def test_set_system_prompt_for_specific_stage() -> None:
    """Individual stage prompts can be overridden without touching others."""

    prompts.set_system_prompt(None)
    original_system_prompt = prompts.SYSTEM_PROMPT
    original_stage_prompts = dict(prompts.STAGE_SYSTEM_PROMPTS)

    try:
        custom_value = "Outline Spezial"
        prompts.set_system_prompt(custom_value, stage="outline")

        assert prompts.STAGE_SYSTEM_PROMPTS["outline"] == custom_value
        assert prompts.SYSTEM_PROMPT == original_system_prompt
        for stage, value in original_stage_prompts.items():
            if stage == "outline":
                continue
            assert prompts.STAGE_SYSTEM_PROMPTS[stage] == value
    finally:
        prompts.set_system_prompt(None, stage="outline")

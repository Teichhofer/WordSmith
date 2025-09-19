"""Tests for the predefined prompt templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import prompts


def test_prompt_templates_match_configuration() -> None:
    """Ensure all prompt templates match the external configuration file."""

    config_data = json.loads(
        prompts.DEFAULT_PROMPT_CONFIG_PATH.read_text(encoding="utf-8")
    )

    assert prompts.SYSTEM_PROMPT == config_data["system_prompt"]
    assert prompts.BRIEFING_PROMPT == config_data["briefing_prompt"]
    assert prompts.IDEA_IMPROVEMENT_PROMPT == config_data["idea_improvement_prompt"]
    assert prompts.OUTLINE_PROMPT == config_data["outline_prompt"]
    assert (
        prompts.OUTLINE_IMPROVEMENT_PROMPT
        == config_data["outline_improvement_prompt"]
    )
    assert prompts.SECTION_PROMPT == config_data["section_prompt"]
    assert (
        prompts.TEXT_TYPE_CHECK_PROMPT
        == config_data["text_type_check_prompt"]
    )
    assert prompts.TEXT_TYPE_FIX_PROMPT == config_data["text_type_fix_prompt"]
    assert prompts.REVISION_PROMPT == config_data["revision_prompt"]
    assert (
        prompts.COMPLIANCE_HINT_INSTRUCTION
        == config_data["compliance_hint_instruction"]
    )
    assert prompts.REFLECTION_PROMPT == config_data["reflection_prompt"]
    assert prompts.FINAL_DRAFT_PROMPT == config_data["final_draft_prompt"]

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

        prompts.set_system_prompt(None)
        assert prompts.SYSTEM_PROMPT == "Neuer Standard"
    finally:
        prompts.load_prompt_config()

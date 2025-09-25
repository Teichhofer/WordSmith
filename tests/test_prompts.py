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
    assert (
        prompts.COMPLIANCE_HINT_INSTRUCTION
        == config_data["compliance_hint_instruction"]
    )

    stage_configs = config_data["stages"]
    expected_stage_systems: dict[str, str] = {}
    for stage in STAGE_NAMES:
        prefix = stage.upper()
        stage_data = stage_configs[stage]
        assert getattr(prompts, f"{prefix}_PROMPT") == stage_data["prompt"]
        assert getattr(prompts, f"{prefix}_SYSTEM_PROMPT") == stage_data[
            "system_prompt"
        ]
        expected_stage_systems[stage] = stage_data["system_prompt"]
        assert dict(prompts.STAGE_PROMPT_PARAMETERS[stage]) == stage_data[
            "parameters"
        ]

    assert dict(prompts.STAGE_SYSTEM_PROMPTS) == expected_stage_systems

    base_revision = prompts.build_revision_prompt(
        target_words=500,
        min_words=450,
        max_words=550,
    )
    assert "Wortkorridor: 450–550" in base_revision
    assert "{audience}" in base_revision
    assert "{text}" in base_revision
    compliance_instruction = prompts.COMPLIANCE_HINT_INSTRUCTION.strip()
    expected_with_hint = base_revision
    if compliance_instruction:
        expected_with_hint = base_revision + "\n" + compliance_instruction
    assert (
        prompts.build_revision_prompt(
            include_compliance_hint=True,
            target_words=500,
            min_words=450,
            max_words=550,
        )
        == expected_with_hint
    )

    sample_context = {
        "text": "Entwurf",
        "text_type": "Memo",
        "audience": "Team",
        "tone": "prägnant",
        "register": "Sie",
        "variant": "DE-DE",
        "constraints": "Keine zusätzlichen Vorgaben",
        "seo_keywords": "Test, Beispiel",
        "sources_mode": "Keine externen Quellen verwenden",
        "iteration": 2,
        "briefing": "{\n  \"goal\": \"Test\"\n}",
    }
    filled_revision = prompts.build_revision_prompt(
        target_words=500,
        min_words=450,
        max_words=550,
        context=sample_context,
    )
    assert "Team" in filled_revision
    assert "Iteration: 2" in filled_revision
    assert "Text zur Überarbeitung:\nEntwurf" in filled_revision

    improvement_text = "1. Einleitung schärfen (Absatz 1)"
    revision_with_guidance = prompts.build_revision_prompt(
        target_words=500,
        min_words=450,
        max_words=550,
        context=sample_context,
        improvement_suggestions=improvement_text,
    )
    assert prompts.REVISION_REFLECTION_HEADER in revision_with_guidance
    assert improvement_text in revision_with_guidance
    if compliance_instruction:
        revision_with_hint = prompts.build_revision_prompt(
            include_compliance_hint=True,
            target_words=500,
            min_words=450,
            max_words=550,
            context=sample_context,
            improvement_suggestions=improvement_text,
        )
        assert revision_with_hint.endswith(compliance_instruction)
        assert (
            revision_with_hint.index(prompts.REVISION_REFLECTION_HEADER)
            < revision_with_hint.rindex(compliance_instruction)
        )


def test_prompt_templates_emphasize_quality_controls() -> None:
    """The curated prompts must retain critical quality and safety guidance."""

    assert "| Abschnitt:" in prompts.COMPLIANCE_HINT_INSTRUCTION
    assert "[KLÄREN: …]" in prompts.BRIEFING_PROMPT
    assert "Ausgabeformat: genau ein Objekt" in prompts.BRIEFING_PROMPT
    assert "kein Markdown, keine Codeblöcke" in prompts.BRIEFING_PROMPT
    assert "dominierende Sprache der Eingaben" in prompts.BRIEFING_PROMPT
    assert "handlungsleitende Formulierungen" in prompts.BRIEFING_PROMPT
    assert "Antwortstruktur" in prompts.IDEA_IMPROVEMENT_PROMPT
    assert "[KLÄREN: …]" in prompts.IDEA_IMPROVEMENT_PROMPT
    assert "Unterliste" in prompts.OUTLINE_PROMPT
    assert "Stichpunkten" in prompts.OUTLINE_PROMPT
    assert "Übergang & Belege" in prompts.OUTLINE_PROMPT
    assert "Unterliste" in prompts.OUTLINE_IMPROVEMENT_PROMPT
    assert "Timinghinweise" in prompts.OUTLINE_IMPROVEMENT_PROMPT
    assert "Fundstelle" in prompts.TEXT_TYPE_CHECK_PROMPT
    assert "Stütze jede Bewertung" in prompts.TEXT_TYPE_CHECK_PROMPT
    assert "Zielwortzahl" in prompts.SECTION_PROMPT
    assert "Mindestlänge" in prompts.SECTION_PROMPT
    assert "Stil:" in prompts.SECTION_PROMPT
    assert "Qualitätscheck" in prompts.SECTION_PROMPT
    assert "unverkennbar dem im Briefing definierten Texttyp" in prompts.SECTION_PROMPT
    assert "Verknüpfe sichtbar" in prompts.SECTION_PROMPT
    revision_template = prompts.REVISION_PROMPT.strip()
    assert "Überarbeite den folgenden" in revision_template
    assert "Halte Format" in revision_template
    assert "dichte Übergänge" in revision_template
    assert "WICHTIG: Gib ausschließlich den überarbeiteten Text zurück" in revision_template
    assert "Poliere" in prompts.REVISION_SYSTEM_PROMPT
    assert "Markdown" in prompts.REVISION_SYSTEM_PROMPT
    assert "Fassung" in prompts.REVISION_SYSTEM_PROMPT
    final_template = prompts.FINAL_DRAFT_PROMPT
    assert "Titel: {title}" in final_template
    assert "Outline:\n{outline}" in final_template
    assert "Stil: {style}" in final_template
    assert "Zielwortzahl: {target_words}" in final_template
    assert "{format_instruction}" in final_template
    assert "konkrete Handlungen" in prompts.REFLECTION_PROMPT
    assert (
        "WICHTIG: Gib ausschließlich den aktualisierten Text zurück"
        in prompts.TEXT_TYPE_FIX_PROMPT
    )


def test_format_prompt_preserves_double_braced_tokens() -> None:
    """Formatting must keep double-braced placeholders intact for the LLM."""

    template = "Abschnitt {{nummer}}: {title} – {{Titel}}"
    result = prompts.format_prompt(template, title="Einleitung")

    assert "Abschnitt {{nummer}}" in result
    assert "– {{Titel}}" in result
    assert "Einleitung" in result


def test_build_final_draft_prompt_removes_meta_guidance() -> None:
    """The final draft prompt collapses to the requested minimalist form."""

    outline = (
        "1. Auftakt (Rolle: Hook, Budget: 200 Wörter) -> Setup\n"
        "    - Fokus: Spannung\n"
        "2. Finale (Rolle: Abschluss, Budget: 180 Wörter)"
    )
    prompt_text = prompts.buildFinalDraftPrompt(
        title="Erfolgsgeschichte",
        outline=outline,
        style="Ton: inspirierend; Register: Du",
        targetWords=500,
    )

    assert prompt_text.startswith("Titel: Erfolgsgeschichte")
    assert "Outline:\n1. Auftakt" in prompt_text
    assert "Rolle" not in prompt_text
    assert "Budget" not in prompt_text
    assert "->" not in prompt_text
    assert "Stil: Ton: inspirierend; Register: Du" in prompt_text
    assert "Zielwortzahl: 500" in prompt_text
    assert prompt_text.endswith("Gib nur den Fließtext zurück.")


def test_build_final_draft_prompt_accepts_custom_output_format() -> None:
    """Custom output instructions can replace the default text-only hint."""

    prompt_text = prompts.buildFinalDraftPrompt(
        title="Whitepaper",
        outline="1. Einleitung",
        style="Ton: sachlich",
        targetWords=1200,
        output_format="Bitte als Markdown mit Überschriften liefern.",
    )

    assert prompt_text.endswith("Bitte als Markdown mit Überschriften liefern.")
    assert "Gib nur den Fließtext zurück." not in prompt_text


def test_prompt_configuration_has_no_merge_markers() -> None:
    """The distributed prompt configuration must be valid JSON without conflict markers."""

    text = prompts.DEFAULT_PROMPT_CONFIG_PATH.read_text(encoding="utf-8")
    for marker in ("<<<<<<<", "=======", ">>>>>>>"):
        assert marker not in text


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
        original_stage_prompts = dict(prompts.STAGE_SYSTEM_PROMPTS)

        prompts.set_system_prompt("Individueller Prompt")
        prompts.load_prompt_config(replacement_path)

        assert prompts.SYSTEM_PROMPT == "Individueller Prompt"
        assert dict(prompts.STAGE_SYSTEM_PROMPTS) == original_stage_prompts

        prompts.set_system_prompt(None)
        assert prompts.SYSTEM_PROMPT == "Neuer Standard"
        expected_stage_systems = {
            stage: config_data["stages"][stage]["system_prompt"]
            for stage in STAGE_NAMES
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


def test_set_system_prompt_does_not_override_stage_prompts() -> None:
    """A global system prompt override keeps the stage-specific prompts intact."""

    prompts.set_system_prompt(None)
    original_stage_prompts = dict(prompts.STAGE_SYSTEM_PROMPTS)

    try:
        prompts.set_system_prompt("Global Override")
        assert dict(prompts.STAGE_SYSTEM_PROMPTS) == original_stage_prompts
    finally:
        prompts.set_system_prompt(None)

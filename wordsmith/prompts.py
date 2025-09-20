"""Prompt templates used by WriterAgent."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Mapping


class PromptConfigurationError(RuntimeError):
    """Raised when the prompt configuration cannot be loaded."""


DEFAULT_PROMPT_CONFIG_PATH = Path(__file__).with_name("prompts_config.json")
_STAGE_PROMPT_ORDER: tuple[tuple[str, str], ...] = (
    ("briefing", "BRIEFING"),
    ("idea_improvement", "IDEA_IMPROVEMENT"),
    ("outline", "OUTLINE"),
    ("outline_improvement", "OUTLINE_IMPROVEMENT"),
    ("section", "SECTION"),
    ("text_type_check", "TEXT_TYPE_CHECK"),
    ("text_type_fix", "TEXT_TYPE_FIX"),
    ("revision", "REVISION"),
    ("reflection", "REFLECTION"),
    ("final_draft", "FINAL_DRAFT"),
)
_STAGE_PREFIXES: Dict[str, str] = {stage: prefix for stage, prefix in _STAGE_PROMPT_ORDER}
_PROMPT_KEYS: tuple[str, ...] = (
    "system_prompt",
    *(
        key
        for stage, _ in _STAGE_PROMPT_ORDER
        for key in (f"{stage}_system_prompt", f"{stage}_prompt")
    ),
    "compliance_hint_instruction",
)

_DEFAULT_SYSTEM_PROMPT: str = ""
_DEFAULT_STAGE_SYSTEM_PROMPTS: Dict[str, str] = {
    stage: "" for stage, _ in _STAGE_PROMPT_ORDER
}
SYSTEM_PROMPT: str = ""
_STAGE_SYSTEM_PROMPTS: Dict[str, str] = {
    stage: "" for stage, _ in _STAGE_PROMPT_ORDER
}
STAGE_SYSTEM_PROMPTS: Mapping[str, str] = MappingProxyType(_STAGE_SYSTEM_PROMPTS)
DEFAULT_STAGE_SYSTEM_PROMPTS: Mapping[str, str] = MappingProxyType(
    _DEFAULT_STAGE_SYSTEM_PROMPTS
)

BRIEFING_PROMPT: str = ""
IDEA_IMPROVEMENT_PROMPT: str = ""
OUTLINE_PROMPT: str = ""
OUTLINE_IMPROVEMENT_PROMPT: str = ""
SECTION_PROMPT: str = ""
TEXT_TYPE_CHECK_PROMPT: str = ""
TEXT_TYPE_FIX_PROMPT: str = ""
REVISION_PROMPT: str = ""
REFLECTION_PROMPT: str = ""
FINAL_DRAFT_PROMPT: str = ""
BRIEFING_SYSTEM_PROMPT: str = ""
IDEA_IMPROVEMENT_SYSTEM_PROMPT: str = ""
OUTLINE_SYSTEM_PROMPT: str = ""
OUTLINE_IMPROVEMENT_SYSTEM_PROMPT: str = ""
SECTION_SYSTEM_PROMPT: str = ""
TEXT_TYPE_CHECK_SYSTEM_PROMPT: str = ""
TEXT_TYPE_FIX_SYSTEM_PROMPT: str = ""
REVISION_SYSTEM_PROMPT: str = ""
REFLECTION_SYSTEM_PROMPT: str = ""
FINAL_DRAFT_SYSTEM_PROMPT: str = ""
COMPLIANCE_HINT_INSTRUCTION: str = ""


def _read_prompt_config(path: Path) -> Dict[str, str]:
    """Load and validate the prompt configuration from ``path``."""

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise PromptConfigurationError(
            f"Prompt-Konfigurationsdatei '{path}' wurde nicht gefunden."
        ) from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise PromptConfigurationError(
            f"Prompt-Konfiguration konnte nicht gelesen werden: {exc}"
        ) from exc

    if not isinstance(raw_data, dict):
        raise PromptConfigurationError("Prompt-Konfiguration muss ein JSON-Objekt sein.")

    missing_keys = [key for key in _PROMPT_KEYS if key not in raw_data]
    if missing_keys:
        formatted = ", ".join(sorted(missing_keys))
        raise PromptConfigurationError(
            f"Prompt-Konfiguration unvollständig. Fehlende Schlüssel: {formatted}."
        )

    validated: Dict[str, str] = {}
    for key in _PROMPT_KEYS:
        value = raw_data[key]
        if not isinstance(value, str):
            raise PromptConfigurationError(
                f"Prompt '{key}' muss als String definiert sein."
            )
        validated[key] = value

    return validated


def _apply_prompt_values(values: Dict[str, str]) -> None:
    """Update module level prompt strings with ``values``."""

    global _DEFAULT_SYSTEM_PROMPT
    global SYSTEM_PROMPT
    global COMPLIANCE_HINT_INSTRUCTION

    previous_default = _DEFAULT_SYSTEM_PROMPT
    previous_system_prompt = SYSTEM_PROMPT or previous_default

    _DEFAULT_SYSTEM_PROMPT = values["system_prompt"]

    # Preserve a customised system prompt but update when defaults were used.
    if previous_system_prompt == previous_default or not previous_system_prompt:
        SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
    else:
        SYSTEM_PROMPT = previous_system_prompt

    for stage, prefix in _STAGE_PROMPT_ORDER:
        prompt_key = f"{stage}_prompt"
        system_key = f"{stage}_system_prompt"

        globals()[f"{prefix}_PROMPT"] = values[prompt_key]

        previous_stage_default = _DEFAULT_STAGE_SYSTEM_PROMPTS[stage]
        previous_stage_value = _STAGE_SYSTEM_PROMPTS[stage] or previous_stage_default

        new_stage_default = values[system_key]
        _DEFAULT_STAGE_SYSTEM_PROMPTS[stage] = new_stage_default

        if previous_stage_value == previous_stage_default or not previous_stage_value:
            _STAGE_SYSTEM_PROMPTS[stage] = new_stage_default

        globals()[f"{prefix}_SYSTEM_PROMPT"] = _STAGE_SYSTEM_PROMPTS[stage]

    COMPLIANCE_HINT_INSTRUCTION = values["compliance_hint_instruction"]


def load_prompt_config(path: str | Path | None = None) -> None:
    """Load prompt templates from ``path`` and update module globals."""

    config_path = Path(path) if path is not None else DEFAULT_PROMPT_CONFIG_PATH
    values = _read_prompt_config(config_path)
    _apply_prompt_values(values)


def set_system_prompt(prompt: str | None, *, stage: str | None = None) -> None:
    """Configure system prompts for subsequent LLM interactions.

    When ``stage`` is ``None`` all stage-specific system prompts are updated.
    Otherwise only the named stage (e.g. ``"briefing"``) is changed.
    """

    global SYSTEM_PROMPT

    if stage is not None:
        if stage not in _STAGE_PREFIXES:
            raise ValueError(f"Unbekannte Prompt-Stufe: {stage}")
        if prompt is None:
            new_value = _DEFAULT_STAGE_SYSTEM_PROMPTS[stage]
        else:
            cleaned_stage = str(prompt).strip()
            new_value = cleaned_stage or _DEFAULT_STAGE_SYSTEM_PROMPTS[stage]
        _STAGE_SYSTEM_PROMPTS[stage] = new_value
        globals()[f"{_STAGE_PREFIXES[stage]}_SYSTEM_PROMPT"] = new_value
        return

    if prompt is None:
        SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
        for stage_name, prefix in _STAGE_PROMPT_ORDER:
            _STAGE_SYSTEM_PROMPTS[stage_name] = _DEFAULT_STAGE_SYSTEM_PROMPTS[stage_name]
            globals()[f"{prefix}_SYSTEM_PROMPT"] = _STAGE_SYSTEM_PROMPTS[stage_name]
        return

    cleaned = str(prompt).strip()
    value = cleaned or _DEFAULT_SYSTEM_PROMPT
    SYSTEM_PROMPT = value


def build_revision_prompt(
    include_compliance_hint: bool = False,
    *,
    target_words: int,
    min_words: int,
    max_words: int,
) -> str:
    """Return the revision prompt, optionally with the compliance hint appended."""

    prompt = REVISION_PROMPT.strip().format(
        ziel_woerter=target_words,
        min_woerter=min_words,
        max_woerter=max_words,
    )
    if include_compliance_hint:
        return f"{prompt}\n{COMPLIANCE_HINT_INSTRUCTION}"
    return prompt


# Load prompt templates immediately so the module exposes populated constants.
load_prompt_config()

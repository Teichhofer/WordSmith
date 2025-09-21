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
_TOP_LEVEL_REQUIRED_KEYS: tuple[str, ...] = (
    "system_prompt",
    "compliance_hint_instruction",
    "stages",
)
_STAGE_VALUE_REQUIRED_KEYS: tuple[str, ...] = (
    "system_prompt",
    "prompt",
    "parameters",
)
_REQUIRED_PARAMETER_FIELDS: tuple[str, ...] = (
    "temperature",
    "top_p",
    "presence_penalty",
    "frequency_penalty",
)
_ALLOWED_PARAMETER_FIELDS: frozenset[str] = frozenset(
    (*_REQUIRED_PARAMETER_FIELDS, "num_predict")
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

_DEFAULT_STAGE_PARAMETERS: Dict[str, Dict[str, float]] = {
    stage: {} for stage, _ in _STAGE_PROMPT_ORDER
}
_STAGE_PARAMETERS: Dict[str, Dict[str, float]] = {
    stage: {} for stage, _ in _STAGE_PROMPT_ORDER
}
DEFAULT_STAGE_PROMPT_PARAMETERS: Mapping[str, Mapping[str, float]] = MappingProxyType(
    _DEFAULT_STAGE_PARAMETERS
)
STAGE_PROMPT_PARAMETERS: Mapping[str, Mapping[str, float]] = MappingProxyType(
    _STAGE_PARAMETERS
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


def _read_prompt_config(
    path: Path,
) -> tuple[
    Dict[str, str],
    Dict[str, Dict[str, str]],
    Dict[str, Dict[str, float]],
]:
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

    missing_keys = [key for key in _TOP_LEVEL_REQUIRED_KEYS if key not in raw_data]
    if missing_keys:
        formatted = ", ".join(sorted(missing_keys))
        raise PromptConfigurationError(
            f"Prompt-Konfiguration unvollständig. Fehlende Schlüssel: {formatted}."
        )

    for key in ("system_prompt", "compliance_hint_instruction"):
        if not isinstance(raw_data[key], str):
            raise PromptConfigurationError(
                f"Prompt '{key}' muss als String definiert sein."
            )

    stages_value = raw_data["stages"]
    if not isinstance(stages_value, dict):
        raise PromptConfigurationError("'stages' muss ein Objekt sein.")

    known_stages = {stage for stage, _ in _STAGE_PROMPT_ORDER}
    unknown_stages = sorted(set(stages_value) - known_stages)
    if unknown_stages:
        formatted = ", ".join(unknown_stages)
        raise PromptConfigurationError(
            f"Unbekannte Prompt-Stufen in der Konfiguration: {formatted}."
        )

    missing_stage_entries = sorted(known_stages - set(stages_value))
    if missing_stage_entries:
        formatted = ", ".join(missing_stage_entries)
        raise PromptConfigurationError(
            f"Prompt-Konfiguration unvollständig. Fehlende Stufen: {formatted}."
        )

    global_strings: Dict[str, str] = {
        "system_prompt": raw_data["system_prompt"],
        "compliance_hint_instruction": raw_data["compliance_hint_instruction"],
    }

    stage_prompts: Dict[str, Dict[str, str]] = {}
    stage_parameters: Dict[str, Dict[str, float]] = {}
    for stage, _ in _STAGE_PROMPT_ORDER:
        stage_config = stages_value[stage]
        if not isinstance(stage_config, dict):
            raise PromptConfigurationError(
                f"Konfiguration für '{stage}' muss ein Objekt sein."
            )

        missing_stage_keys = [
            key for key in _STAGE_VALUE_REQUIRED_KEYS if key not in stage_config
        ]
        if missing_stage_keys:
            formatted = ", ".join(sorted(missing_stage_keys))
            raise PromptConfigurationError(
                f"Konfiguration für '{stage}' fehlt: {formatted}."
            )

        stage_prompt = stage_config["prompt"]
        stage_system_prompt = stage_config["system_prompt"]

        if not isinstance(stage_prompt, str):
            raise PromptConfigurationError(
                f"Prompt für '{stage}' muss als String definiert sein."
            )
        if not isinstance(stage_system_prompt, str):
            raise PromptConfigurationError(
                f"System-Prompt für '{stage}' muss als String definiert sein."
            )

        stage_prompts[stage] = {
            "prompt": stage_prompt,
            "system_prompt": stage_system_prompt,
        }

        parameter_value = stage_config["parameters"]
        if not isinstance(parameter_value, dict):
            raise PromptConfigurationError(
                f"Parameter für '{stage}' müssen als Objekt definiert sein."
            )
        missing_fields = [
            field for field in _REQUIRED_PARAMETER_FIELDS if field not in parameter_value
        ]
        if missing_fields:
            formatted = ", ".join(sorted(missing_fields))
            raise PromptConfigurationError(
                f"Parameter für '{stage}' fehlen folgende Felder: {formatted}."
            )
        cleaned_parameters: Dict[str, float] = {}
        for field, raw_value in parameter_value.items():
            if field not in _ALLOWED_PARAMETER_FIELDS:
                raise PromptConfigurationError(
                    f"Unbekannter Parameter '{field}' für Prompt '{stage}'."
                )
            if field == "num_predict":
                cleaned_parameters[field] = float(int(raw_value))
            else:
                cleaned_parameters[field] = float(raw_value)
        stage_parameters[stage] = cleaned_parameters

    return global_strings, stage_prompts, stage_parameters


def _apply_prompt_values(
    global_strings: Dict[str, str],
    stage_values: Dict[str, Dict[str, str]],
    parameters: Dict[str, Dict[str, float]],
) -> None:
    """Update module level prompt strings with ``values``."""

    global _DEFAULT_SYSTEM_PROMPT
    global SYSTEM_PROMPT
    global COMPLIANCE_HINT_INSTRUCTION

    previous_default = _DEFAULT_SYSTEM_PROMPT
    previous_system_prompt = SYSTEM_PROMPT or previous_default

    _DEFAULT_SYSTEM_PROMPT = global_strings["system_prompt"]

    # Preserve a customised system prompt but update when defaults were used.
    if previous_system_prompt == previous_default or not previous_system_prompt:
        SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
    else:
        SYSTEM_PROMPT = previous_system_prompt

    for stage, prefix in _STAGE_PROMPT_ORDER:
        globals()[f"{prefix}_PROMPT"] = stage_values[stage]["prompt"]

        previous_stage_default = _DEFAULT_STAGE_SYSTEM_PROMPTS[stage]
        previous_stage_value = _STAGE_SYSTEM_PROMPTS[stage] or previous_stage_default

        new_stage_default = stage_values[stage]["system_prompt"]
        _DEFAULT_STAGE_SYSTEM_PROMPTS[stage] = new_stage_default

        if previous_stage_value == previous_stage_default or not previous_stage_value:
            _STAGE_SYSTEM_PROMPTS[stage] = new_stage_default

        globals()[f"{prefix}_SYSTEM_PROMPT"] = _STAGE_SYSTEM_PROMPTS[stage]

        new_parameters = dict(parameters.get(stage, {}))
        _DEFAULT_STAGE_PARAMETERS[stage] = dict(new_parameters)
        _STAGE_PARAMETERS[stage] = new_parameters

    COMPLIANCE_HINT_INSTRUCTION = global_strings["compliance_hint_instruction"]


def load_prompt_config(path: str | Path | None = None) -> None:
    """Load prompt templates from ``path`` and update module globals."""

    config_path = Path(path) if path is not None else DEFAULT_PROMPT_CONFIG_PATH
    global_values, stage_values, parameter_values = _read_prompt_config(config_path)
    _apply_prompt_values(global_values, stage_values, parameter_values)


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

    prompt = REVISION_PROMPT.strip()
    if not include_compliance_hint:
        return prompt

    compliance_hint = COMPLIANCE_HINT_INSTRUCTION.strip()
    if not compliance_hint:
        return prompt

    if prompt:
        return f"{prompt}\n{compliance_hint}"
    return compliance_hint


# Load prompt templates immediately so the module exposes populated constants.
load_prompt_config()

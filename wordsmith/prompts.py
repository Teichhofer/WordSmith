"""Prompt templates used by WriterAgent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class PromptConfigurationError(RuntimeError):
    """Raised when the prompt configuration cannot be loaded."""


DEFAULT_PROMPT_CONFIG_PATH = Path(__file__).with_name("prompts_config.json")
_PROMPT_KEYS: tuple[str, ...] = (
    "system_prompt",
    "briefing_prompt",
    "idea_improvement_prompt",
    "outline_prompt",
    "outline_improvement_prompt",
    "section_prompt",
    "text_type_check_prompt",
    "text_type_fix_prompt",
    "revision_prompt",
    "compliance_hint_instruction",
    "reflection_prompt",
    "final_draft_prompt",
)

_DEFAULT_SYSTEM_PROMPT: str = ""
SYSTEM_PROMPT: str = ""
BRIEFING_PROMPT: str = ""
IDEA_IMPROVEMENT_PROMPT: str = ""
OUTLINE_PROMPT: str = ""
OUTLINE_IMPROVEMENT_PROMPT: str = ""
SECTION_PROMPT: str = ""
TEXT_TYPE_CHECK_PROMPT: str = ""
TEXT_TYPE_FIX_PROMPT: str = ""
REVISION_PROMPT: str = ""
COMPLIANCE_HINT_INSTRUCTION: str = ""
REFLECTION_PROMPT: str = ""
FINAL_DRAFT_PROMPT: str = ""


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
    global BRIEFING_PROMPT
    global IDEA_IMPROVEMENT_PROMPT
    global OUTLINE_PROMPT
    global OUTLINE_IMPROVEMENT_PROMPT
    global SECTION_PROMPT
    global TEXT_TYPE_CHECK_PROMPT
    global TEXT_TYPE_FIX_PROMPT
    global REVISION_PROMPT
    global COMPLIANCE_HINT_INSTRUCTION
    global REFLECTION_PROMPT
    global FINAL_DRAFT_PROMPT

    previous_default = _DEFAULT_SYSTEM_PROMPT
    previous_system_prompt = SYSTEM_PROMPT or previous_default

    _DEFAULT_SYSTEM_PROMPT = values["system_prompt"]

    # Preserve a customised system prompt but update when defaults were used.
    if previous_system_prompt == previous_default or not previous_system_prompt:
        SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
    else:
        SYSTEM_PROMPT = previous_system_prompt

    BRIEFING_PROMPT = values["briefing_prompt"]
    IDEA_IMPROVEMENT_PROMPT = values["idea_improvement_prompt"]
    OUTLINE_PROMPT = values["outline_prompt"]
    OUTLINE_IMPROVEMENT_PROMPT = values["outline_improvement_prompt"]
    SECTION_PROMPT = values["section_prompt"]
    TEXT_TYPE_CHECK_PROMPT = values["text_type_check_prompt"]
    TEXT_TYPE_FIX_PROMPT = values["text_type_fix_prompt"]
    REVISION_PROMPT = values["revision_prompt"]
    COMPLIANCE_HINT_INSTRUCTION = values["compliance_hint_instruction"]
    REFLECTION_PROMPT = values["reflection_prompt"]
    FINAL_DRAFT_PROMPT = values["final_draft_prompt"]


def load_prompt_config(path: str | Path | None = None) -> None:
    """Load prompt templates from ``path`` and update module globals."""

    config_path = Path(path) if path is not None else DEFAULT_PROMPT_CONFIG_PATH
    values = _read_prompt_config(config_path)
    _apply_prompt_values(values)


def set_system_prompt(prompt: str | None) -> None:
    """Configure the system prompt for subsequent LLM interactions."""

    global SYSTEM_PROMPT

    if prompt is None:
        SYSTEM_PROMPT = _DEFAULT_SYSTEM_PROMPT
        return

    cleaned = str(prompt).strip()
    SYSTEM_PROMPT = cleaned or _DEFAULT_SYSTEM_PROMPT


def build_revision_prompt(include_compliance_hint: bool = False) -> str:
    """Return the revision prompt, optionally with the compliance hint appended."""

    prompt = REVISION_PROMPT.strip()
    if include_compliance_hint:
        return f"{prompt}\n{COMPLIANCE_HINT_INSTRUCTION}"
    return prompt


# Load prompt templates immediately so the module exposes populated constants.
load_prompt_config()

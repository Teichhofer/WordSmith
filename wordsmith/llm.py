from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import LLMParameters


@dataclass
class LLMResult:
    """Container for the generated text and optional metadata."""

    text: str
    raw: Optional[Dict[str, Any]] = None


class LLMGenerationError(RuntimeError):
    """Raised when the configured LLM provider cannot generate text."""


def _prepare_options(parameters: LLMParameters) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "temperature": parameters.temperature,
        "top_p": parameters.top_p,
        "presence_penalty": parameters.presence_penalty,
        "frequency_penalty": parameters.frequency_penalty,
    }
    if getattr(parameters, "seed", None) is not None:
        options["seed"] = parameters.seed
    return options


def generate_text(
    *,
    provider: str,
    model: Optional[str],
    prompt: str,
    system_prompt: str,
    parameters: LLMParameters,
    base_url: Optional[str] = None,
) -> LLMResult:
    """Generate text using the configured provider.

    Currently only Ollama is supported. The function performs a blocking HTTP
    call and returns the full response text. Callers are expected to handle
    :class:`LLMGenerationError` to provide fallbacks.
    """

    provider_normalised = provider.strip().lower()
    if provider_normalised == "ollama":
        if not model:
            raise LLMGenerationError("Kein Ollama-Modell ausgewählt.")
        return _generate_with_ollama(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            parameters=parameters,
            base_url=base_url,
        )

    raise LLMGenerationError(
        f"LLM-Anbieter '{provider}' wird derzeit nicht unterstützt."
    )


def _generate_with_ollama(
    *,
    model: str,
    prompt: str,
    system_prompt: str,
    parameters: LLMParameters,
    base_url: Optional[str],
) -> LLMResult:
    """Call the Ollama `/api/generate` endpoint and return the response."""

    url = (base_url or "http://localhost:11434").rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": _prepare_options(parameters),
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network failure branch
        raise LLMGenerationError(
            f"Ollama konnte nicht erreicht werden: {exc}"
        ) from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMGenerationError(
            "Antwort der Ollama-API konnte nicht interpretiert werden."
        ) from exc

    text = payload.get("response")
    if not isinstance(text, str) or not text.strip():
        raise LLMGenerationError("Ollama-API lieferte keinen Text zurück.")

    return LLMResult(text=text.strip(), raw=payload)

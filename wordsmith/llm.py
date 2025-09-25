from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from .config import LLMParameters, OLLAMA_TIMEOUT_SECONDS


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
    if getattr(parameters, "num_predict", None) is not None:
        options["num_predict"] = int(parameters.num_predict)
    stop_sequences = getattr(parameters, "stop", ())
    if stop_sequences is None:
        options["stop"] = []
    elif isinstance(stop_sequences, str):
        cleaned = stop_sequences.strip()
        options["stop"] = [cleaned] if cleaned else []
    else:
        options["stop"] = [
            str(entry).strip()
            for entry in stop_sequences
            if str(entry).strip()
        ]
    return options


def _normalise_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the Ollama payload without bulky token data."""

    cleaned = dict(payload)
    context = cleaned.get("context")
    if isinstance(context, list):
        cleaned["context_token_count"] = len(context)
        cleaned.pop("context", None)
    return cleaned


def _extract_response_fragment(payload: Mapping[str, Any]) -> str:
    """Return textual content from an Ollama response payload."""

    response = payload.get("response")
    if isinstance(response, str):
        return response

    message = payload.get("message")
    if isinstance(message, Mapping):
        content = message.get("content")
        if isinstance(content, str):
            return content

    messages = payload.get("messages")
    if isinstance(messages, Sequence):
        fragments: list[str] = []
        for entry in messages:
            if not isinstance(entry, Mapping):
                continue
            content = entry.get("content")
            if isinstance(content, str):
                fragments.append(content)
        if fragments:
            return "".join(fragments)

    return ""


def _parse_ollama_response(text: str) -> tuple[str, Dict[str, Any]]:
    """Parse a (potentially streamed) Ollama response into text and metadata."""

    payloads: list[Dict[str, Any]] = []

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
        if not payloads:
            raise ValueError("Kein gültiges JSON im Ollama-Response gefunden.")
    else:
        if isinstance(payload, dict):
            payloads.append(payload)
        else:
            raise ValueError("Ollama-Response hat kein JSON-Objekt geliefert.")

    fragments = [
        fragment
        for fragment in (_extract_response_fragment(payload) for payload in payloads)
        if fragment
    ]

    combined_text = "".join(fragments).strip()
    last_payload = payloads[-1]

    if not combined_text:
        combined_text = _extract_response_fragment(last_payload).strip()

    if not combined_text:
        raise ValueError("Ollama-API lieferte keinen Text zurück.")

    raw_payload = _normalise_payload(last_payload)
    if len(fragments) > 1:
        raw_payload["response_fragments"] = fragments

    return combined_text, raw_payload


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
        # Start every request with an empty context to avoid reusing previous
        # conversations that Ollama might keep around implicitly.
        "context": [],
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
        with urllib.request.urlopen(
            request, timeout=OLLAMA_TIMEOUT_SECONDS
        ) as response:
            body = response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network failure branch
        raise LLMGenerationError(
            f"Ollama konnte nicht erreicht werden: {exc}"
        ) from exc

    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LLMGenerationError(
            "Antwort der Ollama-API konnte nicht interpretiert werden."
        ) from exc

    try:
        text, raw_payload = _parse_ollama_response(decoded)
    except ValueError as exc:
        raise LLMGenerationError(
            "Antwort der Ollama-API konnte nicht interpretiert werden."
        ) from exc

    return LLMResult(text=text, raw=raw_payload)

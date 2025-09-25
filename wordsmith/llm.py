from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from .config import LLMParameters, OLLAMA_TIMEOUT_SECONDS


_LOGGER = logging.getLogger(__name__)
_PLACEHOLDER_PATTERN = re.compile(r"(?<!{){([^{}]+)}(?!})")
# Only treat lowercase placeholder tokens as unresolved template fields.
#
# Promptvorlagen nutzen konsequent ``snake_case``-Platzhalter (z. B.
# ``{target_words}``). Anwendertexte oder LLM-Antworten können jedoch
# geschweifte Klammern mit Eigennamen wie ``{Name}`` enthalten. Die
# ursprüngliche Prüfung hat solche Inhalte fälschlich als nicht
# ersetzte Platzhalter interpretiert und dadurch weitere Iterationen
# blockiert. Wir beschränken den regulären Ausdruck deshalb auf
# Kleinbuchstaben sowie die bekannten Trenner. Dadurch bleibt die
# Validierung für reale Prompt-Platzhalter bestehen, während reguläre
# Texte mit ``{Name}`` oder ``{Titel}`` nicht mehr beanstandet werden.
_PLACEHOLDER_NAME_PATTERN = re.compile(r"[a-z0-9_.-]+$")


@dataclass
class LLMResult:
    """Container for the generated text and optional metadata."""

    text: str
    raw: Optional[Dict[str, Any]] = None


class LLMGenerationError(RuntimeError):
    """Raised when the configured LLM provider cannot generate text."""


def _hash_payload(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for logging failed payloads."""

    serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _sanitise_payload(payload: Mapping[str, Any]) -> None:
    """Ensure the payload does not contain unresolved placeholders."""

    unresolved: list[tuple[str, str]] = []

    def _check(value: Any, path: str) -> None:
        if isinstance(value, str):
            for match in _PLACEHOLDER_PATTERN.finditer(value):
                placeholder = match.group(1).strip()
                if placeholder and _PLACEHOLDER_NAME_PATTERN.fullmatch(placeholder):
                    unresolved.append((path or "<root>", placeholder))
            return
        if isinstance(value, Mapping):
            for key, nested in value.items():
                new_path = f"{path}.{key}" if path else str(key)
                _check(nested, new_path)
            return
        if isinstance(value, Sequence) and not isinstance(
            value, (bytes, bytearray)
        ):
            for index, item in enumerate(value):
                new_path = f"{path}[{index}]" if path else f"[{index}]"
                _check(item, new_path)

    _check(payload, "")

    if not unresolved:
        return

    payload_hash = _hash_payload(payload)
    details = []
    for context, placeholder in unresolved:
        details.append(f"{context} -> {placeholder}")
        _LOGGER.error(
            "Unaufgelöster Platzhalter '%s' im Feld '%s' (Payload-Hash: %s)",
            placeholder,
            context,
            payload_hash,
        )

    detail_text = ", ".join(details)
    raise LLMGenerationError(
        "API-Aufruf aufgrund unaufgelöster Platzhalter abgebrochen: "
        f"{detail_text} (Payload-Hash: {payload_hash})"
    )


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
    _sanitise_payload(payload)
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

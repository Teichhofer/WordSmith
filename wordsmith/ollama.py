"""Lightweight HTTP client to interact with a local Ollama instance."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class OllamaModel:
    """Representation of a model entry returned by the Ollama API."""

    name: str


class OllamaError(RuntimeError):
    """Raised when communication with the Ollama API fails."""


class OllamaClient:
    """Small helper around the Ollama HTTP API.

    Only the functionality required by the CLI is implemented: fetching the
    list of locally available models so the user can choose one for the
    pipeline run. The client is intentionally minimal and avoids external
    dependencies so it can run in constrained environments and be mocked
    easily in tests.
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def list_models(self) -> List[OllamaModel]:
        """Return all locally installed models.

        Raises:
            OllamaError: If the Ollama daemon is not reachable or the
                response cannot be parsed.
        """

        url = f"{self.base_url}/api/tags"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.URLError as exc:  # pragma: no cover - network failure branch
            raise OllamaError(f"Verbindung zu Ollama fehlgeschlagen: {exc}") from exc

        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OllamaError("Antwort der Ollama-API konnte nicht gelesen werden.") from exc

        models_data = data.get("models")
        if not isinstance(models_data, Sequence):
            raise OllamaError("Unerwartetes Antwortformat der Ollama-API.")

        models: List[OllamaModel] = []
        for entry in models_data:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                models.append(OllamaModel(name=name.strip()))

        return models

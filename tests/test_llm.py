import json

from wordsmith import llm
from wordsmith.config import LLMParameters, OLLAMA_TIMEOUT_SECONDS


class _DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"response": "Antwort"}).encode("utf-8")


def test_generate_text_uses_configured_timeout(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        return _DummyResponse()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    result = llm.generate_text(
        provider="ollama",
        model="mixtral",
        prompt="Hallo",
        system_prompt="System",
        parameters=LLMParameters(),
    )

    assert result.text == "Antwort"
    assert captured["timeout"] == OLLAMA_TIMEOUT_SECONDS


def test_generate_text_strips_context_from_raw_payload(monkeypatch):
    payload = {
        "response": "Antwort",
        "context": [1, 2, 3],
        "done": True,
    }

    class _PayloadResponse:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._data

    response_bytes = json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        return _PayloadResponse(response_bytes)

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    result = llm.generate_text(
        provider="ollama",
        model="mixtral",
        prompt="Hallo",
        system_prompt="System",
        parameters=LLMParameters(),
    )

    assert result.text == "Antwort"
    assert "context" not in result.raw
    assert result.raw["context_token_count"] == 3
    assert result.raw["response"] == "Antwort"

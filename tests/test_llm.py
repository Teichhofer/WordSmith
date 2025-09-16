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

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import llm
from wordsmith.config import LLMParameters, OLLAMA_TIMEOUT_SECONDS


class _DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"response": "Antwort"}).encode("utf-8")


class _StreamingResponse:
    def __init__(self, payloads):
        self._data = "\n".join(json.dumps(payload) for payload in payloads).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._data


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


def test_generate_text_starts_with_empty_context(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _DummyResponse()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    llm.generate_text(
        provider="ollama",
        model="mixtral",
        prompt="Hallo",
        system_prompt="System",
        parameters=LLMParameters(),
    )

    assert captured["payload"].get("context") == []


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


def test_generate_text_handles_streaming_payload(monkeypatch):
    fragments = [
        {"response": "Erster Teil ", "done": False},
        {"response": "und zweiter Abschnitt.", "done": False},
        {
            "response": "",
            "done": True,
            "context": [1, 2, 3],
            "prompt_eval_count": 12,
            "eval_count": 24,
        },
    ]

    def fake_urlopen(request, timeout):
        return _StreamingResponse(fragments)

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    result = llm.generate_text(
        provider="ollama",
        model="mixtral",
        prompt="Hallo",
        system_prompt="System",
        parameters=LLMParameters(),
    )

    assert result.text == "Erster Teil und zweiter Abschnitt."
    assert result.raw["context_token_count"] == 3
    assert result.raw.get("response") == ""
    assert result.raw.get("response_fragments") == [
        "Erster Teil ",
        "und zweiter Abschnitt.",
    ]


def test_prepare_options_include_stop_and_num_predict_defaults() -> None:
    params = LLMParameters()

    options = llm._prepare_options(params)

    assert options["num_predict"] == 900
    assert options["stop"] == []

    params.update({"num_predict": 256, "stop": ["ENDE"]})

    updated = llm._prepare_options(params)

    assert updated["num_predict"] == 256
    assert updated["stop"] == ["ENDE"]

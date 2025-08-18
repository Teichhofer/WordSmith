import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import json
import urllib.request
import urllib.error

import wordsmith.agent as agent
from wordsmith.config import Config


def test_writer_agent_runs(tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    steps = [agent.Step('intro'), agent.Step('body')]
    writer = agent.WriterAgent('dogs', 5, steps, iterations=1, config=cfg)
    result = writer.run()

    assert len(result.split()) <= 5
    assert (tmp_path / 'output' / 'story.txt').exists()
    assert (tmp_path / 'logs' / 'run.log').exists()


def test_call_llm_with_ollama(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        llm_provider='ollama',
        model='test-model',
        temperature=0.2,
        context_length=128,
    )

    captured = {}

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"response": "ollama text"}'

    def fake_urlopen(req):
        captured['url'] = req.full_url
        captured['data'] = json.loads(req.data.decode())
        return DummyResponse()

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)
    result = writer._call_llm('intro about cats', fallback='fb')
    assert result == 'ollama text'
    assert captured['url'] == cfg.ollama_url
    expected_prompt = f"{writer.system_prompt}\n\nintro about cats"
    assert captured['data']['prompt'] == expected_prompt
    assert captured['data']['options']['temperature'] == cfg.temperature
    assert captured['data']['options']['num_ctx'] == cfg.context_length


def test_call_llm_with_openai(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        llm_provider='openai',
        openai_api_key='test',
        model='gpt-test',
        temperature=0.3,
        context_length=64,
    )

    captured = {}

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices": [{"message": {"content": "openai text"}}]}'

    def fake_urlopen(req):
        captured['url'] = req.full_url
        captured['data'] = json.loads(req.data.decode())
        captured['headers'] = req.headers
        return DummyResponse()

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)
    result = writer._call_llm('intro about cats', fallback='fb')
    assert result == 'openai text'
    assert captured['url'] == cfg.openai_url
    assert captured['data']['messages'][0]['role'] == 'system'
    assert captured['data']['messages'][0]['content'] == writer.system_prompt
    assert captured['data']['messages'][1]['content'] == 'intro about cats'
    assert captured['data']['temperature'] == cfg.temperature
    assert captured['data']['max_tokens'] == cfg.context_length
    assert 'Authorization' in captured['headers']


def test_call_llm_openai_http_error(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        llm_provider='openai',
        openai_api_key='test',
    )

    def fake_urlopen(req):
        raise urllib.error.HTTPError(req.full_url, 404, 'not found', hdrs=None, fp=None)

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)
    result = writer._call_llm('intro about cats', fallback='Intro about cats. (iteration 1)')
    assert result == 'Intro about cats. (iteration 1)'


def test_run_uses_crafted_prompt(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    steps = [agent.Step('intro')]
    writer = agent.WriterAgent('cats', 5, steps, iterations=1, config=cfg)

    calls = []

    def fake_call_llm(prompt, fallback):
        calls.append(prompt)
        # First call crafts the prompt, second generates text
        if 'Provide an optimal prompt' in prompt:
            return 'Write about cats.'
        return 'Some text.'

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer.run()

    assert any('Provide an optimal prompt' in c for c in calls)
    assert any('Current text:' in c for c in calls)

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import json
import urllib.request
import urllib.error

import wordsmith.agent as agent
from wordsmith import prompts
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
        max_tokens=50,
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
    assert captured['data']['stream'] is False
    assert captured['data']['options']['temperature'] == cfg.temperature
    assert captured['data']['options']['num_ctx'] == cfg.context_length
    assert captured['data']['options']['num_predict'] == cfg.max_tokens


def test_call_llm_with_openai(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        llm_provider='openai',
        openai_api_key='test',
        model='gpt-test',
        temperature=0.3,
        context_length=64,
        max_tokens=40,
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
    assert captured['data']['max_tokens'] == cfg.max_tokens
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


def test_call_llm_logs_prompt_and_response(tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
    )
    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)
    result = writer._call_llm('say hi', fallback='hello')
    assert result == 'hello'
    log_path = tmp_path / 'logs' / cfg.llm_log_file
    assert log_path.exists()
    content = log_path.read_text()
    assert 'say hi' in content
    assert 'hello' in content


def test_default_meta_prompt_contains_next_step_phrase():
    assert 'nächste Schritt' in prompts.META_PROMPT


def test_meta_prompt_includes_word_count():
    formatted = prompts.META_PROMPT.format(
        title='T',
        content='C',
        word_count=123,
        current_text='',
    )
    assert '123' in formatted
    assert 'Gewünschte Länge' in formatted


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


def test_run_reports_progress(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    steps = [agent.Step('intro')]
    writer = agent.WriterAgent('cats', 5, steps, iterations=1, config=cfg)

    writer.run()

    out = capsys.readouterr().out
    assert 'step 1/1 iteration 1/1' in out
    assert 'tok/s' in out


def test_run_auto_requests_prompt(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    writer = agent.WriterAgent(
        'Title',
        10,
        [],
        iterations=2,
        config=cfg,
        content='about cats',
    )

    calls = []

    def fake_call_llm(prompt, fallback):
        calls.append(prompt)
        if 'sentinel prompt' in prompt:
            return 'Write intro.'
        return 'Some text.'

    monkeypatch.setattr(
        prompts,
        'META_PROMPT',
        'sentinel prompt {title} {content} {word_count} {current_text}',
    )
    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer.run_auto()

    out = capsys.readouterr().out
    assert any('sentinel prompt' in c for c in calls)
    assert 'iteration 1/2' in out
    assert '[##########----------]' in out
    assert (tmp_path / 'output' / 'story.txt').exists()


def test_run_auto_sets_token_limits(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        context_length=1,
        max_tokens=1,
    )

    writer = agent.WriterAgent(
        'Title',
        10,
        [],
        iterations=1,
        config=cfg,
        content='content',
    )

    captured_prompts = []

    def fake_call_llm(prompt, fallback):
        captured_prompts.append(prompt)
        return ''

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer.run_auto()

    assert cfg.context_length == 40
    assert cfg.max_tokens == 20
    assert any('Gewünschte Länge' in p for p in captured_prompts)

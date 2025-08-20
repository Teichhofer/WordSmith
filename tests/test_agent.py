import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import json
import urllib.request
import urllib.error
from datetime import datetime

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
    extra_system = "Extra system"
    result = writer._call_llm('intro about cats', fallback='fb', system_prompt=extra_system)
    assert result == 'ollama text'
    assert captured['url'] == cfg.ollama_url
    expected_prompt = f"{writer.system_prompt}\n\n{extra_system}\n\nintro about cats"
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
    extra_system = "Extra system"
    result = writer._call_llm('intro about cats', fallback='fb', system_prompt=extra_system)
    assert result == 'openai text'
    assert captured['url'] == cfg.openai_url
    assert captured['data']['messages'][0]['role'] == 'system'
    expected_system = f"{writer.system_prompt}\n\n{extra_system}"
    assert captured['data']['messages'][0]['content'] == expected_system
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
    content = log_path.read_text(encoding='utf-8').strip().splitlines()
    entries = [json.loads(line) for line in content]
    assert any(e["event"] == "prompt" and 'say hi' in e["text"] for e in entries)
    assert any(e["event"] == "response" and e["text"] == 'hello' for e in entries)
    for e in entries:
        datetime.fromisoformat(e["time"])


def test_default_meta_prompt_contains_next_step_phrase():
    assert 'nächsten sinnvollen Schritt' in prompts.META_PROMPT


def test_meta_prompt_includes_word_count():
    formatted = prompts.META_PROMPT.format(
        title='T',
        text_type='Text',
        content='C',
        word_count=123,
        current_text='',
    )
    assert '123' in formatted
    assert 'gewünschte Länge' in formatted


def test_system_prompt_template(tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)
    expected = prompts.SYSTEM_PROMPT.format(topic='cats', text_type='Text')
    assert writer.system_prompt == expected
    assert 'cats' in expected


def test_run_uses_crafted_prompt(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    steps = [agent.Step('intro')]
    writer = agent.WriterAgent('cats', 5, steps, iterations=1, config=cfg)

    calls = []

    def fake_call_llm(prompt, fallback, *, system_prompt=None):
        calls.append((prompt, system_prompt))
        # First call crafts the prompt, second generates text
        return 'Write about cats.' if len(calls) == 1 else 'Some text.'

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer.run()
    expected_meta = prompts.PROMPT_CRAFTING_PROMPT.format(task='intro', topic='cats')
    expected_user = prompts.STEP_PROMPT.format(prompt='Write about cats.', current_text='')
    assert calls[0][0] == expected_meta
    assert calls[0][1] == prompts.PROMPT_CRAFTING_SYSTEM_PROMPT
    assert calls[1][0] == expected_user
    assert calls[1][1] == prompts.STEP_SYSTEM_PROMPT


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


def test_craft_prompt_uses_system_prompt(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)

    captured = {}

    def fake_call_llm(prompt, fallback, *, system_prompt=None):
        captured['system'] = system_prompt
        return 'crafted'

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer._craft_prompt('intro')
    assert captured['system'] == prompts.PROMPT_CRAFTING_SYSTEM_PROMPT


def test_generate_uses_system_prompt(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('cats', 5, [agent.Step('intro')], iterations=1, config=cfg)

    captured = {}

    def fake_call_llm(prompt, fallback, *, system_prompt=None):
        captured['system'] = system_prompt
        return ''

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer._generate('prompt', '', 1)
    assert captured['system'] == prompts.STEP_SYSTEM_PROMPT


def test_run_auto_generates_outline_and_sections(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    writer = agent.WriterAgent(
        'Title',
        10,
        [],
        iterations=1,
        config=cfg,
        content='about cats',
        text_type='Essay',
    )

    calls: list[tuple[str, str | None]] = []
    responses = iter(
        [
            '1. Intro (5)\n2. End (5)',
            'intro text',
            'end text',
            'edited text',
        ]
    )

    def fake_call_llm(prompt, fallback, *, system_prompt=None):
        calls.append((prompt, system_prompt))
        return next(responses)

    saved = []

    def fake_save_text(text: str) -> None:
        saved.append(text)

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    monkeypatch.setattr(writer, '_save_text', fake_save_text)
    writer.run_auto()

    assert 'Erstelle eine gegliederte Outline' in calls[0][0]
    assert calls[0][1] == prompts.OUTLINE_SYSTEM_PROMPT
    assert 'Schreibe den Abschnitt' in calls[1][0]
    assert calls[1][1] == prompts.SECTION_SYSTEM_PROMPT
    assert 'Schreibe den Abschnitt' in calls[2][0]
    assert calls[2][1] == prompts.SECTION_SYSTEM_PROMPT
    assert 'Überarbeite den folgenden' in calls[3][0]
    assert calls[3][1] == prompts.REVISION_SYSTEM_PROMPT
    assert saved[0] == 'intro text'
    assert saved[1] == 'intro text end text'
    assert saved[-1] == 'edited text'


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

    prompts_seen = []

    def fake_call_llm(prompt, fallback, *, system_prompt=None):
        prompts_seen.append((prompt, system_prompt))
        return ''

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)
    writer.run_auto()

    assert cfg.context_length == 40
    assert cfg.max_tokens == 20
    assert any(str(writer.word_count) in p[0] for p in prompts_seen)


def test_parse_outline(tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('T', 10, [], iterations=0, config=cfg)
    outline = '1. Intro (3)\n2. Body (5)'
    assert writer._parse_outline(outline) == [('Intro', 3), ('Body', 5)]


def test_run_auto_writes_iteration_files(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )

    writer = agent.WriterAgent(
        'Title',
        10,
        [],
        iterations=1,
        config=cfg,
        content='about cats',
    )

    responses = iter(['1. Part (5)', 'draft', 'edited'])

    def fake_call_llm(prompt, fallback, *, system_prompt=None):
        return next(responses)

    monkeypatch.setattr(writer, '_call_llm', fake_call_llm)

    writer.run_auto()
    iter0 = (
        tmp_path / 'output' / cfg.auto_iteration_file_template.format(0)
    ).read_text(encoding='utf-8').strip()
    iter1 = (
        tmp_path / 'output' / cfg.auto_iteration_file_template.format(1)
    ).read_text(encoding='utf-8').strip()
    iter2 = (
        tmp_path / 'output' / cfg.auto_iteration_file_template.format(2)
    ).read_text(encoding='utf-8').strip()
    assert iter0 == '1. Part (5)'
    assert iter1 == 'draft'
    assert iter2 == 'edited'

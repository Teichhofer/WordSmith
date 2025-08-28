import sys, pathlib, json, urllib.request, urllib.error
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
from wordsmith.config import Config

def test_call_llm_with_ollama(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        llm_provider='ollama',
        model='test-model',
        temperature=0.2,
        top_p=0.9,
        presence_penalty=0.0,
        frequency_penalty=0.3,
        seed=123,
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

    writer = agent.WriterAgent('cats', 5, iterations=1, config=cfg)
    result = writer._call_llm('intro about cats', fallback='fb', system_prompt='Extra')
    assert result == 'ollama text'
    assert captured['url'] == cfg.ollama_url
    opts = captured['data']['options']
    assert opts['temperature'] == cfg.temperature
    assert opts['top_p'] == cfg.top_p
    assert opts['presence_penalty'] == cfg.presence_penalty
    assert opts['frequency_penalty'] == cfg.frequency_penalty
    assert opts['seed'] == cfg.seed


def test_call_llm_with_openai(monkeypatch, tmp_path):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        llm_provider='openai',
        openai_api_key='test',
        model='gpt-test',
        temperature=0.2,
        top_p=0.9,
        presence_penalty=0.0,
        frequency_penalty=0.3,
        seed=42,
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

    writer = agent.WriterAgent('cats', 5, iterations=1, config=cfg)
    result = writer._call_llm('intro about cats', fallback='fb', system_prompt='Extra')
    assert result == 'openai text'
    assert captured['url'] == cfg.openai_url
    body = captured['data']
    assert body['temperature'] == cfg.temperature
    assert body['top_p'] == cfg.top_p
    assert body['presence_penalty'] == cfg.presence_penalty
    assert body['frequency_penalty'] == cfg.frequency_penalty
    assert body['seed'] == cfg.seed


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

    writer = agent.WriterAgent('cats', 5, iterations=1, config=cfg)
    result = writer._call_llm('intro about cats', fallback='Intro about cats. (iteration 1)')
    assert result == 'Intro about cats. (iteration 1)'


def test_call_llm_logs_prompt_and_response(tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'output')
    writer = agent.WriterAgent('cats', 5, iterations=1, config=cfg)
    result = writer._call_llm('say hi', fallback='hello')
    assert result == 'hello'
    log_path = tmp_path / 'logs' / cfg.llm_log_file
    assert log_path.exists()
    content = log_path.read_text(encoding='utf-8').strip().splitlines()
    entries = [json.loads(line) for line in content]
    assert any(e["event"] == "prompt" and 'say hi' in e["text"] for e in entries)
    assert any(e["event"] == "response" and e["text"] == 'hello' for e in entries)


def test_generate_sections_from_outline_extends_short_sections(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('Topic', 5, iterations=0, config=cfg)
    outline = '1. Intro | Rolle: Hook | Wortbudget: 5 | Liefergegenstand: Start'

    prompts_seen = []
    responses = iter(['zu kurz', 'jetzt kommen genug worte'])

    def fake_call(self, prompt, *, fallback, system_prompt=None):
        prompts_seen.append(prompt)
        return next(responses)

    monkeypatch.setattr(agent.WriterAgent, '_call_llm', fake_call)

    limited, full = writer._generate_sections_from_outline(outline, '{}')
    assert len(full.split()) >= 5
    assert len(prompts_seen) == 2


def test_generate_sections_from_outline_extends_final_section(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('Topic', 5, iterations=0, config=cfg)
    outline = '1. Intro | Rolle: Hook | Wortbudget: 5 | Liefergegenstand: Start'

    prompts_seen = []
    responses = iter(['kurz', '', 'jetzt kommen genug worte'])

    def fake_call(self, prompt, *, fallback, system_prompt=None):
        prompts_seen.append(prompt)
        return next(responses)

    monkeypatch.setattr(agent.WriterAgent, '_call_llm', fake_call)

    limited, full = writer._generate_sections_from_outline(outline, '{}')
    assert len(full.split()) >= 5
    assert len(prompts_seen) == 3


def test_generate_sections_from_outline_dedupes_repeated_text(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('Topic', 4, iterations=0, config=cfg)
    outline = '1. Intro | Rolle: Hook | Wortbudget: 4 | Liefergegenstand: Start'

    responses = iter(['alpha beta', 'alpha beta gamma delta'])

    def fake_call(self, prompt, *, fallback, system_prompt=None):
        return next(responses)

    monkeypatch.setattr(agent.WriterAgent, '_call_llm', fake_call)

    limited, full = writer._generate_sections_from_outline(outline, '{}')
    assert full.strip() == 'alpha beta gamma delta'


def test_run_auto_creates_briefing_and_metadata(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent(
        'Title',
        20,
        iterations=1,
        config=cfg,
        content='notes',
        text_type='Artikel',
        audience='Leser',
        tone='sachlich',
        register='Sie',
        variant='DE-DE',
        constraints='',
        sources_allowed=True,
        seo_keywords='foo, bar',
    )

    outline = (
        '1. Intro | Rolle: Hook | Wortbudget: 10 | Liefergegenstand: Einstieg\n'
        '2. Ende | Rolle: Schluss | Wortbudget: 10 | Liefergegenstand: Fazit'
    )

    responses = iter([
        '{"goal": "inform"}',
        'improved idea',
        outline,
        outline,
        'Intro ' + ' '.join(['wort'] * 9),
        'Ende ' + ' '.join(['wort'] * 9),
        'Ja',
        'fixed text',
        'revised text',
    ])

    monkeypatch.setattr(
        agent.WriterAgent,
        '_call_llm',
        lambda self, prompt, *, fallback, system_prompt=None: next(responses),
    )

    final_text = writer.run_auto()
    assert final_text.strip() == 'revised text'

    briefing_path = cfg.output_dir / 'briefing.json'
    assert briefing_path.exists()
    meta_path = cfg.output_dir / 'metadata.json'
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta['title'] == 'Title'
    assert meta['final_word_count'] == len(final_text.split())


def test_run_auto_briefing_has_no_no_gos(monkeypatch, tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('Topic', 10, iterations=1, config=cfg)

    def fake_call(self, prompt, *, fallback, system_prompt=None):
        return fallback

    monkeypatch.setattr(agent.WriterAgent, '_call_llm', fake_call)

    writer.run_auto()

    briefing = json.loads((cfg.output_dir / 'briefing.json').read_text())
    assert 'no_gos' not in briefing


def test_run_auto_reports_token_speed(monkeypatch, tmp_path, capsys):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('Topic', 10, iterations=2, config=cfg)

    # Skip section generation to focus on revision progress
    monkeypatch.setattr(
        agent.WriterAgent,
        '_generate_sections_from_outline',
        lambda self, outline, briefing_json: ('draft', 'draft'),
    )

    responses = iter([
        '{}',  # briefing
        '',  # idea improvement
        'outline',  # outline
        'outline',  # improved outline
        '',  # type check
        'draft',  # type fix
        'one two',  # revision 1
        'one two three',  # revision 2
    ])

    def fake_call(self, prompt, *, fallback, system_prompt=None):
        return next(responses)

    monkeypatch.setattr(agent.WriterAgent, '_call_llm', fake_call)

    times = iter([0, 1, 2, 3])
    monkeypatch.setattr(agent.time, 'perf_counter', lambda: next(times))

    writer.run_auto()

    out = capsys.readouterr().out
    segments = [seg for seg in out.split('\r') if 'tok/s' in seg]
    assert any('2 tokens (2.00 tok/s)' in seg for seg in segments)
    assert any('3 tokens (3.00 tok/s)' in seg for seg in segments)

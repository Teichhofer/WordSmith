import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
from wordsmith import cli
from wordsmith.config import Config


def test_cli_main(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    captured_cfg = {}
    original_writer = agent.WriterAgent

    def capturing_writer(
        topic, word_count, steps, iterations, config, content="", text_type="Text"
    ):
        captured_cfg['config'] = config
        return original_writer(
            topic, word_count, steps, iterations, config, content=content, text_type=text_type
        )

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(
        [
            'n',
            'Cats',
            '5',
            '1',
            '1',
            'intro',
            'stub',
            'test-model',
            '0.5',
            '128',
            '256',
        ]
    )
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert 'Final text:' in captured.out
    assert 'tok/s' in captured.out
    assert (tmp_path / 'logs' / 'run.log').exists()
    assert (tmp_path / 'output' / 'story.txt').exists()
    assert captured_cfg['config'].llm_provider == 'stub'
    assert captured_cfg['config'].model == 'test-model'
    assert captured_cfg['config'].temperature == 0.5
    assert captured_cfg['config'].context_length == 128
    assert captured_cfg['config'].max_tokens == 256


def test_cli_invalid_numeric_input(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    inputs = iter(
        [
            'n',
            'Cats',
            'five', '5',
            '1',
            '1',
            'intro',
            'stub',
            'test-model',
            'abc', '0.5',
            'xyz', '128',
            'pqr', '256',
        ]
    )
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert captured.out.count('Invalid input') == 4
    assert 'Final text:' in captured.out
    assert 'tok/s' in captured.out


def test_cli_ollama_model_selection(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    monkeypatch.setattr(cli, '_fetch_ollama_models', lambda url: ['m1', 'm2'])

    captured_cfg = {}
    original_writer = agent.WriterAgent

    def capturing_writer(
        topic, word_count, steps, iterations, config, content="", text_type="Text"
    ):
        captured_cfg['config'] = config
        return original_writer(
            topic, word_count, steps, iterations, config, content=content, text_type=text_type
        )

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(
        [
            'n',
            'Cats',
            '5',
            '1',
            '1',
            'intro',
            'ollama',
            '2',
            '0.5',
            '128',
            '256',
        ]
    )
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert 'Final text:' in captured.out
    assert 'tok/s' in captured.out
    assert captured_cfg['config'].llm_provider == 'ollama'
    assert captured_cfg['config'].model == 'm2'
    assert captured_cfg['config'].max_tokens == 256


def test_cli_ollama_no_models(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    # Simulate no models being returned from Ollama
    monkeypatch.setattr(cli, '_fetch_ollama_models', lambda url: [])

    inputs = iter([
        'n',
        'Cats',
        '5',
        '1',
        '1',
        'intro',
        'ollama',
    ])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert 'No models available from Ollama.' in captured.out


def test_cli_defaults(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
        model='default-model',
        max_tokens=64,
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    captured_args = {}
    original_writer = agent.WriterAgent

    def capturing_writer(
        topic, word_count, steps, iterations, config, content="", text_type="Text"
    ):
        captured_args['topic'] = topic
        captured_args['word_count'] = word_count
        captured_args['steps'] = steps
        captured_args['iterations'] = iterations
        captured_args['config'] = config
        captured_args['content'] = content
        captured_args['text_type'] = text_type
        return original_writer(
            topic, word_count, steps, iterations, config, content=content, text_type=text_type
        )

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(['n', '', '', '', '', '', '', '', '', '', ''])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    assert captured_args['topic'] == 'Untitled'
    assert captured_args['word_count'] == 100
    assert len(captured_args['steps']) == 1
    assert captured_args['steps'][0].task == 'Step 1'
    assert captured_args['iterations'] == 1
    cfg_used = captured_args['config']
    assert cfg_used.llm_provider == 'stub'
    assert cfg_used.model == 'default-model'
    assert cfg_used.temperature == cfg.temperature
    assert cfg_used.context_length == cfg.context_length
    assert cfg_used.max_tokens == cfg.max_tokens
    assert captured_args['text_type'] == 'Text'


def test_cli_auto_mode(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    captured = {}
    original_writer = agent.WriterAgent

    def capturing_writer(
        topic, word_count, steps, iterations, config, content="", text_type="Text"
    ):
        captured['topic'] = topic
        captured['content'] = content
        captured['iterations'] = iterations
        captured['steps'] = steps
        captured['config'] = config
        captured['text_type'] = text_type
        return original_writer(
            topic, word_count, steps, iterations, config, content=content, text_type=text_type
        )

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(['y', 'My Title', 'A cat story', 'Essay', '5', '2', 'stub', 'test-model'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    out = capsys.readouterr().out
    assert 'Final text:' in out
    assert captured['steps'] == []
    assert captured['content'] == 'A cat story'
    assert captured['iterations'] == 2
    assert captured['text_type'] == 'Essay'
    cfg_used = captured['config']
    assert cfg_used.llm_provider == 'stub'
    assert cfg_used.model == 'test-model'


def test_cli_auto_mode_openai_endpoint(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    captured = {}
    original_writer = agent.WriterAgent

    def capturing_writer(
        topic, word_count, steps, iterations, config, content="", text_type="Text"
    ):
        captured['config'] = config
        return original_writer(
            topic, word_count, steps, iterations, config, content=content, text_type=text_type
        )

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(
        ['y', 'T', 'C', 'Report', '5', '1', 'openai', 'gpt', 'http://custom']
    )
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    out = capsys.readouterr().out
    assert 'Final text:' in out
    cfg_used = captured['config']
    assert cfg_used.llm_provider == 'openai'
    assert cfg_used.model == 'gpt'
    assert cfg_used.openai_url == 'http://custom'


def test_cli_keyboard_interrupt(monkeypatch, capsys):
    def raise_interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr('builtins.input', raise_interrupt)

    cli.main()

    out = capsys.readouterr().out
    assert 'Aborted.' in out

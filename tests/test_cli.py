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

    def capturing_writer(topic, word_count, steps, iterations, config):
        captured_cfg['config'] = config
        return original_writer(topic, word_count, steps, iterations, config)

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(
        [
            'Cats',
            '5',
            '1',
            '1',
            'intro',
            'stub',
            'test-model',
            '0.5',
            '128',
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


def test_cli_invalid_numeric_input(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / 'logs',
        output_dir=tmp_path / 'output',
        output_file='story.txt',
    )
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    inputs = iter(
        [
            'Cats',
            'five', '5',
            '1',
            '1',
            'intro',
            'stub',
            'test-model',
            'abc', '0.5',
            'xyz', '128',
        ]
    )
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert captured.out.count('Invalid input') == 3
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

    def capturing_writer(topic, word_count, steps, iterations, config):
        captured_cfg['config'] = config
        return original_writer(topic, word_count, steps, iterations, config)

    monkeypatch.setattr(agent, 'WriterAgent', capturing_writer)

    inputs = iter(
        [
            'Cats',
            '5',
            '1',
            '1',
            'intro',
            'ollama',
            '2',
            '0.5',
            '128',
        ]
    )
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert 'Final text:' in captured.out
    assert 'tok/s' in captured.out
    assert captured_cfg['config'].llm_provider == 'ollama'
    assert captured_cfg['config'].model == 'm2'


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

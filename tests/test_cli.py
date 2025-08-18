import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
from wordsmith import cli
from wordsmith.config import Config


def test_cli_main(monkeypatch, tmp_path, capsys):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'output')
    monkeypatch.setattr(agent, 'DEFAULT_CONFIG', cfg)

    inputs = iter(['Cats', '5', '1', '1', 'stub', 'intro'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert 'Final text:' in captured.out
    assert (tmp_path / 'logs' / 'run.log').exists()
    assert (tmp_path / 'output' / 'current_text.txt').exists()

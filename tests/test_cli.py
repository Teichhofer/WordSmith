import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
from wordsmith import cli


def test_cli_main(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(agent, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(agent, 'OUTPUT_DIR', tmp_path / 'output')

    inputs = iter(['Cats', '5', '1', '1', 'intro'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))

    cli.main()

    captured = capsys.readouterr()
    assert 'Final text:' in captured.out
    assert (tmp_path / 'logs' / 'run.log').exists()
    assert (tmp_path / 'output' / 'current_text.txt').exists()

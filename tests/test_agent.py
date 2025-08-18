import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent


def test_writer_agent_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(agent, 'OUTPUT_DIR', tmp_path / 'output')

    steps = [agent.Step('intro'), agent.Step('body')]
    writer = agent.WriterAgent('dogs', 5, steps, iterations=1)
    result = writer.run()

    assert len(result.split()) <= 5
    assert (tmp_path / 'output' / 'current_text.txt').exists()
    assert (tmp_path / 'logs' / 'run.log').exists()

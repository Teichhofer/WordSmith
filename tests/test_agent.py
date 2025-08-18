import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
from wordsmith.config import Config


def test_writer_agent_runs(tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'output')

    steps = [agent.Step('intro'), agent.Step('body')]
    writer = agent.WriterAgent('dogs', 5, steps, iterations=1, config=cfg)
    result = writer.run()

    assert len(result.split()) <= 5
    assert (tmp_path / 'output' / 'current_text.txt').exists()
    assert (tmp_path / 'logs' / 'run.log').exists()

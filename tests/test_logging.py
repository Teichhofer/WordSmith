import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from wordsmith.agent import WriterAgent, Step
from wordsmith.config import Config


def test_log_overwritten_with_new_encoding(tmp_path):
    log_dir = tmp_path / 'logs'
    out_dir = tmp_path / 'out'

    cfg16 = Config(log_dir=log_dir, output_dir=out_dir, log_encoding='utf-16')
    WriterAgent('T', 5, [Step('s')], 1, config=cfg16).run()

    cfg8 = Config(log_dir=log_dir, output_dir=out_dir, log_encoding='utf-8')
    WriterAgent('T', 5, [Step('s')], 1, config=cfg8).run()

    content = (log_dir / cfg8.log_file).read_text(encoding='utf-8')
    assert 'step 1/1' in content


import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import codecs

import wordsmith.agent as agent
from wordsmith.config import Config


def test_logs_use_utf16(tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'out')
    writer = agent.WriterAgent('topic', 5, [], iterations=1, config=cfg)
    writer.logger.info('unicode ✓')
    writer.llm_logger.info('prompt: 你好')
    run_data = (cfg.log_dir / cfg.log_file).read_bytes()
    llm_data = (cfg.log_dir / cfg.llm_log_file).read_bytes()
    for data, expected in [(run_data, 'unicode ✓'), (llm_data, 'prompt: 你好')]:
        assert data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE)
        text = data.decode('utf-16')
        assert expected in text

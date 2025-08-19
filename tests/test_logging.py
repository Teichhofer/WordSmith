import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
from wordsmith.config import Config


def test_logs_use_utf8(tmp_path):
    cfg = Config(log_dir=tmp_path / "logs", output_dir=tmp_path / "out")
    writer = agent.WriterAgent("topic", 5, [], iterations=1, config=cfg)
    writer.logger.info("unicode \u2713")
    writer.llm_logger.info("prompt: \u4f60\u597d")
    run_data = (cfg.log_dir / cfg.log_file).read_bytes()
    llm_data = (cfg.log_dir / cfg.llm_log_file).read_bytes()
    for data, expected in [
        (run_data, "unicode \u2713"),
        (llm_data, "prompt: \u4f60\u597d"),
    ]:
        assert b"\x00" not in data
        text = data.decode("utf-8")
        assert expected in text

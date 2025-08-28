import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import json
import wordsmith.agent as agent
from wordsmith.config import Config


def test_logs_use_utf8(tmp_path):
    cfg = Config(log_dir=tmp_path / "logs", output_dir=tmp_path / "out")
    writer = agent.WriterAgent("topic", 5, [], iterations=1, config=cfg)
    writer.logger.info("unicode \u2713")
    writer.llm_logger.info(json.dumps({"event": "prompt", "text": "\u4f60\u597d"}, ensure_ascii=False))
    run_data = (cfg.log_dir / cfg.log_file).read_bytes()
    llm_data = (cfg.log_dir / cfg.llm_log_file).read_bytes()
    for data, expected in [
        (run_data, "unicode \u2713"),
        (llm_data, "\u4f60\u597d"),
    ]:
        assert b"\x00" not in data
        text = data.decode("utf-8")
        assert expected in text
    # Ensure llm log is valid JSON
    json.loads(llm_data.decode("utf-8").splitlines()[0])


def test_logging_records_iteration(tmp_path):
    cfg = Config(log_dir=tmp_path / "logs", output_dir=tmp_path / "out")
    step = agent.Step(task="test")
    writer = agent.WriterAgent("topic", 5, [step], iterations=1, config=cfg)
    writer.run()
    run_log = (cfg.log_dir / cfg.log_file).read_text("utf-8")
    assert "iteration 1/1" in run_log
    llm_lines = (cfg.log_dir / cfg.llm_log_file).read_text("utf-8").splitlines()
    parsed = [json.loads(line) for line in llm_lines]
    iterations = {entry["iteration"] for entry in parsed}
    steps = {entry.get("step") for entry in parsed}
    assert 1 in iterations
    assert 1 in steps

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from wordsmith.config import Config


def test_config_creates_directories(tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'output')
    cfg.ensure_dirs()
    assert cfg.log_dir.exists()
    assert cfg.output_dir.exists()
    assert cfg.temperature == 0.7
    assert cfg.context_length == 2048
    assert cfg.max_tokens == 256
    assert cfg.log_encoding == 'utf-16'


def test_adjust_for_word_count():
    cfg = Config()
    cfg.adjust_for_word_count(50)
    assert cfg.context_length == 200
    assert cfg.max_tokens == 100

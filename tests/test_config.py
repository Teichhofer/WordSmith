import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from wordsmith.config import Config


def test_config_creates_directories(tmp_path):
    cfg = Config(log_dir=tmp_path / 'logs', output_dir=tmp_path / 'output')
    cfg.ensure_dirs()
    assert cfg.log_dir.exists()
    assert cfg.output_dir.exists()

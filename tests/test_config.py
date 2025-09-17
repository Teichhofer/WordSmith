from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith.config import (
    DEFAULT_LLM_PROVIDER,
    MIN_CONTEXT_LENGTH,
    MIN_TOKEN_LIMIT,
    Config,
    load_config,
)


def test_config_initialisation_creates_directories(tmp_path):
    output_dir = tmp_path / "out"
    logs_dir = tmp_path / "logs"

    Config(output_dir=output_dir, logs_dir=logs_dir)

    assert output_dir.exists() and output_dir.is_dir()
    assert logs_dir.exists() and logs_dir.is_dir()


def test_adjust_for_word_count_scales_limits_and_sets_determinism():
    config = Config()
    config.llm.temperature = 0.7
    config.llm.top_p = 0.5
    config.llm.presence_penalty = 1.2
    config.llm.frequency_penalty = -0.2
    config.llm.seed = None

    config.adjust_for_word_count(600)

    assert config.word_count == 600
    assert config.context_length == 8192
    assert config.token_limit == 8192
    assert config.llm.temperature == 0.8
    assert config.llm.top_p == 0.9
    assert config.llm.presence_penalty == 0.0
    assert config.llm.frequency_penalty == 0.3
    assert config.llm.seed == 42


def test_config_uses_ollama_as_default_llm_provider():
    config = Config()

    assert config.llm_provider == DEFAULT_LLM_PROVIDER


def test_config_enforces_minimum_windows_on_initialisation(tmp_path):
    config = Config(
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        context_length=512,
        token_limit=256,
    )

    assert config.context_length == MIN_CONTEXT_LENGTH
    assert config.token_limit == MIN_TOKEN_LIMIT


def test_loading_config_enforces_minimum_windows(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
            "context_length": 512,
            "token_limit": 512
        }
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.context_length == MIN_CONTEXT_LENGTH
    assert config.token_limit == MIN_TOKEN_LIMIT

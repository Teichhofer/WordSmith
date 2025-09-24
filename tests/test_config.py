from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from wordsmith.config import (
    DEFAULT_LLM_PROVIDER,
    MIN_CONTEXT_LENGTH,
    MIN_TOKEN_LIMIT,
    Config,
    ConfigError,
    LLMParameters,
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
    config.llm.temperature = 0.58
    config.llm.top_p = 0.65
    config.llm.presence_penalty = 1.2
    config.llm.frequency_penalty = -0.2
    config.llm.seed = None

    config.adjust_for_word_count(600)

    assert config.word_count == 600
    assert config.context_length == 8192
    assert config.token_limit == 8192
    assert config.llm.temperature == 0.58
    assert config.llm.top_p == 0.65
    assert config.llm.presence_penalty == 0.05
    assert config.llm.frequency_penalty == 0.05
    assert config.llm.seed == 42
    assert config.llm.num_predict == config.token_limit


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


def test_cleanup_temporary_outputs_removes_previous_run_files(tmp_path: Path) -> None:
    config = Config(output_dir=tmp_path / "output", logs_dir=tmp_path / "logs")

    temporary_files = [
        config.output_dir / "briefing.json",
        config.output_dir / "idea.txt",
        config.output_dir / "outline.txt",
        config.output_dir / "source_research.json",
        config.output_dir / "current_text.txt",
        config.output_dir / "text_type_check.txt",
        config.output_dir / "text_type_fix.txt",
        config.output_dir / "iteration_07.txt",
        config.output_dir / "reflection_03.txt",
    ]
    for path in temporary_files:
        path.write_text("veraltet", encoding="utf-8")

    final_file = config.output_dir / "Final-20240101-010101.txt"
    final_file.write_text("final", encoding="utf-8")

    config.cleanup_temporary_outputs()

    for path in temporary_files:
        assert not path.exists()
    assert final_file.exists()


def test_load_config_supports_source_search_query_count(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
            "source_search_query_count": 5
        }
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.source_search_query_count == 5


def test_load_config_rejects_negative_source_query_count(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
            "source_search_query_count": -1
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="darf nicht negativ"):
        load_config(config_path)


def test_llm_parameters_support_max_tokens_alias_and_stop_normalisation() -> None:
    params = LLMParameters()

    params.update({"max_tokens": 512, "stop": ["", "ENDE", "  Schluss "]})

    assert params.num_predict == 512
    assert params.has_override("num_predict")
    assert params.stop == ("ENDE", "Schluss")


def test_adjust_for_word_count_respects_num_predict_override() -> None:
    config = Config()
    config.llm.update({"num_predict": 1200})

    config.adjust_for_word_count(600)

    assert config.llm.num_predict == 1200

from wordsmith.config import DEFAULT_LLM_PROVIDER, Config


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
    assert config.context_length == 2400
    assert config.token_limit == 960
    assert config.llm.temperature == 0.2
    assert config.llm.top_p == 0.9
    assert config.llm.presence_penalty == 0.0
    assert config.llm.frequency_penalty == 0.3
    assert config.llm.seed == 42


def test_config_uses_ollama_as_default_llm_provider():
    config = Config()

    assert config.llm_provider == DEFAULT_LLM_PROVIDER

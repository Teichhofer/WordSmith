import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import wordsmith.agent as agent
import wordsmith.cli as cli
from wordsmith.config import Config


def test_cli_auto_mode(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / "logs",
        output_dir=tmp_path / "output",
        output_file="story.txt",
    )
    monkeypatch.setattr(agent, "DEFAULT_CONFIG", cfg)

    captured = {}
    original_writer = agent.WriterAgent

    def capturing_writer(topic, word_count, iterations, config, **kwargs):
        captured["topic"] = topic
        captured["content"] = kwargs.get("content")
        captured["iterations"] = iterations
        captured["config"] = config
        captured["text_type"] = kwargs.get("text_type")
        captured["audience"] = kwargs.get("audience")
        return original_writer(topic, word_count, iterations, config=config, **kwargs)

    monkeypatch.setattr(agent, "WriterAgent", capturing_writer)

    inputs = iter(
        [
            "My Title",  # title
            "A cat story",  # content
            "Essay",  # text type
            "Adults",  # audience
            "formal",  # tone
            "Sie",  # register
            "DE-DE",  # variant
            "",  # constraints
            "y",  # sources allowed
            "",  # seo keywords
            "5",  # word count
            "2",  # iterations
            "stub",  # provider
            "test-model",  # model name
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    cli.main()

    out = capsys.readouterr().out
    assert "Final text:" in out
    assert "Generating sections:" in out
    assert f"Revising: {captured['iterations']}/{captured['iterations']}" in out
    assert captured["content"] == "A cat story"
    assert captured["iterations"] == 2
    assert captured["text_type"] == "Essay"
    assert captured["audience"] == "Adults"
    cfg_used = captured["config"]
    assert cfg_used.llm_provider == "stub"
    assert cfg_used.model == "test-model"


def test_cli_auto_mode_ollama_custom_ip(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / "logs",
        output_dir=tmp_path / "output",
        output_file="story.txt",
    )
    monkeypatch.setattr(agent, "DEFAULT_CONFIG", cfg)
    monkeypatch.setattr(cli, "_fetch_ollama_models", lambda url: ["m1"])

    captured = {}
    original_writer = agent.WriterAgent

    def capturing_writer(topic, word_count, iterations, config, **kwargs):
        captured["config"] = config
        return original_writer(topic, word_count, iterations, config=config, **kwargs)

    monkeypatch.setattr(agent, "WriterAgent", capturing_writer)

    inputs = iter(
        [
            "T",  # title
            "C",  # content
            "Essay",  # text type
            "",  # audience
            "",  # tone
            "",  # register
            "",  # variant
            "",  # constraints
            "",  # sources allowed
            "",  # seo keywords
            "5",  # word count
            "1",  # iterations
            "",  # provider -> default ollama
            "10.1.1.1",  # custom IP
            "",  # model selection default 1
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    cli.main()

    out = capsys.readouterr().out
    assert "Final text:" in out
    cfg_used = captured["config"]
    assert cfg_used.llm_provider == "ollama"
    assert cfg_used.ollama_url == "http://10.1.1.1:11434/api/generate"
    assert cfg_used.ollama_list_url == "http://10.1.1.1:11434/api/tags"


def test_cli_auto_mode_openai_endpoint(monkeypatch, tmp_path, capsys):
    cfg = Config(
        log_dir=tmp_path / "logs",
        output_dir=tmp_path / "output",
        output_file="story.txt",
    )
    monkeypatch.setattr(agent, "DEFAULT_CONFIG", cfg)

    captured = {}
    original_writer = agent.WriterAgent

    def capturing_writer(topic, word_count, iterations, config, **kwargs):
        captured["config"] = config
        return original_writer(topic, word_count, iterations, config=config, **kwargs)

    monkeypatch.setattr(agent, "WriterAgent", capturing_writer)

    inputs = iter(
        [
            "T",  # title
            "C",  # content
            "Report",  # text type
            "",  # audience
            "",  # tone
            "",  # register
            "",  # variant
            "",  # constraints
            "",  # sources allowed
            "",  # seo keywords
            "5",  # word count
            "1",  # iterations
            "openai",  # provider
            "gpt",  # model
            "http://custom",  # openai url
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    cli.main()

    out = capsys.readouterr().out
    assert "Final text:" in out
    cfg_used = captured["config"]
    assert cfg_used.llm_provider == "openai"
    assert cfg_used.model == "gpt"
    assert cfg_used.openai_url == "http://custom"


def test_cli_keyboard_interrupt(monkeypatch, capsys):
    def raise_interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)

    cli.main()

    out = capsys.readouterr().out
    assert "Aborted." in out


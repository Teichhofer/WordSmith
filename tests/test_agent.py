import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith.agent import WriterAgent
from wordsmith.config import Config
from wordsmith.defaults import (
    DEFAULT_AUDIENCE,
    DEFAULT_CONSTRAINTS,
    DEFAULT_REGISTER,
    DEFAULT_TONE,
    DEFAULT_VARIANT,
)


def _build_config(tmp_path: Path, word_count: int) -> Config:
    config = Config(output_dir=tmp_path / "output", logs_dir=tmp_path / "logs")
    config.adjust_for_word_count(word_count)
    return config


def test_agent_applies_defaults_and_logs_hint(tmp_path):
    config = _build_config(tmp_path, 300)
    agent = WriterAgent(
        topic="Strategie",
        word_count=300,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Memo",
        audience="   ",
        tone="",
        register=" ",
        variant="  ",
        constraints="",
        sources_allowed=False,
    )

    final_text = agent.run()
    assert "Strategie" in final_text

    assert agent.audience == DEFAULT_AUDIENCE
    assert agent.tone == DEFAULT_TONE
    assert agent.register == DEFAULT_REGISTER
    assert agent.variant == DEFAULT_VARIANT
    assert agent.constraints == DEFAULT_CONSTRAINTS

    defaults_events = [
        event
        for event in agent._run_events
        if event["step"] == "input_defaults" and "defaults" in event.get("data", {})
    ]
    assert defaults_events, "Erwarteter Hinweis zu automatisch gesetzten Werten fehlt."
    recorded_defaults = set(defaults_events[-1]["data"]["defaults"])
    assert {"audience", "tone", "register", "variant", "constraints"}.issubset(
        recorded_defaults
    )


def test_agent_rebalances_word_budget(tmp_path):
    config = _build_config(tmp_path, 420)

    class ShortWriter(WriterAgent):
        def _adjust_section_to_budget(self, sentences, budget, briefing, section):  # type: ignore[override]
            text = super()._adjust_section_to_budget(sentences, budget, briefing, section)
            words = text.split()
            if len(words) <= 6:
                return text
            keep = max(3, len(words) // 4)
            truncated = " ".join(words[:keep])
            return self._ensure_variant(truncated)

    agent = ShortWriter(
        topic="Budget",  # pragma: no mutate - deterministic input
        word_count=420,
        steps=[],
        iterations=0,
        config=config,
        content="Ein kurzer Hinweis auf das Budget.",
        text_type="Bericht",
        audience="Führungsteam",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    agent.run()

    rebalance_events = [
        event for event in agent._run_events if event["step"] == "budget_rebalance"
    ]
    assert rebalance_events, "Es wurde kein Re-Balance-Hinweis protokolliert."
    assert any(event["data"]["redistributed"] > 0 for event in rebalance_events)


def test_agent_inserts_recaps_when_batches_trigger(tmp_path):
    config = _build_config(tmp_path, 640)
    config.token_limit = 150
    config.context_length = 300

    content = "Wir haben mehrere Kernbotschaften. " * 3

    agent = WriterAgent(
        topic="Batch-Test",
        word_count=640,
        steps=[],
        iterations=0,
        config=config,
        content=content,
        text_type="Strategiepapier",
        audience="Team",
        tone="inspirierend",
        register="Du",
        variant="DE-DE",
        constraints="",
        sources_allowed=True,
    )

    final_text = agent.run()

    assert "Zur Orientierung fasst Batch" in final_text
    batch_events = [
        event for event in agent._run_events if event["step"] == "batch_generation"
    ]
    assert batch_events, "Batch-Wechsel wurde nicht protokolliert."
    assert batch_events[0]["data"]["batch_index"] >= 2

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import llm
from wordsmith.agent import WriterAgent, WriterAgentError
from wordsmith.config import Config


def _build_config(tmp_path: Path, word_count: int) -> Config:
    config = Config(output_dir=tmp_path / "output", logs_dir=tmp_path / "logs")
    config.adjust_for_word_count(word_count)
    return config


def test_agent_requires_llm_configuration(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 200)

    agent = WriterAgent(
        topic="Ohne Modell",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="Kurze Notiz.",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    with pytest.raises(WriterAgentError, match="kein kompatibles LLM-Modell"):
        agent.run()


def test_agent_generates_outputs_with_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_config(tmp_path, 300)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"
    config.ollama_base_url = "http://ollama.local"

    briefing_payload = {
        "goal": "Ausarbeitung",
        "audience": "Vorstand",
        "tone": "präzise",
        "register": "Sie",
        "variant": "DE-DE",
        "constraints": "Keine Geheimnisse",
        "messages": ["Fokus auf Umsetzung"],
        "key_terms": ["Roadmap"],
    }
    idea_text = "- Fokus auf Umsetzung\n- Transparenz sichern"
    outline_text = (
        "1. Auftakt (Rolle: Hook, Wortbudget: 80 Wörter) -> Kontext setzen.\n"
        "2. Strategiepfad (Rolle: Argument, Wortbudget: 140 Wörter) -> Entscheidung stützen."
    )
    section_one = "Der Auftakt liefert vertrauliche Einblicke und schafft Klarheit."
    section_two = "Der Strategiepfad benennt vertrauliche Kennzahlen und den Ausblick."
    text_type_check = "Keine Abweichungen festgestellt."
    revision_text = (
        "## Überarbeitet\n"
        "Die Revision fasst vertrauliche Erkenntnisse zusammen und bleibt konkret."
    )

    responses = deque(
        [
            llm.LLMResult(text=json.dumps(briefing_payload)),
            llm.LLMResult(text=idea_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=section_one),
            llm.LLMResult(text=section_two),
            llm.LLMResult(text=text_type_check),
            llm.LLMResult(text=revision_text),
        ]
    )

    def fake_generate_text(**_: object) -> llm.LLMResult:
        return responses.popleft()

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    agent = WriterAgent(
        topic="Strategische Planung",
        word_count=300,
        steps=[],
        iterations=1,
        config=config,
        content="Wir priorisieren die nächsten Schritte.",
        text_type="Strategiepapier",
        audience="Vorstand",
        tone="präzise",
        register="Sie",
        variant="DE-DE",
        constraints="Keine Geheimnisse",
        sources_allowed=False,
        seo_keywords=["Roadmap"],
    )

    final_output = agent.run()

    idea_output = (config.output_dir / "idea.txt").read_text(encoding="utf-8").strip()
    outline_output = (config.output_dir / "outline.txt").read_text(encoding="utf-8").strip()
    current_text = (config.output_dir / "current_text.txt").read_text(encoding="utf-8")
    metadata = json.loads((config.output_dir / "metadata.json").read_text(encoding="utf-8"))
    compliance = json.loads((config.output_dir / "compliance.json").read_text(encoding="utf-8"))

    assert "[ENTFERNT: vertrauliche]" in final_output
    assert "[ENTFERNT: vertrauliche]" in current_text
    assert idea_output == idea_text
    assert "Strategiepfad" in outline_output
    assert metadata["llm_model"] == "llama2"
    assert metadata["final_word_count"] == agent._count_words(final_output)
    assert metadata["rubric_passed"] is True
    assert compliance["checks"]
    stages = {entry["stage"] for entry in compliance["checks"]}
    assert stages == {"draft", "revision_01"}
    assert agent._llm_generation and agent._llm_generation["status"] == "success"
    assert not responses


def test_agent_raises_when_llm_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_config(tmp_path, 200)
    config.llm_provider = "ollama"
    config.llm_model = "mistral"

    responses = deque(
        [
            llm.LLMResult(text=json.dumps({"messages": []})),
            llm.LLMResult(text="- Punkt"),
            llm.LLMResult(text="1. Abschnitt (Rolle: Hook, Wortbudget: 50 Wörter) -> Test."),
            llm.LLMResult(text="1. Abschnitt (Rolle: Hook, Wortbudget: 50 Wörter) -> Test."),
        ]
    )

    def failing_generate_text(**kwargs: object) -> llm.LLMResult:
        if responses:
            return responses.popleft()
        raise llm.LLMGenerationError("Ausfall")

    monkeypatch.setattr("wordsmith.llm.generate_text", failing_generate_text)

    agent = WriterAgent(
        topic="Fehlschlag",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="Notiz",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=True,
    )

    with pytest.raises(WriterAgentError, match="Finaler Entwurf konnte nicht erstellt"):
        agent.run()
    assert agent._llm_generation and agent._llm_generation["status"] == "failed"


def test_text_type_fix_applied_when_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 150)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"

    briefing_payload = {"goal": "Optimierung", "messages": ["CTA schärfen"]}
    idea_text = "- Fokus auf Nutzen"
    outline_text = "1. Fokus (Rolle: Hook, Wortbudget: 150 Wörter) -> Nutzen verdeutlichen."
    section_text = "Der Abschnitt bleibt allgemein und verzichtet auf einen klaren CTA."
    check_report = "- Abschnitt 1: Kein klarer CTA am Ende."
    fix_response = "## 1. Fokus\nSchärferer Abschnitt mit klarem CTA zum Schluss."

    responses = deque(
        [
            llm.LLMResult(text=json.dumps(briefing_payload)),
            llm.LLMResult(text=idea_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=section_text),
            llm.LLMResult(text=check_report),
            llm.LLMResult(text=fix_response),
        ]
    )

    def fake_generate_text(**_: object) -> llm.LLMResult:
        return responses.popleft()

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    agent = WriterAgent(
        topic="Optimierung",
        word_count=150,
        steps=[],
        iterations=0,
        config=config,
        content="Wir wollen den CTA schärfen.",
        text_type="Landingpage",
        audience="Kund:innen",
        tone="motiviert",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    final_output = agent.run()

    fix_file = (config.output_dir / "text_type_fix.txt").read_text(encoding="utf-8").strip()
    metadata = json.loads((config.output_dir / "metadata.json").read_text(encoding="utf-8"))

    assert "CTA" in final_output
    assert final_output.strip() == fix_response
    assert fix_file == fix_response
    assert "text_type_fix" in agent.steps
    assert metadata["rubric_passed"] is True
    assert not responses


def test_run_compliance_masks_sensitive_terms(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 120)

    agent = WriterAgent(
        topic="Compliance",
        word_count=120,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Memo",
        audience="Leitung",
        tone="direkt",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    result = agent._run_compliance("draft", "Die vertrauliche Information fehlt.")

    assert "[ENTFERNT: vertrauliche]" in result
    assert agent._compliance_audit
    last_entry = agent._compliance_audit[-1]
    assert last_entry["stage"] == "draft"
    assert last_entry["placeholders_present"] is False
    assert last_entry["sensitive_replacements"] == 1

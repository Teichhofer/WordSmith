from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import llm, prompts
from wordsmith.agent import WriterAgent, WriterAgentError, _load_json_object
from wordsmith.config import Config


def _build_config(tmp_path: Path, word_count: int) -> Config:
    config = Config(output_dir=tmp_path / "output", logs_dir=tmp_path / "logs")
    config.adjust_for_word_count(word_count)
    return config


def test_generate_briefing_includes_word_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 150)

    agent = WriterAgent(
        topic="Testthema",
        word_count=150,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Blogartikel",
        audience="Zielgruppe",
        tone="lebhaft",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    monkeypatch.setattr(prompts, "BRIEFING_PROMPT", "Wortanzahl: {word_count}")
    captured: dict[str, str] = {}

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return "{\"goal\": \"Test\"}"

    monkeypatch.setattr(
        WriterAgent,
        "_call_llm_stage",
        fake_call_llm_stage,
    )

    briefing = agent._generate_briefing()

    assert captured["prompt"] == "Wortanzahl: 150"
    assert captured["system_prompt"] == prompts.BRIEFING_SYSTEM_PROMPT
    assert briefing["goal"] == "Test"


def test_load_json_object_handles_invalid_escape_sequences() -> None:
    malformed = '{"goal": "Test", "key\\_terms": ["KI"], "messages": ["Hinweis"]}'

    result = _load_json_object(malformed)

    assert result["goal"] == "Test"
    assert "key_terms" in result
    assert result["key_terms"] == ["KI"]


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
    compliance_note = "[COMPLIANCE-HINWEIS: Bitte Quellen final prüfen.]"
    revision_text = (
        "## Überarbeitet\n"
        "Die Revision fasst vertrauliche Erkenntnisse zusammen und bleibt konkret.\n\n"
        + compliance_note
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
    final_files = list(config.output_dir.glob("Final-*.txt"))
    metadata = json.loads((config.output_dir / "metadata.json").read_text(encoding="utf-8"))
    compliance = json.loads((config.output_dir / "compliance.json").read_text(encoding="utf-8"))

    assert "[ENTFERNT: vertrauliche]" in final_output
    assert "[ENTFERNT: vertrauliche]" in current_text
    assert idea_output == idea_text
    assert "Strategiepfad" in outline_output
    assert len(final_files) == 1
    final_file = final_files[0]
    assert re.fullmatch(r"Final-\d{8}-\d{6}\.txt", final_file.name)
    assert final_file.read_text(encoding="utf-8").strip() == final_output.strip()
    assert metadata["llm_model"] == "llama2"
    assert metadata["final_word_count"] == agent._count_words(final_output)
    assert metadata["rubric_passed"] is True
    assert metadata["system_prompts"] == dict(prompts.STAGE_SYSTEM_PROMPTS)
    assert compliance["checks"]
    stages = {entry["stage"] for entry in compliance["checks"]}
    assert stages == {"draft", "revision_01"}
    revision_entry = next(
        entry for entry in compliance["checks"] if entry["stage"] == "revision_01"
    )
    assert revision_entry["compliance_note"] is True
    assert revision_entry["compliance_note_text"] == compliance_note
    draft_entry = next(entry for entry in compliance["checks"] if entry["stage"] == "draft")
    assert draft_entry["compliance_note_text"] == ""
    assert compliance["latest_compliance_note"] == compliance_note
    metadata_revision_entry = next(
        entry for entry in metadata["compliance_checks"] if entry["stage"] == "revision_01"
    )
    assert metadata_revision_entry["compliance_note_text"] == compliance_note
    assert metadata["latest_compliance_note"] == compliance_note
    assert agent._llm_generation and agent._llm_generation["status"] == "success"
    assert agent.runtime_seconds is not None
    assert agent.runtime_seconds >= 0
    assert not responses


def test_agent_parses_briefing_from_code_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 280)
    config.llm_provider = "ollama"
    config.llm_model = "mixtral:latest"

    briefing_payload = {
        "goal": "Blogartikel zu Produktneuheit",
        "audience": "Bestandskund:innen",
        "tone": "inspirierend",
        "register": "Du",
        "variant": "DE-DE",
        "constraints": "Keine Preise nennen",
        "messages": ["Hervorheben, wie einfach der Einstieg ist."],
        "key_terms": ["Innovation"],
    }
    briefing_text = (
        "Hier das Briefing vorab {Hinweis}:\n"
        "```json\n"
        + json.dumps(briefing_payload, indent=2)
        + "\n```\nBitte prüfen."
    )
    idea_text = "- Fokus auf Einstieg\n- Vorteile betonen"
    outline_text = (
        "1. Einstieg (Rolle: Hook, Wortbudget: 90 Wörter) -> Interesse wecken.\n"
        "2. Vorteile (Rolle: Argument, Wortbudget: 190 Wörter) -> Nutzen erklären."
    )
    section_one = "Der Einstieg adressiert bestehende Nutzer:innen und motiviert zum Weiterlesen."
    section_two = "Im Vorteilsteil wird erläutert, wie Innovation den Alltag vereinfacht."
    text_type_check = "Keine Abweichungen festgestellt."

    responses = deque(
        [
            llm.LLMResult(text=briefing_text),
            llm.LLMResult(text=idea_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=outline_text),
            llm.LLMResult(text=section_one),
            llm.LLMResult(text=section_two),
            llm.LLMResult(text=text_type_check),
        ]
    )

    def fake_generate_text(**_: object) -> llm.LLMResult:
        return responses.popleft()

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    agent = WriterAgent(
        topic="Produktneuheit vorstellen",
        word_count=280,
        steps=[],
        iterations=0,
        config=config,
        content="Neue Funktion erleichtert den Einstieg.",
        text_type="Blogartikel",
        audience="Bestandskund:innen",
        tone="inspirierend",
        register="Du",
        variant="DE-DE",
        constraints="Keine Preise nennen",
        sources_allowed=False,
        seo_keywords=["Innovation"],
    )

    final_output = agent.run()

    briefing_output = json.loads((config.output_dir / "briefing.json").read_text(encoding="utf-8"))

    assert "Innovation" in final_output
    assert briefing_output["goal"] == briefing_payload["goal"]
    assert briefing_output["messages"] == briefing_payload["messages"]
    assert not responses





def test_revision_stage_is_stateless(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 200)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"

    agent = WriterAgent(
        topic="Stateless Revision",
        word_count=200,
        steps=[],
        iterations=1,
        config=config,
        content="",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
        include_compliance_note=True,
    )

    captured: dict[str, str] = {}

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured["stage"] = stage
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return "Überarbeitet"

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    source_text = "  Aktueller Text mit Kontext.  "
    result = agent._revise_with_llm(source_text, 1, {"goal": "Test"})

    assert result == "Überarbeitet"
    assert captured["prompt"] == source_text.strip()
    assert "Briefing" not in captured["prompt"]
    base_prompt = prompts.REVISION_SYSTEM_PROMPT.strip()
    assert captured["system_prompt"].startswith(base_prompt)
    compliance_instruction = prompts.COMPLIANCE_HINT_INSTRUCTION.strip()
    if compliance_instruction:
        assert compliance_instruction in captured["system_prompt"]
    min_words, max_words = agent._calculate_word_limits(agent.word_count)
    assert f"{min_words}-{max_words}" in captured["system_prompt"]



def test_call_llm_stage_enforces_token_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 120)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"
    config.token_limit = 120

    agent = WriterAgent(
        topic="Token-Test",
        word_count=120,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    called = False

    def fake_generate_text(**_: object) -> llm.LLMResult:
        nonlocal called
        called = True
        return llm.LLMResult(text="ok")

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    long_prompt = "p" * 500
    short_system_prompt = "s" * 20

    with pytest.raises(WriterAgentError, match="Tokenbudget überschritten"):
        agent._call_llm_stage(
            stage="test_stage",
            prompt=long_prompt,
            system_prompt=short_system_prompt,
            success_message="ok",
            failure_message="fail",
        )

    assert not called





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
    assert last_entry["compliance_note_text"] == ""


def test_run_compliance_strips_note_by_default(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 80)

    agent = WriterAgent(
        topic="Hinweis",
        word_count=80,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    note_text = "Kurzer Text.\n\n[COMPLIANCE-HINWEIS: Quellen prüfen.]"
    result = agent._run_compliance("draft", note_text)

    assert "[COMPLIANCE-HINWEIS:" not in result
    assert agent._compliance_note == "[COMPLIANCE-HINWEIS: Quellen prüfen.]"
    last_entry = agent._compliance_audit[-1]
    assert last_entry["compliance_note"] is True
    assert last_entry["compliance_note_text"] == "[COMPLIANCE-HINWEIS: Quellen prüfen.]"


def test_run_compliance_keeps_note_when_enabled(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 80)

    agent = WriterAgent(
        topic="Hinweis",
        word_count=80,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
        include_compliance_note=True,
    )

    note_text = "Kurzer Text.\n\n[COMPLIANCE-HINWEIS: Quellen prüfen.]"
    result = agent._run_compliance("draft", note_text)

    assert result.strip().endswith("[COMPLIANCE-HINWEIS: Quellen prüfen.]")
    assert agent._compliance_note == "[COMPLIANCE-HINWEIS: Quellen prüfen.]"
    last_entry = agent._compliance_audit[-1]
    assert last_entry["compliance_note"] is True
    assert last_entry["compliance_note_text"] == "[COMPLIANCE-HINWEIS: Quellen prüfen.]"

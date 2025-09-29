from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any, Mapping

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from wordsmith import llm, prompts
from wordsmith.agent import (
    OutlineSection,
    WriterAgent,
    WriterAgentError,
    _load_json_object,
)
from wordsmith.config import Config


def _build_config(tmp_path: Path, word_count: int) -> Config:
    config = Config(output_dir=tmp_path / "output", logs_dir=tmp_path / "logs")
    config.adjust_for_word_count(word_count)
    return config


_DEFAULT_RAW_RESPONSE: dict[str, Any] = {
    "prompt_eval_count": 30,
    "eval_count": 60,
    "total_duration": 9_000_000_000,
}


def _llm_result(text: str, raw_override: Mapping[str, Any] | None = None) -> llm.LLMResult:
    payload = dict(_DEFAULT_RAW_RESPONSE)
    if raw_override:
        payload.update(raw_override)
    return llm.LLMResult(text=text, raw=payload)


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
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["prompt_type"] = prompt_type
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
    assert captured["prompt_type"] == "briefing"


def test_generate_reflection_includes_word_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 200)

    agent = WriterAgent(
        topic="Testthema",
        word_count=200,
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

    captured: dict[str, Any] = {}

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured["prompt"] = prompt
        captured["data"] = data or {}
        captured["stage"] = stage
        captured["system_prompt"] = system_prompt
        captured["prompt_type"] = prompt_type
        return "1. Wortbudget schließen – Gesamttext."

    monkeypatch.setattr(
        WriterAgent,
        "_call_llm_stage",
        fake_call_llm_stage,
    )

    text = "Wort " * 120
    reflection = agent._generate_reflection(text, 1)

    assert "Zielwortzahl von 200 Wörtern" in captured["prompt"]
    assert "aktuelle Länge (120 Wörter)" in captured["prompt"]
    assert "fehlenden 80 Wörter" in captured["prompt"]
    assert captured["prompt_type"] == "reflection"
    assert captured["stage"] == "reflection_01_llm"
    assert captured["system_prompt"] == prompts.REFLECTION_SYSTEM_PROMPT
    assert captured["data"].get("current_words") == 120
    assert captured["data"].get("word_gap") == 80
    assert reflection == "1. Wortbudget schließen – Gesamttext."


def test_section_prompt_includes_full_previous_text(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 200)
    agent = WriterAgent(
        topic="Serial",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Roman",
        audience="Leser:innen",
        tone="spannend",
        register="Du",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    section_one = OutlineSection(
        number="1",
        title="Einleitung",
        role="Hook",
        budget=100,
        deliverable="Spannung erzeugen",
    )
    section_two = OutlineSection(
        number="2",
        title="Konflikt",
        role="Drama",
        budget=100,
        deliverable="Konflikt zuspitzen",
    )

    previous_text = "Der Auftakt legt die Welt dar und führt die Heldin ein."
    prompt = agent._build_section_prompt(
        briefing={"goal": "Test", "audience": "Leser:innen"},
        sections=[section_one, section_two],
        section=section_two,
        idea_text="- Konflikt klar darstellen",
        compiled_sections=[(section_one, previous_text)],
    )

    marker = "**Bisheriger Text (vollständige Abschnitte):**"
    assert marker in prompt
    section_block = prompt.split(marker, 1)[1]
    context_block = section_block.split("\n\nBriefing:", 1)[0]
    assert previous_text in context_block
    assert context_block.count(previous_text) == 1


def test_section_prompt_handles_missing_previous_sections(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 150)
    agent = WriterAgent(
        topic="Serial",
        word_count=150,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Roman",
        audience="Leser:innen",
        tone="spannend",
        register="Du",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    section_one = OutlineSection(
        number="1",
        title="Einleitung",
        role="Hook",
        budget=150,
        deliverable="Spannung erzeugen",
    )

    prompt = agent._build_section_prompt(
        briefing={"goal": "Test"},
        sections=[section_one],
        section=section_one,
        idea_text="",
        compiled_sections=[],
    )

    assert "Noch kein Abschnitt verfasst." in prompt


def test_call_llm_stage_stores_raw_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_config(tmp_path, 150)
    config.llm_model = "dummy-model"

    agent = WriterAgent(
        topic="Test",
        word_count=150,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Story",
        audience="Publikum",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    def fake_generate_text(**_: Any) -> llm.LLMResult:
        return _llm_result("  Rohtext mit Leerzeichen  \nZweite Zeile  ")

    monkeypatch.setattr(llm, "generate_text", fake_generate_text)

    result = agent._call_llm_stage(
        stage="section_01_llm",
        prompt_type="section",
        prompt="Prompt",
        system_prompt="System",
        success_message="OK",
        failure_message="Fehler",
        data={"phase": "section", "target_words": 75},
    )

    assert result == "Rohtext mit Leerzeichen  \nZweite Zeile"

    output_files = sorted((config.logs_dir / "llm_outputs").glob("*.txt"))
    assert len(output_files) == 1
    stored = output_files[0].read_text(encoding="utf-8")
    assert stored == "  Rohtext mit Leerzeichen  \nZweite Zeile  \n"

    last_event = agent._run_events[-1]
    assert "artifacts" in last_event
    assert last_event["artifacts"][0].startswith("llm_outputs/")


def test_generate_draft_records_section_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_config(tmp_path, 200)
    config.llm_model = "dummy-model"

    agent = WriterAgent(
        topic="Serie",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Roman",
        audience="Leser",
        tone="spannend",
        register="Du",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    sections = [
        OutlineSection(
            number="1",
            title="Einleitung",
            role="Hook",
            budget=100,
            deliverable="Spannung",
        ),
        OutlineSection(
            number="2",
            title="Hauptteil",
            role="Konflikt",
            budget=100,
            deliverable="Auflösung",
        ),
    ]

    stage_outputs = {
        "section_01_llm": "  Erste Szene mit Geheimnissen.  ",
        "section_02_llm": "  Zweite Szene mit Auflösung.  ",
    }

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        text = stage_outputs[stage]
        path = self._store_llm_output(stage, text)
        self._last_stage_output_path = path
        return text.strip()

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    draft = agent._generate_draft_from_outline({"goal": "Test"}, sections, "Idee")

    assert "Erste Szene" in draft
    assert "Zweite Szene" in draft

    expected_paths = [
        agent._format_artifact_path(agent._stage_output_dir / "001_section_01_llm.txt"),
        agent._format_artifact_path(agent._stage_output_dir / "002_section_02_llm.txt"),
    ]
    assert agent._llm_generation["section_outputs"] == expected_paths
    assert agent._llm_generation["combined_output"] == draft
    assert agent._llm_generation["combined_output_path"] == "current_text.txt"
def test_load_json_object_handles_invalid_escape_sequences() -> None:
    malformed = '{"goal": "Test", "key\\_terms": ["KI"], "messages": ["Hinweis"]}'

    result = _load_json_object(malformed)

    assert result["goal"] == "Test"
    assert "key_terms" in result
    assert result["key_terms"] == ["KI"]


def test_load_json_object_recovers_from_missing_closing_brace() -> None:
    truncated = (
        "{\n"
        "  \"goal\": \"Test\",\n"
        "  \"key_terms\": [\"KI\", \"keller\"],\n"
        "  \"messages\": [\n"
        "    \"Hinweis eins\",\n"
        "    \"Hinweis zwei\"\n"
        "  ],\n"
        "  \"seo_keywords\": [\n"
        "    \"\",\n"
        "    \"\"\n"
        "  ]\n"
    )

    result = _load_json_object(truncated)

    assert result["goal"] == "Test"
    assert result["seo_keywords"] == ["", ""]


def test_load_json_object_recovers_from_missing_closing_brackets() -> None:
    truncated = '{"goal": "Test", "messages": ["A", "B"'

    result = _load_json_object(truncated)

    assert result["messages"] == ["A", "B"]


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


def test_run_records_llm_response_when_briefing_json_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 200)

    agent = WriterAgent(
        topic="Invalides Briefing",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="Notizen",
        text_type="Blog",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        return "kein-json"

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    with pytest.raises(
        WriterAgentError, match="Briefing-Antwort konnte nicht als JSON interpretiert werden."
    ):
        agent.run()

    assert agent._run_events
    last_event = agent._run_events[-1]
    assert last_event["step"] == "error"
    assert last_event["status"] == "failed"
    assert "LLM-Antwort" in last_event["message"]
    assert "kein-json" in last_event["message"]
    assert last_event.get("data", {}).get("raw_text") == "kein-json"


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
    section_texts = [
        "## 1. Auftakt\nDer Auftakt liefert vertrauliche Einblicke und schafft Klarheit.",
        "## 2. Strategiepfad\nDer Strategiepfad benennt vertrauliche Kennzahlen und den Ausblick.",
    ]
    text_type_check = "Keine Abweichungen festgestellt."
    compliance_note = "[COMPLIANCE-HINWEIS: Bitte Quellen final prüfen.]"
    revision_text = (
        "## Überarbeitet\n"
        "Die Revision fasst vertrauliche Erkenntnisse zusammen und bleibt konkret.\n\n"
        + compliance_note
    )
    initial_reflection_text = (
        "1. Einleitung präzisieren – Abschnitt 1.\n"
        "2. Zahlenbeispiele ergänzen – Abschnitt 2.\n"
        "3. Abschluss verdichten – Schlussabsatz."
    )
    reflection_text = (
        "1. Beispiele verifizieren – Abschnitt 2.\n"
        "2. Schlussfolgerung verdeutlichen – Abschluss."
    )
    filler_sentence = (
        "Zusätzliche Analysen erweitern die [ENTFERNT: vertrauliche] Bewertung mit konkreten Beispielen "
        "und klaren Handlungsempfehlungen."
    )
    final_stage_text = (
        "## Überarbeitet\n"
        "Die Revision fasst [ENTFERNT: vertrauliche] Erkenntnisse zusammen und bleibt konkret.\n\n"
        + " ".join([filler_sentence] * 30)
    )

    responses = deque(
        [
            _llm_result(json.dumps(briefing_payload)),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(section_texts[0]),
            _llm_result(section_texts[1]),
            _llm_result(text_type_check),
            _llm_result(initial_reflection_text),
            _llm_result(revision_text),
            _llm_result(reflection_text),
            _llm_result(final_stage_text),
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
    iteration_output = (
        config.output_dir / "iteration_02.txt"
    ).read_text(encoding="utf-8")
    first_reflection_output = (
        config.output_dir / "reflection_01.txt"
    ).read_text(encoding="utf-8").strip()
    reflection_output = (
        config.output_dir / "reflection_02.txt"
    ).read_text(encoding="utf-8").strip()
    final_draft_file = (
        config.output_dir / "final_draft.txt"
    ).read_text(encoding="utf-8").strip()
    final_files = list(config.output_dir.glob("Final-*.txt"))
    metadata = json.loads((config.output_dir / "metadata.json").read_text(encoding="utf-8"))
    compliance = json.loads((config.output_dir / "compliance.json").read_text(encoding="utf-8"))
    run_log_entries = [
        json.loads(line)
        for line in (config.logs_dir / "run.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "[ENTFERNT: vertrauliche]" in final_output
    assert "[ENTFERNT: vertrauliche]" in current_text
    assert all(not line.startswith("#") for line in iteration_output.splitlines())
    assert idea_output == idea_text
    assert "Strategiepfad" in outline_output
    assert "Einleitung präzisieren" in first_reflection_output
    assert "Schlussfolgerung verdeutlichen" in reflection_output
    assert agent._count_words(final_output) >= int(config.word_count * 0.9)
    assert final_draft_file == final_output.strip()
    assert len(final_files) == 1
    final_file = final_files[0]
    assert re.fullmatch(r"Final-\d{8}-\d{6}\.txt", final_file.name)
    assert final_file.read_text(encoding="utf-8").strip() == final_output.strip()
    assert metadata["llm_model"] == "llama2"
    assert metadata["final_word_count"] == agent._count_words(final_output)
    assert metadata["rubric_passed"] is True
    assert metadata["include_outline_headings"] is True
    assert metadata["system_prompts"] == dict(prompts.STAGE_SYSTEM_PROMPTS)
    assert metadata["source_research"] == []
    assert compliance["checks"]
    stages = {entry["stage"] for entry in compliance["checks"]}
    assert stages == {"draft", "revision_01", "final_draft"}
    revision_entry = next(
        entry for entry in compliance["checks"] if entry["stage"] == "revision_01"
    )
    assert revision_entry["compliance_note"] is True
    assert revision_entry["compliance_note_text"] == compliance_note
    draft_entry = next(entry for entry in compliance["checks"] if entry["stage"] == "draft")
    assert draft_entry["compliance_note_text"] == ""
    final_entry = next(
        entry for entry in compliance["checks"] if entry["stage"] == "final_draft"
    )
    assert final_entry["compliance_note_text"] == compliance_note
    assert compliance["latest_compliance_note"] == compliance_note
    metadata_revision_entry = next(
        entry for entry in metadata["compliance_checks"] if entry["stage"] == "revision_01"
    )
    assert metadata_revision_entry["compliance_note_text"] == compliance_note
    assert any(
        entry["stage"] == "final_draft" and entry["compliance_note_text"] == compliance_note
        for entry in metadata["compliance_checks"]
    )
    assert metadata["latest_compliance_note"] == compliance_note
    assert "final_draft" in agent.steps
    assert agent._llm_generation and agent._llm_generation["status"] == "success"
    assert agent.runtime_seconds is not None
    assert agent.runtime_seconds >= 0
    reflection_zero_event = next(
        entry for entry in run_log_entries if entry["step"] == "reflection_00"
    )
    assert reflection_zero_event["status"] == "completed"
    assert "reflection_01.txt" in reflection_zero_event["artifacts"]
    reflection_event = next(
        entry for entry in run_log_entries if entry["step"] == "reflection_01"
    )
    assert reflection_event["status"] == "completed"
    assert "reflection_02.txt" in reflection_event["artifacts"]
    assert not responses
    assert agent._telemetry
    telemetry_entry = agent._telemetry[0]
    assert telemetry_entry["token_limit"] == config.token_limit
    assert telemetry_entry["parameters"]["top_p"] == 1.0
    assert telemetry_entry["prompt_type"]
    expected_tokens_per_second = (
        _DEFAULT_RAW_RESPONSE["prompt_eval_count"]
        + _DEFAULT_RAW_RESPONSE["eval_count"]
    ) / (_DEFAULT_RAW_RESPONSE["total_duration"] / 1_000_000_000)
    assert telemetry_entry["tokens_per_second"] == pytest.approx(
        expected_tokens_per_second
    )


def test_agent_can_omit_outline_headings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 200)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"
    config.ollama_base_url = "http://ollama.local"

    briefing_payload = {"goal": "Skizze", "messages": ["Leitfaden"], "key_terms": []}
    idea_text = "- Auftakt strukturieren"
    outline_text = (
        "1. Einstieg (Rolle: Hook, Wortbudget: 80 Wörter) -> Spannung erzeugen.\n"
        "2. Ausblick (Rolle: Fazit, Wortbudget: 120 Wörter) -> Nutzen zuspitzen."
    )
    section_texts = [
        "Der Auftakt führt ins Thema ein und bindet die Leser:innen direkt ein.",
        "Der Ausblick formuliert klar den Mehrwert und ruft zur Aktion auf.",
    ]
    text_type_check = "Keine Abweichungen festgestellt."
    filler_sentence = (
        "Der Text vertieft den Blick auf die Ausgangssituation, nennt anschauliche Beispiele "
        "und betont den unmittelbaren Mehrwert für Leser:innen."
    )
    final_stage_text = (
        section_texts[0]
        + " "
        + " ".join([filler_sentence] * 12)
        + "\n\n"
        + section_texts[1]
        + " "
        + " ".join([filler_sentence] * 15)
    )

    responses = deque(
        [
            _llm_result(json.dumps(briefing_payload)),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(section_texts[0]),
            _llm_result(section_texts[1]),
            _llm_result(text_type_check),
            _llm_result(final_stage_text),
        ]
    )

    def fake_generate_text(**_: object) -> llm.LLMResult:
        return responses.popleft()

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    agent = WriterAgent(
        topic="Oberfläche ohne Überschriften",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="Bitte nur Fließtext.",
        text_type="Blogartikel",
        audience="Leser:innen",
        tone="informativ",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
        include_outline_headings=False,
    )

    final_output = agent.run()

    assert "##" not in final_output
    assert final_output.startswith("Der Auftakt führt")
    assert "Mehrwert" in final_output
    assert agent._count_words(final_output) >= int(config.word_count * 0.9)

    current_text = (config.output_dir / "current_text.txt").read_text(encoding="utf-8").strip()
    final_draft = (config.output_dir / "final_draft.txt").read_text(encoding="utf-8").strip()
    assert current_text == final_output.strip()
    assert final_draft == final_output.strip()
    assert "final_draft" in agent.steps
    assert not responses


def test_generate_draft_from_outline_accepts_string_outline_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 180)
    agent = WriterAgent(
        topic="String-Flag",  # pragma: no mutate - descriptive topic
        word_count=180,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Artikel",
        audience="Team",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
        include_outline_headings="false",
    )

    sections = [
        OutlineSection("1", "Intro", "Hook", 90, "Kontext"),
        OutlineSection("2", "Nutzen", "Argument", 90, "Belege"),
    ]

    outputs = deque([
        "Erster Abschnitt beschreibt den Einstieg.",
        "Zweiter Abschnitt liefert überzeugende Argumente.",
    ])

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: Mapping[str, Any] | None = None,
    ) -> str:
        return outputs.popleft()

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    draft = agent._generate_draft_from_outline({"goal": "Überzeugen"}, sections, "- Ideenskizze")

    assert agent.include_outline_headings is False
    assert "##" not in draft
    assert "Erster Abschnitt" in draft
    assert "Zweiter Abschnitt" in draft
    assert not outputs


def test_perform_source_research_uses_outline_titles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 220)
    config.source_search_query_count = 2

    agent = WriterAgent(
        topic="Erneuerbare Energie",
        word_count=220,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Analyse",
        audience="Vorstand",
        tone="nüchtern",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=True,
    )

    sections = [
        OutlineSection(
            number="1",
            title="Marktüberblick",
            role="Hook",
            budget=100,
            deliverable="Aktuelle Studien zusammenfassen.",
        ),
        OutlineSection(
            number="2",
            title="Förderprogramme",
            role="Argument",
            budget=120,
            deliverable="Relevante Programme vergleichen.",
        ),
    ]

    captured_queries: list[str] = []
    responses = [
        [{"title": "Studie A", "url": "https://example.com/a", "snippet": "A"}],
        [{"title": "Programm B", "url": "https://example.com/b", "snippet": "B"}],
    ]

    def fake_search(self: WriterAgent, query: str) -> list[dict[str, str]]:
        captured_queries.append(query)
        return responses[len(captured_queries) - 1]

    monkeypatch.setattr(WriterAgent, "_search_duckduckgo", fake_search)

    agent._perform_source_research(sections)

    expected_queries = [
        "Erneuerbare Energie Marktüberblick",
        "Erneuerbare Energie Förderprogramme",
    ]
    assert captured_queries == expected_queries
    assert agent._source_research_results == [
        {"query": expected_queries[0], "results": responses[0]},
        {"query": expected_queries[1], "results": responses[1]},
    ]

    stored_results = json.loads(
        (config.output_dir / "source_research.json").read_text(encoding="utf-8")
    )
    assert stored_results == agent._source_research_results

    assert agent._run_events
    summary_event = agent._run_events[-1]
    assert summary_event["step"] == "source_research"
    assert summary_event["status"] == "info"
    assert summary_event["data"] == {"queries": 2, "results": 2}


def test_perform_source_research_skips_without_sources(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 180)
    config.source_search_query_count = 3

    agent = WriterAgent(
        topic="Digitalisierung",
        word_count=180,
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

    sections = [
        OutlineSection(
            number="1",
            title="Status quo",
            role="Hook",
            budget=90,
            deliverable="Aktuelle Projekte benennen.",
        )
    ]

    agent._perform_source_research(sections)

    assert agent._source_research_results == []
    assert not (config.output_dir / "source_research.json").exists()
    assert not any(event["step"] == "source_research" for event in agent._run_events)


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
    section_texts = [
        "## 1. Einstieg\nDer Einstieg adressiert bestehende Nutzer:innen und motiviert zum Weiterlesen.",
        "## 2. Vorteile\nIm Vorteilsteil wird erläutert, wie Innovation den Alltag vereinfacht.",
    ]
    text_type_check = "Keine Abweichungen festgestellt."
    filler_sentence = (
        "Der Abschnitt führt die Innovation mit praxisnahen Beispielen aus und zeigt Schritt für Schritt den "
        "einfachen Einstieg in die Nutzung."
    )
    final_stage_text = (
        section_texts[0]
        + "\n\n"
        + " ".join([filler_sentence] * 15)
        + "\n\n"
        + section_texts[1]
        + "\n\n"
        + " ".join([filler_sentence] * 18)
    )

    responses = deque(
        [
            _llm_result(briefing_text),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(section_texts[0]),
            _llm_result(section_texts[1]),
            _llm_result(text_type_check),
            _llm_result(final_stage_text),
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
    final_draft_output = (
        config.output_dir / "final_draft.txt"
    ).read_text(encoding="utf-8").strip()

    assert "Innovation" in final_output
    assert agent._count_words(final_output) >= int(config.word_count * 0.9)
    assert final_draft_output == final_output.strip()
    assert briefing_output["goal"] == briefing_payload["goal"]
    assert briefing_output["messages"] == briefing_payload["messages"]
    assert "final_draft" in agent.steps
    assert not responses


def test_generate_draft_from_outline_compiles_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 220)
    config.llm_provider = "ollama"
    config.llm_model = "mixtral:latest"

    agent = WriterAgent(
        topic="Kampagne planen",
        word_count=220,
        steps=[],
        iterations=0,
        config=config,
        content="Rohideen zur Kampagne",
        text_type="Artikel",
        audience="Marketing-Team",
        tone="aktiv",
        register="Du",
        variant="DE-AT",
        constraints="Keine Preise nennen",
        sources_allowed=True,
        seo_keywords=["Innovation"],
        include_outline_headings=False,
    )

    sections = [
        OutlineSection(
            number="1",
            title="Einstieg",
            role="Hook",
            budget=110,
            deliverable="Kontext schaffen.",
        ),
        OutlineSection(
            number="2",
            title="Nutzen",
            role="Argument",
            budget=110,
            deliverable="Vorteile belegen.",
        ),
    ]
    briefing = {"goal": "Überzeugen", "messages": ["Nutzen zeigen"]}

    responses = deque(
        [
            "## 1. Einstieg\n\nDer Auftakt zieht Leser:innen hinein und zeichnet die Ausgangslage.",
            "## 2. Nutzen\n\nDer zweite Abschnitt liefert greifbare Vorteile und bereitet den Abschluss vor.",
        ]
    )
    captured_calls: list[dict[str, Any]] = []

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: Mapping[str, Any] | None = None,
    ) -> str:
        captured_calls.append(
            {
                "stage": stage,
                "prompt_type": prompt_type,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "success_message": success_message,
                "failure_message": failure_message,
                "data": dict(data or {}),
            }
        )
        return responses.popleft()

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    result = agent._generate_draft_from_outline(briefing, sections, "- Vorarbeit")

    assert "Der Auftakt zieht Leser:innen hinein" in result
    assert "Der zweite Abschnitt liefert" in result
    assert result.count("Der") >= 2
    assert len(captured_calls) == 2
    first_call, second_call = captured_calls
    assert first_call["stage"] == "section_01_llm"
    assert first_call["prompt_type"] == "section"
    assert first_call["system_prompt"] == prompts.SECTION_SYSTEM_PROMPT
    assert "Noch kein Abschnitt verfasst." in first_call["prompt"]
    assert sections[0].format_line() in first_call["prompt"]
    assert "Outline-Überschriften: weglassen" in first_call["prompt"]
    assert first_call["data"]["target_words"] == sections[0].budget
    assert second_call["stage"] == "section_02_llm"
    assert "Vorheriger Abschnitt 'Einstieg'" in second_call["prompt"]
    assert sections[1].format_line() in second_call["prompt"]
    assert agent._llm_generation and agent._llm_generation["status"] == "success"
    assert agent.steps and agent.steps[-1] == "llm_generation"
    assert agent._llm_generation["sections"][0]["number"] == "1"
    assert agent._llm_generation["sections"][1]["word_count"] > 0


def test_clean_outline_sections_assigns_missing_budgets(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 600)
    agent = WriterAgent(
        topic="Budget",  # pragma: no mutate - descriptive topic
        word_count=600,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Blogartikel",
        audience="Leser:innen",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    sections = [
        OutlineSection(
            number="1",
            title="Einleitung",
            role="Hook",
            budget=0,
            deliverable="Interesse wecken",
        ),
        OutlineSection(
            number="2",
            title="Hauptteil",
            role="Analyse",
            budget=200,
            deliverable="Kernaussagen erläutern",
        ),
        OutlineSection(
            number="3",
            title="Schluss",
            role="Call-to-Action",
            budget=0,
            deliverable="Handlungsimpuls geben",
        ),
    ]

    cleaned = agent._clean_outline_sections(sections)

    assert [section.budget for section in cleaned] == [200, 200, 200]
    assert sum(section.budget for section in cleaned) == 600


def test_clean_outline_sections_rebalances_overflow(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 500)
    agent = WriterAgent(
        topic="Budget",
        word_count=500,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Blogartikel",
        audience="Leser:innen",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    sections = [
        OutlineSection("1", "Eröffnung", "Hook", 300, "Rahmen setzen"),
        OutlineSection("2", "Vertiefung", "Analyse", 300, "Details ausarbeiten"),
        OutlineSection("3", "Ausblick", "Schluss", 0, "Nächste Schritte"),
    ]

    cleaned = agent._clean_outline_sections(sections)

    assert sum(section.budget for section in cleaned) == 500
    assert all(section.budget > 0 for section in cleaned)


def test_clean_outline_sections_handles_all_zero_budgets(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 450)
    agent = WriterAgent(
        topic="Budget",
        word_count=450,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Blogartikel",
        audience="Leser:innen",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    sections = [
        OutlineSection("1", "Eröffnung", "Hook", 0, "Rahmen setzen"),
        OutlineSection("2", "Vertiefung", "Analyse", 0, "Details ausarbeiten"),
        OutlineSection("3", "Ausblick", "Schluss", 0, "Nächste Schritte"),
    ]

    cleaned = agent._clean_outline_sections(sections)

    assert sum(section.budget for section in cleaned) == 450
    assert all(section.budget > 0 for section in cleaned)


def test_clean_outline_sections_ensures_unique_numbers(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 300)
    agent = WriterAgent(
        topic="Nummern",
        word_count=300,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Blogartikel",
        audience="Leser:innen",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    sections = [
        OutlineSection("1", "Einleitung", "Hook", 100, "Rahmen setzen"),
        OutlineSection("1", "Vertiefung", "Analyse", 100, "Details liefern"),
        OutlineSection("", "Schluss", "Fazit", 100, "Abschluss formulieren"),
    ]

    cleaned = agent._clean_outline_sections(sections)

    assert [section.number for section in cleaned] == ["1", "2", "3"]


def test_generate_draft_from_outline_truncates_multi_section_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 220)
    config.llm_provider = "ollama"
    config.llm_model = "mixtral:latest"

    agent = WriterAgent(
        topic="Mehrstufige Outline", 
        word_count=220,
        steps=[],
        iterations=0,
        config=config,
        content="Vorarbeit",
        text_type="Artikel",
        audience="Marketing-Team",
        tone="aktiv",
        register="Du",
        variant="DE-AT",
        constraints="Keine Preise nennen",
        sources_allowed=False,
        seo_keywords=None,
        include_outline_headings=True,
    )

    sections = [
        OutlineSection(
            number="1",
            title="Einstieg",
            role="Hook",
            budget=110,
            deliverable="Kontext schaffen.",
        ),
        OutlineSection(
            number="2",
            title="Nutzen",
            role="Argument",
            budget=110,
            deliverable="Vorteile belegen.",
        ),
    ]

    responses = deque(
        [
            (
                "## 1. Einstieg\n\n"
                "Der Auftakt liefert einen prägnanten Einstieg.\n\n"
                "## 2. Nutzen\n\n"
                "Falscher Text für Abschnitt zwei."
            ),
            "## 2. Nutzen\n\nDer zweite Abschnitt liefert greifbare Vorteile.",
        ]
    )

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: Mapping[str, Any] | None = None,
    ) -> str:
        return responses.popleft()

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    result = agent._generate_draft_from_outline(
        {"goal": "Überzeugen"}, sections, "- Kernaussagen"
    )

    assert "Falscher Text für Abschnitt zwei" not in result
    assert result.count("## 2. Nutzen") == 1
    assert not responses


def test_generate_draft_from_outline_handles_section_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 180)
    config.llm_provider = "ollama"
    config.llm_model = "mixtral:latest"

    agent = WriterAgent(
        topic="Kampagne planen",
        word_count=180,
        steps=[],
        iterations=0,
        config=config,
        content="Rohideen",
        text_type="Artikel",
        audience="Marketing-Team",
        tone="aktiv",
        register="Du",
        variant="DE-AT",
        constraints="Keine Preise nennen",
        sources_allowed=True,
        include_outline_headings=True,
    )

    sections = [
        OutlineSection("1", "Einstieg", "Hook", 90, "Kontext"),
        OutlineSection("2", "Nutzen", "Argument", 90, "Belegen"),
    ]

    responses = deque(["Abschnitt eins Text", None])

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: Mapping[str, Any] | None = None,
    ) -> str | None:
        return responses.popleft()

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    result = agent._generate_draft_from_outline({"goal": "Überzeugen"}, sections, "- Ideenskizze")

    assert result is None
    assert agent._llm_generation and agent._llm_generation["status"] == "failed"
    assert agent._llm_generation["failed_section"]["number"] == "2"
    assert not agent.steps
    assert agent._run_events
    last_event = agent._run_events[-1]
    assert last_event["step"] == "llm_generation"
    assert last_event["status"] == "warning"





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
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured["stage"] = stage
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["prompt_type"] = prompt_type
        return "Überarbeitet"

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    source_text = "  Aktueller Text mit Kontext.  "
    result = agent._revise_with_llm(source_text, 1, {"goal": "Test"})

    assert result == "Überarbeitet"
    prompt_text = captured["prompt"]
    assert prompt_text.startswith("Überarbeite den folgenden Memo")
    assert "Zielgruppe: Team" in prompt_text
    assert "\"goal\": \"Test\"" in prompt_text
    assert "Arbeitsanweisungen aus letzter Reflexion" in prompt_text
    assert "Text zur Überarbeitung:\nAktueller Text mit Kontext." in prompt_text
    assert prompts.REVISION_REFLECTION_HEADER not in prompt_text
    base_prompt = prompts.REVISION_SYSTEM_PROMPT.strip()
    assert captured["system_prompt"].startswith(base_prompt)
    compliance_instruction = prompts.COMPLIANCE_HINT_INSTRUCTION.strip()
    if compliance_instruction:
        assert compliance_instruction in captured["system_prompt"]
    min_words, max_words = agent._calculate_word_limits(agent.word_count)
    assert f"Wortkorridor: {min_words}–{max_words}" in prompt_text
    assert f"{min_words}-{max_words}" in captured["system_prompt"]
    assert captured["prompt_type"] == "revision"

def test_revision_prompt_includes_reflection_suggestions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 200)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"

    agent = WriterAgent(
        topic="Reflexionsintegration",
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

    captured_prompt: dict[str, str] = {}

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured_prompt["stage"] = stage
        captured_prompt["prompt"] = prompt
        captured_prompt["system_prompt"] = system_prompt
        captured_prompt["prompt_type"] = prompt_type
        return "Überarbeitet"

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    source_text = "Erste Version"
    improvements = "1. Einstieg zuspitzen (Absatz 1)"
    result = agent._revise_with_llm(source_text, 2, {"goal": "Test"}, improvements)

    assert result == "Überarbeitet"
    prompt_text = captured_prompt["prompt"]
    assert prompts.REVISION_REFLECTION_HEADER in prompt_text
    assert improvements in prompt_text
    assert "Arbeitsanweisungen" in prompt_text
    assert captured_prompt["prompt_type"] == "revision"


def test_run_applies_initial_reflection_to_first_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 150)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"

    sections = [OutlineSection("1", "Einstieg", "Hook", 60, "Kontext schaffen")]

    agent = WriterAgent(
        topic="Reflexion nutzen",
        word_count=150,
        steps=[],
        iterations=1,
        config=config,
        content="Ausgangssituation",
        text_type="Memo",
        audience="Team",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
        include_compliance_note=False,
    )

    monkeypatch.setattr(WriterAgent, "_generate_briefing", lambda self: {"goal": "Test"})
    monkeypatch.setattr(WriterAgent, "_improve_idea_with_llm", lambda self: "Stichpunkte")
    monkeypatch.setattr(WriterAgent, "_extract_idea_bullets", lambda self, text: [])
    monkeypatch.setattr(WriterAgent, "_create_outline_with_llm", lambda self, briefing: sections)
    monkeypatch.setattr(WriterAgent, "_refine_outline_with_llm", lambda self, briefing, secs: list(secs))
    monkeypatch.setattr(WriterAgent, "_clean_outline_sections", lambda self, secs: list(secs))
    monkeypatch.setattr(WriterAgent, "_perform_source_research", lambda self, secs: None)
    monkeypatch.setattr(
        WriterAgent,
        "_generate_draft_from_outline",
        lambda self, briefing, secs, idea_text: "Ausgangstext",
    )
    monkeypatch.setattr(
        WriterAgent,
        "_apply_text_type_review",
        lambda self, draft, briefing, secs: draft,
    )
    monkeypatch.setattr(
        WriterAgent,
        "_run_compliance",
        lambda self, stage, text, ensure_sources=False, annotation_label=None: text,
    )
    monkeypatch.setattr(
        WriterAgent,
        "_ensure_target_word_count",
        lambda self, text, briefing, secs: (text, False),
    )
    def _fake_write_final_output(self: WriterAgent, text: str) -> Path:
        path = self.output_dir / "Final-00000000-000000.txt"
        self._write_text(path, text)
        return path

    monkeypatch.setattr(WriterAgent, "_write_final_output", _fake_write_final_output)
    monkeypatch.setattr(WriterAgent, "_write_metadata", lambda self, text: None)
    monkeypatch.setattr(WriterAgent, "_write_compliance_report", lambda self: None)
    monkeypatch.setattr(WriterAgent, "_write_logs", lambda self, briefing, outline: None)

    stage_outputs = {
        "reflection_00_llm": "1. Einstieg zuspitzen – Abschnitt 1.",
        "revision_01_llm": "Überarbeiteter Text",
        "reflection_01_llm": "",
    }
    captured_prompts: dict[str, str] = {}

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: dict[str, object] | None = None,
    ) -> str:
        captured_prompts[stage] = prompt
        return stage_outputs.get(stage, "OK")

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    final_text = agent.run()

    assert final_text == "Überarbeiteter Text"
    revision_prompt = captured_prompts["revision_01_llm"]
    assert prompts.REVISION_REFLECTION_HEADER in revision_prompt
    assert "Einstieg zuspitzen" in revision_prompt
    initial_reflection_path = config.output_dir / "reflection_01.txt"
    assert initial_reflection_path.exists()
    assert (
        "Einstieg zuspitzen"
        in initial_reflection_path.read_text(encoding="utf-8").strip()
    )

def test_ensure_target_word_count_triggers_final_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path, 120)
    config.llm_provider = "ollama"
    config.llm_model = "llama2"

    agent = WriterAgent(
        topic="Längenprüfung",
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

    sections = [
        OutlineSection("1", "Einstieg", "Hook", 60, "Kontext"),
        OutlineSection("2", "Nutzen", "Argument", 60, "Beispiel"),
    ]
    briefing = {"goal": "Test"}

    call_count = 0
    captured: dict[str, Any] = {}
    expanded_text = "Langer Text " + "Wort " * 150

    def fake_call_llm_stage(
        self,
        *,
        stage: str,
        prompt_type: str,
        prompt: str,
        system_prompt: str,
        success_message: str,
        failure_message: str,
        data: Mapping[str, Any] | None = None,
    ) -> str:
        nonlocal call_count
        call_count += 1
        captured["stage"] = stage
        captured["prompt_type"] = prompt_type
        captured["prompt"] = prompt
        captured["data"] = dict(data or {})
        return expanded_text

    monkeypatch.setattr(WriterAgent, "_call_llm_stage", fake_call_llm_stage)

    short_text = "Zu kurzer Text."
    result, adjusted = agent._ensure_target_word_count(short_text, briefing, sections)

    assert adjusted is True
    assert result == expanded_text
    assert call_count == 1
    assert captured["stage"] == "final_draft_llm"
    assert captured["prompt_type"] == "final_draft"
    assert '"goal": "Test"' in captured["prompt"]
    assert captured["data"]["current_words"] == agent._count_words(short_text)
    min_words, _ = agent._calculate_word_limits(agent.word_count)
    assert captured["data"]["min_words"] == min_words

    long_text = "Wort " * 130
    result_long, adjusted_long = agent._ensure_target_word_count(long_text, briefing, sections)
    assert adjusted_long is False
    assert result_long.strip() == long_text.strip()
    assert call_count == 1


def test_stage_parameters_use_configured_generation_limits(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 400)
    config.llm.num_predict = 1234
    config.llm.stop = ("<<END>>",)

    agent = WriterAgent(
        topic="Parameterkopie",
        word_count=400,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Fachartikel",
        audience="Profis",
        tone="präzise",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    parameters = agent._build_stage_parameters("section")

    assert parameters.num_predict == config.llm.num_predict
    assert parameters.stop == config.llm.stop


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
        return _llm_result("ok")

    monkeypatch.setattr("wordsmith.llm.generate_text", fake_generate_text)

    long_prompt = "p" * 500
    short_system_prompt = "s" * 20

    with pytest.raises(WriterAgentError, match="Tokenbudget überschritten"):
        agent._call_llm_stage(
            stage="test_stage",
            prompt_type="section",
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
    config.source_search_query_count = 0

    responses = deque(
        [
            _llm_result(json.dumps({"messages": []})),
            _llm_result("- Punkt"),
            _llm_result("1. Abschnitt (Rolle: Hook, Wortbudget: 50 Wörter) -> Test."),
            _llm_result("1. Abschnitt (Rolle: Hook, Wortbudget: 50 Wörter) -> Test."),
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
    final_draft_text = "## 1. Fokus\nDer Abschnitt bleibt allgemein und verzichtet auf einen klaren CTA."
    check_report = "- Abschnitt 1: Kein klarer CTA am Ende."
    fix_response = "## 1. Fokus\nSchärferer Abschnitt mit klarem CTA zum Schluss."
    final_stage_text = (
        fix_response
        + "\n\n"
        + " ".join(
            [
                "Der Abschnitt liefert konkrete Beispiele, stärkt den Nutzen und endet mit einem klaren CTA, "
                "der Leser:innen unmittelbar anspricht."
            ]
            * 20
        )
    )

    responses = deque(
        [
            _llm_result(json.dumps(briefing_payload)),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(final_draft_text),
            _llm_result(check_report),
            _llm_result(fix_response),
            _llm_result(final_stage_text),
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
    final_draft = (config.output_dir / "final_draft.txt").read_text(encoding="utf-8").strip()
    metadata = json.loads((config.output_dir / "metadata.json").read_text(encoding="utf-8"))

    assert "CTA" in final_output
    assert agent._count_words(final_output) >= int(config.word_count * 0.9)
    assert final_output.strip() == final_stage_text
    assert fix_file == fix_response
    assert "text_type_fix" in agent.steps
    assert "final_draft" in agent.steps
    assert final_draft == final_output.strip()
    assert metadata["rubric_passed"] is True
    assert metadata["source_research"] == []
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


def test_truncate_following_sections_ignores_plain_title_prefix(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 200)
    agent = WriterAgent(
        topic="Test",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Artikel",
        audience="Leser:innen",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    text = "Einleitung mit Beispielen.\n\nNutzen entstehen durch gemeinsame Arbeit."
    remaining = [
        OutlineSection(
            number="2",
            title="Nutzen",
            role="Analyse",
            budget=100,
            deliverable="Ergebnisse darstellen",
        )
    ]

    result = agent._truncate_following_sections(text, remaining)

    assert result == text


def test_truncate_following_sections_detects_heading(tmp_path: Path) -> None:
    config = _build_config(tmp_path, 200)
    agent = WriterAgent(
        topic="Test",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="",
        text_type="Artikel",
        audience="Leser:innen",
        tone="neutral",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )

    text = "Einleitung mit Beispielen.\n\n## Nutzen\nWeitere Details folgen."
    remaining = [
        OutlineSection(
            number="2",
            title="Nutzen",
            role="Analyse",
            budget=100,
            deliverable="Ergebnisse darstellen",
        )
    ]

    result = agent._truncate_following_sections(text, remaining)

    assert result == "Einleitung mit Beispielen."

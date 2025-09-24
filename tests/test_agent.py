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
    reflection_text = (
        "1. Einleitung präzisieren – Abschnitt 1.\n"
        "2. Zahlenbeispiele ergänzen – Abschnitt 2.\n"
        "3. Abschluss verdichten – Schlussabsatz."
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
            _llm_result(revision_text),
            _llm_result(reflection_text),
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
    reflection_output = (
        config.output_dir / "reflection_02.txt"
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
    assert "Einleitung präzisieren" in reflection_output
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

    responses = deque(
        [
            _llm_result(json.dumps(briefing_payload)),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(section_texts[0]),
            _llm_result(section_texts[1]),
            _llm_result(text_type_check),
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

    current_text = (config.output_dir / "current_text.txt").read_text(encoding="utf-8").strip()
    assert current_text == final_output.strip()
    assert not responses


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

    responses = deque(
        [
            _llm_result(briefing_text),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(section_texts[0]),
            _llm_result(section_texts[1]),
            _llm_result(text_type_check),
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
    assert captured_prompt["prompt_type"] == "revision"


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

    responses = deque(
        [
            _llm_result(json.dumps(briefing_payload)),
            _llm_result(idea_text),
            _llm_result(outline_text),
            _llm_result(outline_text),
            _llm_result(final_draft_text),
            _llm_result(check_report),
            _llm_result(fix_response),
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

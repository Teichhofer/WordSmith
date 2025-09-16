import sys
from itertools import cycle
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


def test_agent_final_text_meets_quality_criteria(tmp_path):
    config = _build_config(tmp_path, 800)
    content_lines = [
        "Stakeholder erwarten belastbare Kennzahlen.",
        "Teams benötigen klare Prozesse.",
        "Budgetfragen bleiben offen.",
        "Pilotteam testet frühe Versionen.",
        "Risikoteam fordert Transparenz.",
        "Kunden fragen nach Roadmap.",
        "Support braucht Einblicke.",
        "Finanzen wollen Daten.",
    ]
    agent = WriterAgent(
        topic="Innovations-Roadmap",
        word_count=800,
        steps=[],
        iterations=1,
        config=config,
        content="\n".join(content_lines),
        text_type="Strategiepapier",
        audience="Innovationsabteilung",
        tone="präzise",
        register="Sie",
        variant="DE-DE",
        constraints="Keine vertraulichen Details",
        sources_allowed=False,
        seo_keywords=["Innovationsmanagement"],
    )

    final_text = agent.run()
    body, note = agent._extract_compliance_note(final_text)

    # Zielgruppenpassung
    assert agent.audience in body

    # Faktentreue via Platzhalter und Compliance-Protokoll
    placeholders = ("[KLÄREN", "[KENNZAHL]", "[QUELLE]", "[DATUM]", "[ZAHL]")
    assert any(marker in final_text for marker in placeholders)
    assert any(entry["placeholders_present"] for entry in agent._compliance_audit)

    # Struktur & Stil
    heading_count = body.count("## ")
    assert heading_count >= 3
    assert "## 1." in body and "## 2." in body
    assert "Nutzen Sie die Impulse" in body
    assert " du " not in body.lower()

    # Länge innerhalb ±3 %
    word_count = agent._count_words(body)
    assert abs(word_count - agent.word_count) / agent.word_count <= 0.03

    # Lesbarkeit & Kohärenz
    assert "So übersetzt der Abschnitt die Anforderung" in body
    assert "Der Ausblick bereitet den Abschnitt" in body
    assert "handlungsfähige Schritte" in body
    assert "Aufbauend auf" in body

    # Compliance-Hinweis vorhanden
    assert note.strip().startswith("[COMPLIANCE-")

    # Wiederholungen vermeiden: keine identischen aufeinanderfolgenden Zeilen
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    assert all(lines[index] != lines[index + 1] for index in range(len(lines) - 1))


def test_enforce_length_trims_excess_words_and_keeps_compliance_note(tmp_path):
    config = _build_config(tmp_path, 200)
    agent = WriterAgent(
        topic="Längenprüfung",
        word_count=200,
        steps=[],
        iterations=0,
        config=config,
        content="Kurze Notiz.",
        text_type="Memo",
        audience="Controlling",
        tone="sachlich",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )
    agent._terminology_cache = ["innovation"]
    agent._term_cycle = cycle(agent._terminology_cache)

    compliance_note = agent._build_compliance_note("draft")
    long_text = ("Wort " * 400).strip() + "\n\n" + compliance_note

    adjusted = agent._enforce_length(long_text)
    body, note = agent._extract_compliance_note(adjusted)

    assert agent._count_words(body) <= int(agent.word_count * 1.03)
    assert note.strip() == compliance_note


def test_enforce_length_extends_short_text_to_minimum(tmp_path):
    config = _build_config(tmp_path, 180)
    agent = WriterAgent(
        topic="Expansionstest",
        word_count=180,
        steps=[],
        iterations=0,
        config=config,
        content="Ausgangspunkt.",
        text_type="Notiz",
        audience="Produktteam",
        tone="motivierend",
        register="Du",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )
    agent._terminology_cache = ["innovation", "strategie", "roadmap"]
    agent._term_cycle = cycle(agent._terminology_cache)

    short_text = "Kurzer Satz."
    expanded = agent._enforce_length(short_text)
    body, _ = agent._extract_compliance_note(expanded)

    assert agent._count_words(body) >= int(agent.word_count * 0.97)
    assert "Zusätzliche Details" in body


def test_revise_draft_removes_duplicates_and_applies_register(tmp_path):
    config = _build_config(tmp_path, 220)
    agent = WriterAgent(
        topic="Registertest",
        word_count=220,
        steps=[],
        iterations=1,
        config=config,
        content="Hinweis.",
        text_type="Bericht",
        audience="Innovationsabteilung",
        tone="klar",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=True,
    )

    draft = (
        "Das Team handelt schnell. Das Team handelt schnell. du bist informiert. du bist informiert."
    )
    revised = agent._revise_draft(draft, 1, {})

    sentences = [
        sentence.strip().lower()
        for sentence in agent._split_sentences(revised)
        if sentence.strip()
    ]
    assert sentences.count("das team handelt schnell.") == 1
    assert sentences.count("sie bist informiert.") == 1
    assert " du " not in revised.lower()
    assert revised.strip().endswith(
        "Revision 1 schärft Klarheit, Flow und Terminologie für Innovationsabteilung."
    )


def test_run_compliance_masks_sensitive_terms_and_adds_placeholders(tmp_path):
    config = _build_config(tmp_path, 150)
    agent = WriterAgent(
        topic="Compliance",
        word_count=150,
        steps=[],
        iterations=0,
        config=config,
        content="vertrauliche Daten",  # pragma: no mutate - deterministic input
        text_type="Memo",
        audience="Leitung",
        tone="direkt",
        register="Sie",
        variant="DE-DE",
        constraints="",
        sources_allowed=False,
    )
    agent._compliance_audit.clear()

    result = agent._run_compliance(
        "draft",
        "Die vertraulichen Angaben fehlen.",
        ensure_sources=True,
        annotation_label="pipeline",
    )

    assert "[ENTFERNT: vertraulichen]" in result
    assert "[KLÄREN: Quellenfreigabe ausstehend]" in result
    assert "[COMPLIANCE-PIPELINE]" in result

    assert agent._compliance_audit
    last_entry = agent._compliance_audit[-1]
    assert last_entry["stage"] == "draft"
    assert last_entry["placeholders_present"] is True
    assert "Quellen" in last_entry["sources"]

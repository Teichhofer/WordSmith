from wordsmith import prompts


def test_prompts_have_system_prompts():
    assert prompts.SYSTEM_PROMPT.strip()
    assert prompts.IDEA_IMPROVEMENT_SYSTEM_PROMPT.strip()
    assert prompts.OUTLINE_SYSTEM_PROMPT.strip()
    assert prompts.OUTLINE_IMPROVEMENT_SYSTEM_PROMPT.strip()
    assert prompts.SECTION_SYSTEM_PROMPT.strip()
    assert prompts.REVISION_SYSTEM_PROMPT.strip()
    assert prompts.TEXT_TYPE_CHECK_SYSTEM_PROMPT.strip()
    assert prompts.TEXT_TYPE_FIX_SYSTEM_PROMPT.strip()
    assert prompts.STORY_DEEPENING_SYSTEM_PROMPT.strip()


def test_system_prompts_quality_phrases():
    assert "Vermeide Wiederholungen und Füllwörter" in prompts.SYSTEM_PROMPT
    assert "Rechtschreib- und Grammatikfehler" in prompts.IDEA_IMPROVEMENT_SYSTEM_PROMPT
    assert "klare Hierarchien" in prompts.OUTLINE_SYSTEM_PROMPT
    assert "Charakterisierung der Figuren" in prompts.OUTLINE_IMPROVEMENT_SYSTEM_PROMPT
    assert "konsequent im Stil" in prompts.SECTION_SYSTEM_PROMPT
    assert "Stil, Kohärenz und Grammatik" in prompts.REVISION_SYSTEM_PROMPT
    assert "Merkmalen der angegebenen Textart" in prompts.TEXT_TYPE_CHECK_SYSTEM_PROMPT
    assert "Textchecks" in prompts.TEXT_TYPE_FIX_SYSTEM_PROMPT
    assert "vertiefst die Geschichte" in prompts.STORY_DEEPENING_SYSTEM_PROMPT


def test_outline_prompt_mentions_briefing():
    text = prompts.OUTLINE_PROMPT.format(
        text_type='Report',
        title='Titel',
        briefing_json='{}',
        word_count=100,
    )
    assert 'Briefing' in text
    assert 'Rollenfunktion' in text


def test_section_prompt_mentions_briefing():
    text = prompts.SECTION_PROMPT.format(
        section_number=1,
        section_title='Einleitung',
        role='Hook',
        deliverable='Ziel',
        budget=100,
        briefing_json='{}',
        previous_section_recap='',
    )
    assert 'Briefing' in text
    assert 'Zielwortzahl' in text
    assert 'neu generierten Abschnittstext' in text


def test_text_type_fix_prompt_mentions_issues():
    text = prompts.TEXT_TYPE_FIX_PROMPT.format(
        issues='Fehler',
        current_text='Inhalt',
    )
    assert 'Rubrik-Check hat ergeben' in text
    assert 'Behebe sie' in text


def test_briefing_prompt_has_no_no_gos():
    assert 'no_gos' not in prompts.BRIEFING_PROMPT

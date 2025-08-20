from wordsmith import prompts


def test_prompts_have_system_prompts():
    assert prompts.SYSTEM_PROMPT.strip()
    assert prompts.META_SYSTEM_PROMPT.strip()
    assert prompts.INITIAL_AUTO_SYSTEM_PROMPT.strip()
    assert prompts.OUTLINE_SYSTEM_PROMPT.strip()
    assert prompts.SECTION_SYSTEM_PROMPT.strip()
    assert prompts.REVISION_SYSTEM_PROMPT.strip()
    assert prompts.PROMPT_CRAFTING_SYSTEM_PROMPT.strip()
    assert prompts.STEP_SYSTEM_PROMPT.strip()
    assert prompts.TEXT_TYPE_CHECK_SYSTEM_PROMPT.strip()


def test_system_prompts_quality_phrases():
    assert "Vermeide Wiederholungen und Füllwörter" in prompts.SYSTEM_PROMPT
    assert "strukturierter Schreibcoach" in prompts.META_SYSTEM_PROMPT
    assert "hochwertigen ersten Rohtext" in prompts.INITIAL_AUTO_SYSTEM_PROMPT
    assert "klare Hierarchien" in prompts.OUTLINE_SYSTEM_PROMPT
    assert "konsistent im Stil" in prompts.SECTION_SYSTEM_PROMPT
    assert "Stil, Kohärenz und Grammatik" in prompts.REVISION_SYSTEM_PROMPT
    assert "vermeidest Mehrdeutigkeiten" in prompts.PROMPT_CRAFTING_SYSTEM_PROMPT
    assert "Figuren, Ton und Spannung" in prompts.STEP_SYSTEM_PROMPT
    assert "Merkmalen der angegebenen Textart" in prompts.TEXT_TYPE_CHECK_SYSTEM_PROMPT


def test_section_prompt_mentions_text_type():
    assert "Textart: {text_type}" in prompts.SECTION_PROMPT
    assert "Anforderungen und Konventionen der Textart" in prompts.SECTION_PROMPT


def test_outline_prompt_mentions_character_lines():
    text = prompts.OUTLINE_PROMPT.format(
        text_type='Roman',
        title='Titel',
        content='Inhalt',
        word_count=100,
    )
    assert 'Jede Zeile beginnt mit #' in text

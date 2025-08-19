from wordsmith import prompts


def test_prompts_have_system_prompts():
    assert prompts.META_SYSTEM_PROMPT.strip()
    assert prompts.INITIAL_AUTO_SYSTEM_PROMPT.strip()
    assert prompts.OUTLINE_SYSTEM_PROMPT.strip()
    assert prompts.SECTION_SYSTEM_PROMPT.strip()
    assert prompts.REVISION_SYSTEM_PROMPT.strip()
    assert prompts.PROMPT_CRAFTING_SYSTEM_PROMPT.strip()
    assert prompts.STEP_SYSTEM_PROMPT.strip()

from __future__ import annotations

from dataclasses import replace
from typing import List

import wordsmith.agent as agent


def main() -> None:
    topic = input("Topic: ")
    word_count = int(input("Word count: "))
    step_count = int(input("Number of steps: "))
    iterations = int(input("Iterations per step: "))

    steps: List[agent.Step] = []
    for i in range(1, step_count + 1):
        task = input(f"Task for step {i}: ")
        steps.append(agent.Step(task))

    provider = (
        input("LLM provider (stub/ollama/openai): ").strip()
        or agent.DEFAULT_CONFIG.llm_provider
    )
    model = input("Model name: ").strip() or agent.DEFAULT_CONFIG.model
    temperature_input = (
        input(f"Temperature [{agent.DEFAULT_CONFIG.temperature}]: ").strip()
    )
    temperature = (
        float(temperature_input)
        if temperature_input
        else agent.DEFAULT_CONFIG.temperature
    )
    context_input = (
        input(f"Context length [{agent.DEFAULT_CONFIG.context_length}]: ").strip()
    )
    context_length = (
        int(context_input)
        if context_input
        else agent.DEFAULT_CONFIG.context_length
    )

    cfg = replace(
        agent.DEFAULT_CONFIG,
        llm_provider=provider,
        model=model,
        temperature=temperature,
        context_length=context_length,
    )
    writer = agent.WriterAgent(topic, word_count, steps, iterations, config=cfg)
    final_text = writer.run()

    print("\nFinal text:\n")
    print(final_text)


if __name__ == "__main__":
    main()

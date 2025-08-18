from __future__ import annotations

from dataclasses import replace
from typing import List

import wordsmith.agent as agent


def main() -> None:
    topic = input("Topic: ")
    word_count = int(input("Word count: "))
    step_count = int(input("Number of steps: "))
    iterations = int(input("Iterations per step: "))
    provider = (
        input("LLM provider (stub/ollama/openai): ").strip()
        or agent.DEFAULT_CONFIG.llm_provider
    )

    steps: List[agent.Step] = []
    for i in range(1, step_count + 1):
        task = input(f"Task for step {i}: ")
        steps.append(agent.Step(task))
    cfg = replace(agent.DEFAULT_CONFIG, llm_provider=provider)
    writer = agent.WriterAgent(topic, word_count, steps, iterations, config=cfg)
    final_text = writer.run()

    print("\nFinal text:\n")
    print(final_text)


if __name__ == "__main__":
    main()

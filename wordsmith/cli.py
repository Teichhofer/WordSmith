from __future__ import annotations

from typing import List

from .agent import Step, WriterAgent


def main() -> None:
    topic = input("Topic: ")
    word_count = int(input("Word count: "))
    step_count = int(input("Number of steps: "))
    iterations = int(input("Iterations per step: "))

    steps: List[Step] = []
    for i in range(1, step_count + 1):
        task = input(f"Task for step {i}: ")
        steps.append(Step(task))

    agent = WriterAgent(topic, word_count, steps, iterations)
    final_text = agent.run()

    print("\nFinal text:\n")
    print(final_text)


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import replace
import json
import urllib.error
import urllib.request
from typing import List

import wordsmith.agent as agent


def _prompt_int(prompt: str, default: int | None = None) -> int:
    while True:
        raw = input(prompt)
        if not raw.strip() and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Invalid input. Please enter a number.")


def _prompt_float(prompt: str, default: float | None = None) -> float:
    while True:
        raw = input(prompt)
        if not raw.strip() and default is not None:
            return default
        try:
            return float(raw)
        except ValueError:
            print("Invalid input. Please enter a number.")


def _fetch_ollama_models(url: str) -> List[str]:
    try:
        with urllib.request.urlopen(url) as resp:  # type: ignore[assignment]
            payload = json.loads(resp.read().decode("utf8"))
        return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
    except urllib.error.URLError:
        return []


def main() -> None:
    topic = input("Topic: ")
    word_count = _prompt_int("Word count: ")
    step_count = _prompt_int("Number of steps: ")
    iterations = _prompt_int("Iterations per step: ")

    steps: List[agent.Step] = []
    for i in range(1, step_count + 1):
        task = input(f"Task for step {i}: ")
        steps.append(agent.Step(task))

    provider = (
        input("LLM provider (stub/ollama/openai): ").strip()
        or agent.DEFAULT_CONFIG.llm_provider
    )
    if provider == "ollama":
        models = _fetch_ollama_models(agent.DEFAULT_CONFIG.ollama_list_url)
        if not models:
            print("No models available from Ollama.")
            return
        print("Available models:")
        for i, name in enumerate(models, 1):
            print(f"{i}. {name}")
        choice = _prompt_int("Select model [1]: ", default=1)
        model = models[min(max(choice, 1), len(models)) - 1]
    else:
        model = input("Model name: ").strip() or agent.DEFAULT_CONFIG.model
    temperature = _prompt_float(
        f"Temperature [{agent.DEFAULT_CONFIG.temperature}]: ",
        default=agent.DEFAULT_CONFIG.temperature,
    )
    context_length = _prompt_int(
        f"Context length [{agent.DEFAULT_CONFIG.context_length}]: ",
        default=agent.DEFAULT_CONFIG.context_length,
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

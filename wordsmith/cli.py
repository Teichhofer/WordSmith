from __future__ import annotations

from dataclasses import replace
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

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


def _fetch_ollama_models(url: str) -> list[str]:
    try:
        with urllib.request.urlopen(url) as resp:  # type: ignore[assignment]
            payload = json.loads(resp.read().decode("utf8"))
        return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
    except urllib.error.URLError:
        return []


def _run_cli() -> None:
    default_topic = "Untitled"
    topic = input(f"Title [{default_topic}]: ").strip() or default_topic
    content = input("Desired content: ").strip()
    text_type = input("Text type: ").strip() or "Text"
    audience = (
        input("Audience [Allgemeine Leserschaft mit Grundkenntnissen]: ").strip()
        or "Allgemeine Leserschaft mit Grundkenntnissen"
    )
    tone = input("Tone [sachlich-lebendig]: ").strip() or "sachlich-lebendig"
    register = input("Register [Sie]: ").strip() or "Sie"
    variant = input("Variant [DE-DE]: ").strip() or "DE-DE"
    constraints = input("Constraints (optional): ").strip()
    sources_allowed = input("Sources allowed? (y/N): ").strip().lower() == "y"
    seo_keywords = input("SEO keywords (optional): ").strip()
    word_count = _prompt_int("Word count [100]: ", default=100)
    iterations = _prompt_int("Number of iterations [1]: ", default=1)

    default_provider = "ollama"
    provider = (
        input(
            f"LLM provider (stub/ollama/openai) [{default_provider}]: "
        ).strip()
        or default_provider
    )
    if provider == "ollama":
        default_ip = urlparse(agent.DEFAULT_CONFIG.ollama_url).hostname or ""
        host_ip = input(f"Ollama host IP [{default_ip}]: ").strip() or default_ip
        base_url = f"http://{host_ip}:11434"
        ollama_url = f"{base_url}/api/generate"
        list_url = f"{base_url}/api/tags"
        models = _fetch_ollama_models(list_url)
        if not models:
            print("No models available from Ollama.")
            return
        print("Available models:")
        for i, name in enumerate(models, 1):
            print(f"{i}. {name}")
        choice = _prompt_int("Select model [1]: ", default=1)
        model = models[min(max(choice, 1), len(models)) - 1]
        cfg = replace(
            agent.DEFAULT_CONFIG,
            llm_provider=provider,
            model=model,
            ollama_url=ollama_url,
            ollama_list_url=list_url,
        )
    else:
        model = (
            input(f"Model name [{agent.DEFAULT_CONFIG.model}]: ").strip()
            or agent.DEFAULT_CONFIG.model
        )
        if provider == "openai":
            openai_url = (
                input(
                    f"OpenAI API URL [{agent.DEFAULT_CONFIG.openai_url}]: "
                ).strip()
                or agent.DEFAULT_CONFIG.openai_url
            )
            cfg = replace(
                agent.DEFAULT_CONFIG,
                llm_provider=provider,
                model=model,
                openai_url=openai_url,
            )
        else:
            cfg = replace(
                agent.DEFAULT_CONFIG, llm_provider=provider, model=model
            )

    writer = agent.WriterAgent(
        topic,
        word_count,
        iterations,
        config=cfg,
        content=content,
        text_type=text_type,
        audience=audience,
        tone=tone,
        register=register,
        variant=variant,
        constraints=constraints,
        sources_allowed=sources_allowed,
        seo_keywords=seo_keywords,
    )
    final_text = writer.run_auto()

    print("\nFinal text:\n")
    print(final_text)


def main() -> None:
    try:
        _run_cli()
    except KeyboardInterrupt:
        print("\nAborted.")


if __name__ == "__main__":
    main()

# WordSmith

WordSmith is a tiny demonstration project for an automatic writing agent.
The command‑line interface collects a brief and generates a complete text
without manual step definitions.

## Usage

```
python -m wordsmith.cli
```

The program will prompt for details such as title, desired content, text type,
audience, tone, register, variant, optional constraints, whether sources may be
used, optional SEO keywords, desired word count, revision count, and LLM
provider (stub/ollama/openai). When using Ollama you are asked for the host IP
and to choose a model from the available list. Selecting OpenAI lets you supply
a custom API URL. Each prompt displays a default in square brackets and pressing
Enter accepts it.

During execution logs are written to `logs/run.log` and `logs/llm.log` while the
evolving text is stored in `output/current_text.txt`.

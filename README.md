# WordSmith

WordSmith is a tiny demonstration project for an automatic writing agent.
The command‑line interface collects a brief and generates a complete text
without manual step definitions.

## Usage

```
python -m wordsmith.cli
```

The program will prompt for details such as title, desired content, text type,
audience, tone, register, variant, optional constraints and keywords, desired
word count, revision count, and LLM provider (stub/Ollama/OpenAI). When using
Ollama the available models are listed for selection. Each prompt displays a
default in square brackets and pressing Enter accepts it.

During execution a log is written to `logs/run.log` and the evolving text is
stored in `output/current_text.txt`.

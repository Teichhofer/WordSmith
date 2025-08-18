# WordSmith

WordSmith is a tiny demonstration project for an iterative writing agent.
The command‑line interface guides a user through a sequence of steps and
records intermediate results.

## Usage

```
python -m wordsmith.cli
```

The program will prompt for:

1. **Topic** – the subject of the text.
2. **Word count** – approximate length of the final output.
3. **Number of steps** – how many distinct phases the writing process has.
4. **Iterations per step** – how many times each phase should run.
5. **Task for each step** – a short description of what should happen in that
   step.

During execution a log is written to `logs/run.log` and the current state of
the text is stored in `output/current_text.txt`.

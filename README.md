# WordSmith

WordSmith operates solely in automatic mode. The CLI runs without any
additional configuration and other modes have been removed from the
documentation.

## Automatic Mode

The automatic mode is intended for unattended processing. Executing the
CLI triggers a fixed pipeline that transforms an input file into an
output file without requiring user interaction.

1. **Load configuration** – default settings such as model parameters and
   output paths are read from `wordsmith/config.py`.
2. **Load prompts** – templates that drive text generation are imported
   from `wordsmith/prompts.py`.
3. **Read input** – the program searches for `input/input.txt` or accepts
   data from `stdin`.
4. **Generate output** – the transformed text is written to
   `output/output.txt` and echoed to `stdout`.
5. **Exit status** – the CLI returns `0` on success and a non‑zero code on
   error.

Run the CLI in its automatic mode with:

```bash
python cli.py
```

This command executes the entire pipeline using the built‑in defaults.

import io
import contextlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from cli import main


def test_cli_main_outputs_message():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    assert "WordSmith CLI is under construction." in buffer.getvalue()

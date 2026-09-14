"""Run one song in a disposable process so native GPU contexts cannot accumulate."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def process_audio(audio_file: str, lyrics: str, language: str) -> dict[str, str]:
    """Return generated file paths only after the GPU worker has exited.

    This module deliberately does not import torch or the inference modules.
    Worker progress and errors inherit the application's stdout/stderr. Results
    use a separate file so native GPU-library output cannot corrupt the protocol.
    """
    request = {
        "audio_file": str(Path(audio_file).resolve()),
        "lyrics": lyrics,
        "language": language,
    }
    with tempfile.TemporaryDirectory(prefix="domeoke-song-") as directory:
        result_path = Path(directory) / "result.json"
        subprocess.run(
            [sys.executable, "-m", "audio_processing.worker", "--result", str(result_path)],
            input=json.dumps(request),
            text=True,
            cwd=ROOT,
            check=True,
        )
        # subprocess.run has reaped the worker before any result is delivered.
        return json.loads(result_path.read_text(encoding="utf-8"))

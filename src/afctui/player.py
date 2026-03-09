"""Audio playback via ffplay."""

from __future__ import annotations

import subprocess
from pathlib import Path


def play_audio(path: str | Path) -> subprocess.Popen:
    """Launch ffplay to play an audio file non-blocking.

    Returns the Popen object so the caller can wait on it or stop it.
    -nodisp suppresses the video window, -autoexit terminates when done.
    """
    return subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_audio(process: subprocess.Popen | None) -> None:
    """Terminate a running ffplay process, if any."""
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait()
        except Exception:
            pass
    except Exception:
        pass

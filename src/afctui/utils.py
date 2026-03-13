"""Shared utilities used by both the TUI and Windows GUI."""

from __future__ import annotations

import platform
import subprocess


# Suppress console windows on Windows for background processes.
# On POSIX, creationflags must be 0 so this resolves to an empty dict.
POPEN_FLAGS: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if platform.system() == "Windows"
    else {}
)


def fmt_time(seconds: float) -> str:
    """Format seconds as M:SS.s  (e.g. 1:04.3)."""
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:04.1f}"


def parse_trim_time(value: str) -> float | None:
    """Parse a trim time string into seconds.

    Accepts either ``M:SS.s`` (e.g. ``1:04.3``) or a bare float
    (e.g. ``64.3``).  Returns *None* if the string is empty or
    cannot be parsed.
    """
    value = value.strip()
    if not value:
        return None
    try:
        if ":" in value:
            minutes, rest = value.split(":", 1)
            return int(minutes) * 60 + float(rest)
        return float(value)
    except ValueError:
        return None

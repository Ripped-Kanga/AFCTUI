# PyInstaller runtime hook — runs before any app code.
# Redirects stderr to a log file so boot-level crashes are captured
# even when the exe is built with console=False.
import os
import sys
import tempfile

_log_path = os.path.join(tempfile.gettempdir(), "afcgui_startup.log")

try:
    _log_file = open(_log_path, "w", encoding="utf-8", buffering=1)  # line-buffered
    sys.stderr = _log_file
    # Write a header so the file always has content on startup.
    print(f"afcgui startup log: {_log_path}", file=sys.stderr)
    print(f"Python {sys.version}", file=sys.stderr)
    print(f"Executable: {sys.executable}", file=sys.stderr)
except OSError:
    pass  # Can't open log — continue silently rather than crashing harder

"""Preset storage and retrieval for AFCTUI / AFCGUI.

Presets are stored as a single JSON file in a platform-appropriate
location:
  Linux / macOS : $XDG_DATA_HOME/afctui/presets.json
                  (falls back to ~/.local/share/afctui/presets.json)
  Windows       : %APPDATA%\\AFCTUI\\presets.json

Built-in presets are always available and cannot be deleted.  User
presets take precedence when a name collides with a built-in.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path


# ---------------------------------------------------------------------------
# Built-in read-only presets
# ---------------------------------------------------------------------------

BUILT_IN_PRESETS: dict[str, dict] = {
    "MP3 High Quality": {
        "container": ".mp3", "codec": "libmp3lame",
        "bitrate": "320k", "channels": 2,
    },
    "Podcast (Mono)": {
        "container": ".mp3", "codec": "libmp3lame",
        "bitrate": "128k", "channels": 1,
    },
    "Voice (Mono)": {
        "container": ".mp3", "codec": "libmp3lame",
        "bitrate": "96k", "channels": 1,
    },
    "Lossless FLAC": {
        "container": ".flac", "codec": "flac",
        "bitrate": None, "channels": 2,
    },
}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_presets_path() -> Path:
    """Return the platform-appropriate path for the presets JSON file."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "AFCTUI" / "presets.json"
    # Linux / macOS — XDG Base Directory Specification
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "afctui" / "presets.json"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_user_presets() -> dict[str, dict]:
    """Load user-saved presets from disk.

    Returns an empty dict if the file is missing or cannot be parsed.
    """
    path = get_presets_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_user_presets(presets: dict[str, dict]) -> None:
    path = get_presets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)


def all_presets() -> dict[str, dict]:
    """Return built-in presets merged with user presets.

    User presets take precedence; built-ins fill any gaps.
    Ordering: built-ins first (in definition order), then user presets.
    """
    merged: dict[str, dict] = dict(BUILT_IN_PRESETS)
    merged.update(load_user_presets())
    return merged


def save_preset(
    name: str,
    container: str,
    codec: str,
    bitrate: str | None,
    channels: int,
) -> None:
    """Persist a named user preset, overwriting if it already exists."""
    user = load_user_presets()
    user[name] = {
        "container": container,
        "codec": codec,
        "bitrate": bitrate,
        "channels": channels,
    }
    _save_user_presets(user)


def delete_preset(name: str) -> None:
    """Delete a user preset by name.  No-op if the name does not exist.

    Built-in presets cannot be deleted; if ``name`` matches a built-in
    it will simply not be found in user presets and nothing is written.
    """
    user = load_user_presets()
    if name in user:
        del user[name]
        _save_user_presets(user)


def is_builtin(name: str) -> bool:
    """Return True if *name* is a built-in preset (not user-created)."""
    return name in BUILT_IN_PRESETS and name not in load_user_presets()

"""Entry point for AFCTUI."""

from __future__ import annotations

import sys


_DESKTOP_ID = "afctui"
_DESKTOP_CONTENT = """\
[Desktop Entry]
Version=1.0
Type=Application
Name=AFCTUI
Comment=Audio File Converter (TUI)
Exec=afctui
Terminal=true
Categories=AudioVideo;Audio;Utility;
"""


def _desktop_path():
    """Return ~/.local/share/applications/afctui.desktop"""
    from pathlib import Path
    return Path.home() / ".local" / "share" / "applications" / f"{_DESKTOP_ID}.desktop"


def _install_desktop() -> None:
    path = _desktop_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DESKTOP_CONTENT, encoding="utf-8")
    print(f"Installed desktop entry: {path}")


def _uninstall_desktop() -> None:
    path = _desktop_path()
    if path.exists():
        path.unlink()
        print(f"Removed desktop entry: {path}")
    else:
        print(f"Desktop entry not found: {path}")


def main() -> None:
    if "--install-desktop" in sys.argv:
        _install_desktop()
        return

    if "--uninstall-desktop" in sys.argv:
        _uninstall_desktop()
        return

    from afctui.converter import check_ffmpeg
    try:
        check_ffmpeg()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from afctui.app import AFCApp
    app = AFCApp()
    app.run()


if __name__ == "__main__":
    main()

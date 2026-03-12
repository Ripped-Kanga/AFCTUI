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
Icon=afctui
Terminal=true
Categories=AudioVideo;Audio;Utility;
"""


def _desktop_path():
    from pathlib import Path
    return Path.home() / ".local" / "share" / "applications" / f"{_DESKTOP_ID}.desktop"


def _icon_path():
    from pathlib import Path
    return Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / f"{_DESKTOP_ID}.svg"


def _install_desktop() -> None:
    from importlib.resources import files

    desktop = _desktop_path()
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(_DESKTOP_CONTENT, encoding="utf-8")
    print(f"Installed desktop entry: {desktop}")

    icon_dest = _icon_path()
    icon_dest.parent.mkdir(parents=True, exist_ok=True)
    icon_src = files("afctui") / "assets" / "afctui.svg"
    icon_dest.write_bytes(icon_src.read_bytes())
    print(f"Installed icon:          {icon_dest}")


def _uninstall_desktop() -> None:
    removed_any = False

    desktop = _desktop_path()
    if desktop.exists():
        desktop.unlink()
        print(f"Removed desktop entry: {desktop}")
        removed_any = True

    icon = _icon_path()
    if icon.exists():
        icon.unlink()
        print(f"Removed icon:          {icon}")
        removed_any = True

    if not removed_any:
        print("Nothing to remove.")


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

"""Entry point for the AFCTUI Windows GUI application."""

from __future__ import annotations

import sys


def _fatal(title: str, message: str) -> None:
    """Show an error dialog without requiring Qt (safe before QApplication exists).

    Uses only sys (built-in) and ctypes (C extension) so this works even when
    PyInstaller's base_library.zip cannot be resolved — which can happen on
    machines where %TEMP% is set to a Windows 8.3 short-name path (e.g. a
    username containing a dot on an Entra ID joined machine).
    """
    # Write a log file first so the information is preserved even if the
    # MessageBox call below also fails.  Wrapped defensively because os and
    # tempfile live in base_library.zip and may not be importable in the same
    # failure scenario described above.
    log_path: str | None = None
    try:
        import os
        import tempfile
        log_path = os.path.join(tempfile.gettempdir(), "afcgui_startup.log")
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(f"{title}\n\n{message}\n")
    except Exception:  # noqa: BLE001
        pass

    # sys.platform is a built-in attribute — never needs base_library.zip.
    if sys.platform == "win32":
        try:
            import ctypes
            detail = f"\n\nSee startup log:\n{log_path}" if log_path else ""
            ctypes.windll.user32.MessageBoxW(0, message + detail, title, 0x10)
        except Exception:  # noqa: BLE001
            pass
    else:
        print(f"{title}: {message}", file=sys.stderr)


def main() -> None:
    try:
        _run()
    except Exception as exc:  # noqa: BLE001
        import traceback
        _fatal(
            "AFCGUI — Unexpected Error",
            f"AFCGUI failed to start:\n\n{exc}\n\n{traceback.format_exc()}",
        )
        sys.exit(1)


def _run() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("AFCGUI")
    app.setApplicationDisplayName("Audio File Converter")

    try:
        from afctui.converter import check_ffmpeg
        check_ffmpeg()
    except RuntimeError as exc:
        if not _handle_missing_ffmpeg(str(exc)):
            sys.exit(1)
        # User may have just installed ffmpeg — re-check before launching
        try:
            from afctui.converter import check_ffmpeg
            check_ffmpeg()
        except RuntimeError:
            sys.exit(1)

    from afctui.gui_app import AFCGuiApp
    window = AFCGuiApp()
    window.show()
    sys.exit(app.exec())


def _handle_missing_ffmpeg(error_msg: str) -> bool:
    """Show a dialog explaining the missing ffmpeg dependency.

    On Windows, offers a one-click winget install option.
    Returns True if the user attempted an install (caller should re-check PATH).
    """
    import webbrowser

    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox()
    msg.setWindowTitle("ffmpeg not found")
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText("ffmpeg is required but was not found on your PATH.")
    msg.setInformativeText(
        "AFCTUI uses ffmpeg for audio conversion and playback.\n\n"
        "Install ffmpeg and restart the app, or use the button below."
    )
    msg.setDetailedText(error_msg)

    winget_btn = None
    if sys.platform == "win32":
        winget_btn = msg.addButton("Install via winget", QMessageBox.ButtonRole.ActionRole)

    ffmpeg_btn = msg.addButton("Open ffmpeg.org", QMessageBox.ButtonRole.ActionRole)
    msg.addButton("Exit", QMessageBox.ButtonRole.RejectRole)

    msg.exec()
    clicked = msg.clickedButton()

    if winget_btn and clicked == winget_btn:
        _run_winget_install()
        return True

    if clicked == ffmpeg_btn:
        webbrowser.open("https://ffmpeg.org/download.html")

    return False


def _run_winget_install() -> None:
    """Launch winget in a new visible console window to install ffmpeg,
    then prompt the user to relaunch once it completes."""
    import subprocess

    from PySide6.QtWidgets import QMessageBox

    # Use /k (keep-open) so the window stays visible after winget finishes.
    # Passing the winget command as a single string to cmd /k avoids the
    # list2cmdline quoting issues that break && chaining with /c.
    try:
        subprocess.Popen(
            ["cmd", "/k", "winget install --id Gyan.FFmpeg -e"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except FileNotFoundError:
        QMessageBox.information(
            None,
            "winget not available",
            "winget was not found on this system.\n\n"
            "Please install ffmpeg manually:\n"
            "  • Download from https://ffmpeg.org/download.html\n"
            "  • Add the ffmpeg bin/ folder to your system PATH\n"
            "  • Restart AFCTUI",
        )
        return

    # winget runs asynchronously — wait for the user to signal completion
    # then relaunch so the fresh PATH is picked up.
    msg = QMessageBox()
    msg.setWindowTitle("Installing ffmpeg…")
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setText("ffmpeg is being installed in the console window.")
    msg.setInformativeText(
        "Wait for the installation to finish, then click Relaunch.\n\n"
        "The app will restart and pick up the new ffmpeg automatically."
    )
    relaunch_btn = msg.addButton("Relaunch", QMessageBox.ButtonRole.AcceptRole)
    msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
    msg.exec()

    if msg.clickedButton() == relaunch_btn:
        import os
        env = os.environ.copy()
        env["PATH"] = _fresh_windows_path()
        subprocess.Popen([sys.executable] + sys.argv, env=env)
        sys.exit(0)


def _fresh_windows_path() -> str:
    """Read the current system + user PATH from the registry.

    winget updates the registry but the change is not visible in the
    environment of the already-running process.  Spawning the relaunch
    with the registry values gives it the same PATH that a cold start
    of the exe would see.
    """
    import winreg

    parts: list[str] = []
    keys = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ]
    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as k:
                value, _ = winreg.QueryValueEx(k, "Path")
                if value:
                    parts.append(value)
        except OSError:
            pass
    return ";".join(parts) if parts else os.environ.get("PATH", "")

if __name__ == "__main__":
    main()

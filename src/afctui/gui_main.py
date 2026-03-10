"""Entry point for the AFCTUI Windows GUI application."""

from __future__ import annotations

import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("AFCTUI")
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
    import platform
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
    if platform.system() == "Windows":
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
    """Launch winget in a new visible console window to install ffmpeg."""
    import subprocess

    from PySide6.QtWidgets import QMessageBox

    # Use /k (keep-open) so the window stays visible after winget finishes.
    # Passing the winget command as a single string to cmd /k avoids the
    # list2cmdline quoting issues that break && chaining with /c.
    try:
        subprocess.Popen(
            ["cmd", "/k", "winget install --id gyan.dev.ffmpeg.full -e"],
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

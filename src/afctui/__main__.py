"""Entry point for AFCTUI."""

from __future__ import annotations

import sys


def main() -> None:
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

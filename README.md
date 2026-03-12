# AFCTUI — Audio File Converter

A cross-platform audio file converter with two interfaces:

- **TUI** (Linux / macOS) — terminal UI built with [Textual](https://textual.textualize.io/)
- **Windows GUI** — native desktop app built with PySide6, distributed as a standalone `.exe`

Both use system ffmpeg under the hood.

## Features

- **Drag and drop** — drop an audio file directly into the terminal (TUI); drag onto the window (GUI)
- **Audio playback** — play the original file and the converted output without leaving the app
- **Trim / scrubber** — visual timeline with adjustable start and end handles to convert only a portion of the file
- **Conversion options** — container format, codec, bitrate (hidden for lossless), mono/stereo channels
- **Presets** — save and load named conversion settings; four built-in presets included (★ = read-only)
- **Settings summary** — live one-line summary of active options displayed above the log
- **Progress tracking** — live progress bar and cancellation via `Escape`
- **Desktop integration** (TUI, Linux) — `--install-desktop` / `--uninstall-desktop` installs a `.desktop` entry and SVG icon

## Supported Formats

### Input
`.mp3` `.flac` `.wav` `.aac` `.ogg` `.opus` `.m4a` `.wma` `.aiff` `.alac` `.ape` `.mka`

### Output

| Format | Codecs |
|--------|--------|
| MP3 | libmp3lame |
| FLAC | flac |
| WAV | pcm_s16le, pcm_s24le, pcm_s32le, pcm_alaw\*, pcm_mulaw\* |
| AAC | aac, libfdk_aac |
| M4A | aac, libfdk_aac |
| OGG | libvorbis, libopus |
| OPUS | libopus |
| MKA | copy, libvorbis, libopus, aac |

\* `pcm_alaw` (G.711 A-law) and `pcm_mulaw` (G.711 μ-law) are telephony codecs fixed at 8000 Hz.

---

## Windows GUI (`afcgui.exe`)

A standalone desktop application — no Python or Textual required.

### ffmpeg

ffmpeg is **not** bundled in the exe. On first launch, if ffmpeg is not found the app offers:

- **Install via winget** — opens a console window and runs `winget install --id Gyan.FFmpeg`
- **Open ffmpeg.org** — opens the download page in your browser

Once ffmpeg is installed, restart the app.

### Building the exe

```bash
pip install pyinstaller ".[gui]"
pyinstaller afcgui.spec
```

The resulting executable is at `dist/afcgui.exe`.

### Building the installer

The project ships an [Inno Setup](https://jrsoftware.org/isinfo.php) script (`afcgui.iss`) that wraps the exe into a standard Windows installer:

```
iscc /DAppVersion=<version> afcgui.iss
# Output: dist/afcgui-setup-<version>.exe
```

The CI workflow (`.github/workflows/build-windows-exe.yml`) builds and uploads the installer automatically on tagged releases.

---

## TUI (Linux / macOS)

### Requirements

- Python 3.11+
- ffmpeg (includes ffplay and ffprobe) installed on your system

```bash
# Arch / Manjaro
sudo pacman -S ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# macOS
brew install ffmpeg
```

### Installation

```bash
pipx install git+https://github.com/Ripped-Kanga/AFCTUI.git
```

### Usage

```bash
afctui
```

### Desktop integration (Linux)

Install a `.desktop` launcher and SVG icon into `~/.local/share/`:

```bash
afctui --install-desktop    # install
afctui --uninstall-desktop  # remove
```

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+B` | Open file browser |
| `Ctrl+O` | Focus input path field |
| `Escape` | Cancel conversion in progress |
| `Q` | Quit |

### Scrubber controls

| Key | Action |
|-----|--------|
| `Tab` | Switch active handle (start / end) |
| `←` / `→` | Nudge active handle |
| `Home` | Jump active handle to its track boundary |
| `End` | Jump active handle to its track boundary |
| Click | Snap nearest handle to click position |
| Drag | Move active handle |

---

## Project Structure

```
src/afctui/
├── assets/
│   ├── afctui.ico    — Windows icon (7 sizes, 16–256 px)
│   └── afctui.svg    — Vector icon (Linux desktop integration)
├── __init__.py       — package version
├── __main__.py       — TUI entry point, ffmpeg check, --install-desktop
├── app.py            — main Textual application
├── app.tcss          — TUI stylesheet
├── browse.py         — FileBrowserScreen modal (_AudioTree, no hidden files)
├── converter.py      — ffmpeg/ffprobe wrapper, conversion logic
├── gui_app.py        — PySide6 main window (Windows GUI)
├── gui_main.py       — Windows GUI entry point
├── gui_scrubber.py   — PySide6 scrubber widget
├── player.py         — ffplay-based audio playback
├── presets.py        — preset storage: built-ins, load/save/delete
├── scrubber.py       — Textual scrubber widget (TUI trim timeline)
└── utils.py          — shared utilities: fmt_time, parse_trim_time, POPEN_FLAGS

afcgui.spec           — PyInstaller build spec for afcgui.exe
afcgui.iss            — Inno Setup installer script
```

## License

MIT

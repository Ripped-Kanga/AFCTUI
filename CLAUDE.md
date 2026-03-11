# AFCTUI — Codebase Summary

## Project Overview
**AFCTUI** (Audio File Converter) is a Python audio conversion application available in two interfaces:
- **TUI** (Linux/macOS) — terminal UI built with [Textual](https://textual.textualize.io/)
- **Windows GUI** — native desktop app built with PySide6, distributed as a standalone `.exe`

Both interfaces share a common conversion engine. Version 0.1.0, MIT licensed.

---

## ⚠️ No Functionality Divergence Rule

**The TUI (`app.py`) and the Windows GUI (`gui_app.py`) must remain functionally equivalent at all times.**

This is a hard rule. Specifically:

- Any new conversion option, format, codec, or user-facing feature added to one interface **must be added to the other**.
- Validation logic (accepted formats, codec/container combinations, trim clamping, file checks) must be **identical** in both.
- Log/status messages for the same events must carry the **same meaning**. Wording may differ to suit the interface style (Rich markup vs plain text), but the information conveyed must match.
- Bug fixes applied to one interface must be **assessed for applicability** to the other and applied if relevant.
- The shared layer (`converter.py`, `player.py`, `utils.py`) is the **single source of truth** for all business logic. Neither UI may re-implement logic that belongs there.
- `pcm_alaw` (and any future codec-specific constraints) are defined once in `converter.CODEC_CONSTRAINTS`. Both UIs read from this — they do not hard-code codec behaviour themselves.

When in doubt: if a user of the TUI and a user of the GUI perform the same steps, they must get the same result.

---

## Tech Stack
- **Python** >= 3.11
- **Textual** >= 8.0.0 — TUI framework (Linux/macOS only)
- **PySide6** >= 6.6 — GUI framework (Windows only)
- **ffmpeg** — system install required (probed at startup)
- **Build**: Hatchling (`pyproject.toml`)
- **Entry points**:
  - `afctui` → `afctui.__main__:main` (TUI)
  - `afcgui` → `afctui.gui_main:main` (Windows GUI)

## Source Layout
```
src/afctui/
├── __init__.py          # Package version
├── __main__.py          # TUI entry point (runs AFCApp)
├── app.py               # Main Textual App (TUI)
├── app.tcss             # Textual CSS stylesheet
├── browse.py            # FileBrowserScreen (DirectoryTree, no hidden files/folders)
├── converter.py         # ffmpeg wrapper: probe, convert, format/codec/bitrate options
├── gui_app.py           # Main PySide6 window (Windows GUI)
├── gui_main.py          # Windows GUI entry point, ffmpeg dependency handling
├── gui_scrubber.py      # PySide6 scrubber widget
├── player.py            # Audio playback via ffplay
├── presets.py           # Preset storage: built-ins, load/save/delete, platform paths
├── scrubber.py          # Textual scrubber widget (TUI)
└── utils.py             # Shared utilities: fmt_time, parse_trim_time, POPEN_FLAGS

afcgui.spec              # PyInstaller build spec for afcgui.exe
```

## Module Responsibilities

### `utils.py` — Shared Utilities
- **`fmt_time(seconds)`**: Formats seconds as `M:SS.s`. Used by both UIs and both scrubber widgets.
- **`parse_trim_time(value)`**: Parses `M:SS.s` or bare float strings into seconds. Used by both UIs.
- **`POPEN_FLAGS`**: `CREATE_NO_WINDOW` on Windows, empty dict on POSIX. Used by `converter.py` and `player.py`.

### `app.py` — TUI Application
- **`AFCApp`**: Root Textual `App`. Manages UI state, input validation, wires together all widgets.
  - Input path field + Browse button + drag-and-drop drop zone
  - Output path field (auto-derived from input; editable)
  - Conversion options: container format, codec, bitrate, channels (mono/stereo)
  - Playback controls: play original / play converted buttons
  - Conversion runs in a background thread via `@work(thread=True)`
  - Progress tracked via `ProgressBar`, logs written to `RichLog`
  - Cancel support via `Escape` key
  - `_converted_path` stores the last successful output path; never read from UI widgets in a background thread

### `gui_app.py` — Windows GUI Application
- **`AFCGuiApp`**: PySide6 `QMainWindow`. Feature-equivalent to `AFCApp`.
  - All long-running work runs in `QThread` subclasses (`_ProbeWorker`, `_ConversionWorker`, `_PlaybackWorker`)
  - Workers call `deleteLater()` on `finished` to prevent Qt memory leaks
  - Colour-coded log: errors in red (`#D94040`), warnings in amber (`#E8A000`), info in default
  - `_log_coloured(msg, colour)` is the single implementation; `_log_warn` and `_log_error` delegate to it

### `converter.py` — Conversion Engine
- **`AudioInfo`** dataclass: `duration`, `codec`, `bitrate`, `channels`, `sample_rate`
- **`ConversionOptions`** dataclass: `container`, `codec`, `bitrate`, `channels`, `extra_ffmpeg_args`
  - `extra_ffmpeg_args` allows callers to inject arbitrary ffmpeg flags without changing the signature
- **`SUPPORTED_INPUT_FORMATS`**: `.mp3 .flac .wav .aac .ogg .opus .m4a .wma .aiff .alac .ape .mka`
- **`OUTPUT_FORMATS`**: dict mapping container extension → list of compatible codecs
- **`CODEC_CONSTRAINTS`**: dict mapping codec → list of extra ffmpeg args applied automatically (e.g. `pcm_alaw` → `["-ar", "8000"]`)
- **`get_audio_info()`**: Probes with `ffprobe` (or `ffmpeg -i` fallback), parses JSON output
- **`convert_audio()`**: Runs ffmpeg conversion. Accepts optional `audio_info` to skip redundant re-probe.
  - Progress via `out_time_us=` from `ffmpeg -progress pipe:1`
  - Cancellation via `cancel_check` callback
- **`check_ffmpeg()`**: Validates `ffmpeg` and `ffplay` are available on `$PATH` at startup

### `browse.py` — File Browser (TUI only)
- **`FileBrowserScreen`**: Modal Textual screen with `_AudioTree` for audio-only file selection.
  - `_AudioTree` subclasses `DirectoryTree`, overrides `filter_paths()` to exclude hidden entries and non-audio files.
  - Fallback for platforms without drag-and-drop support.

### `player.py` — Audio Playback
- **`play_audio()`**: Launches `ffplay` non-blocking. Returns the `Popen` handle.
- **`stop_audio()`**: Terminates an active `ffplay` process gracefully.
- Used for both original file preview and post-conversion output preview.

### `scrubber.py` — TUI Scrubber Widget
- **`AudioScrubber`**: Custom Textual widget. Visual timeline with adjustable start/end trim handles.
- Emits `StartChanged` / `EndChanged` messages. Handles mouse and keyboard interaction.

### `gui_scrubber.py` — GUI Scrubber Widget
- **`AudioScrubberWidget`**: PySide6 equivalent of `AudioScrubber`.
- Emits `start_changed` / `end_changed` signals. Handles mouse and keyboard interaction.

### `presets.py` — Preset Storage
- **`BUILT_IN_PRESETS`**: Dict of read-only built-in presets (MP3 High Quality, Podcast Mono, Voice Mono, Lossless FLAC).
- **`get_presets_path()`**: Returns platform-appropriate path for `presets.json`:
  - Linux/macOS: `$XDG_DATA_HOME/afctui/presets.json` (falls back to `~/.local/share/afctui/presets.json`)
  - Windows: `%APPDATA%\AFCTUI\presets.json`
- **`all_presets()`**: Returns built-ins merged with user presets (user presets take precedence; built-ins first in output order).
- **`save_preset(name, container, codec, bitrate, channels)`**: Persists a named user preset.
- **`delete_preset(name)`**: Removes a user preset; no-op if name is a built-in or doesn't exist.
- **`is_builtin(name)`**: Returns True if name refers to a built-in preset.
- Both UIs display built-in presets with a `★` suffix to indicate they cannot be deleted.

## Conversion Options

### Container Formats & Compatible Codecs
| Container | Codecs |
|-----------|--------|
| `.mp3`    | libmp3lame |
| `.flac`   | flac |
| `.wav`    | pcm_s16le, pcm_s24le, pcm_s32le, pcm_alaw |
| `.aac` / `.m4a` | aac, libfdk_aac |
| `.ogg`    | libvorbis, libopus |
| `.opus`   | libopus |
| `.mka`    | copy, libvorbis, libopus, aac |

### Bitrate Options
Standard presets: 64k, 96k, 128k, 192k, 256k, 320k. Lossless formats (flac, wav) ignore bitrate.

### Channels
- Stereo (2 channels) — default
- Mono (1 channel) — downmix via ffmpeg `-ac 1`

## Key Design Patterns
- All long-running work (conversion, playback, file probing) runs in background threads. UI updates are marshalled back to the main thread (`call_from_thread` in TUI, Qt signals in GUI).
- `_converted_path` is always stored as an instance variable after a successful conversion. Neither UI reads the output path from a UI widget in a background thread.
- Codec select is dynamically repopulated when the container format changes; both UIs guard against spurious change events during repopulation.
- Bitrate select is hidden/disabled when a lossless container is selected.
- `CODEC_CONSTRAINTS` in `converter.py` is the single place to define per-codec forced ffmpeg args.
- ffmpeg and ffplay are sourced from the system `$PATH` — no bundled binary.
- Preset `_syncing_preset` flag prevents re-entrant events when presets programmatically set option widgets.
- Built-in presets are displayed with a `★` suffix in both UIs; only user-created presets can be deleted.

## Drag-and-Drop
- **TUI**: Textual's `on_paste` event handles file URIs pasted or dropped from a file manager.
- **GUI**: Qt drag-and-drop (`dragEnterEvent` / `dropEvent`) on the main window.
- Both accept only files with extensions in `SUPPORTED_INPUT_FORMATS`.

## Running / Installing

### TUI Prerequisites
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

### Install TUI via pipx (recommended)
```bash
pipx install git+https://github.com/Ripped-Kanga/AFCTUI.git
afctui
```

### Install for development
```bash
pip install -e .
afctui
```

### Building the Windows GUI exe
```bash
pip install pyinstaller ".[gui]"
pyinstaller afcgui.spec
# Output: dist/afcgui.exe
```

## ffmpeg Dependency Check
On startup, `check_ffmpeg()` verifies both `ffmpeg` and `ffplay` exist on `$PATH`. If missing:
- **TUI**: displays an error and exits with install instructions.
- **GUI**: shows a dialog offering one-click `winget` install or a link to ffmpeg.org.

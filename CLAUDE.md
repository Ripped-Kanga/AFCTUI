# AFCTUI — Codebase Summary

## Project Overview
**AFCTUI** (Audio File Converter TUI) is a Python terminal UI application for converting audio files between formats with playback support. Built with [Textual](https://textual.textualize.io/) and [ffmpeg](https://ffmpeg.org/) (via system install). Version 0.1.0, MIT licensed.

## Tech Stack
- **Python** >= 3.11
- **Textual** >= 8.0.0 — TUI framework
- **ffmpeg** — system install required (probed at startup)
- **Build**: Hatchling (`pyproject.toml`)
- **Entry point**: `afctui` CLI command → `afctui.__main__:main`

## Source Layout
```
src/afctui/
├── __init__.py
├── __main__.py          # Entry point (runs AFCApp)
├── app.py               # Main Textual App + modal screens
├── app.tcss             # Textual CSS stylesheet
├── browse.py            # FileBrowserScreen (DirectoryTree, no hidden files/folders)
├── converter.py         # ffmpeg wrapper: probe, convert, format/codec/bitrate options
└── player.py            # Audio playback (before/after conversion) via ffplay
```

## Module Responsibilities

### `app.py` — Main Application
- **`AFCApp`**: Root Textual `App`. Manages UI state, input validation, wires together all widgets.
  - Input path field + Browse button + drag-and-drop drop zone
  - Output path field (auto-derived from input; editable)
  - Conversion options: container format, codec, bitrate, channels (mono/stereo)
  - Playback controls: play original / play converted buttons
  - `ConversionOptions` widget (container, codec, bitrate, channels selects)
  - Conversion runs in a background thread via `@work(thread=True)`
  - Progress tracked via `ProgressBar`, logs written to `RichLog`
  - Cancel support via `Escape` key
- **`FileBrowserScreen`**: Modal Textual file browser. Uses `_AudioTree` (subclass of `DirectoryTree`) that:
  - Filters to supported audio formats only
  - Hides hidden files and folders (entries starting with `.`)

### `converter.py` — Conversion Engine
- **`AudioInfo`** dataclass: `duration`, `codec`, `bitrate`, `channels`, `sample_rate`
- **`ConversionOptions`** dataclass: `container`, `codec`, `bitrate`, `channels`
- **`SUPPORTED_INPUT_FORMATS`**: `.mp3 .flac .wav .aac .ogg .opus .m4a .wma .aiff .alac .ape .mka`
- **`OUTPUT_FORMATS`**: dict mapping container extension → list of compatible codecs
- **`get_audio_info()`**: Probes with `ffprobe` (or `ffmpeg -i`), parses JSON output
- **`convert_audio()`**: Runs ffmpeg conversion with provided `ConversionOptions`
  - Progress via `out_time_us=` from `ffmpeg -progress pipe:1`
  - Cancellation via `cancel_check` callback
- **`check_ffmpeg()`**: Validates `ffmpeg` and `ffplay` are available on `$PATH` at startup

### `browse.py` — File Browser
- **`FileBrowserScreen`**: Modal Textual screen with `_AudioTree` for audio-only file selection.
  - `_AudioTree` subclasses `DirectoryTree`, overrides `filter_paths()` to exclude hidden entries and non-audio files.
  - Fallback for platforms without drag-and-drop support.

### `player.py` — Audio Playback
- **`play_audio()`**: Launches `ffplay` in a background thread to play a given file. Returns a handle to stop playback.
- **`stop_audio()`**: Terminates an active `ffplay` process.
- Playback is non-blocking; UI remains responsive during playback.
- Used for both original file preview and post-conversion output preview.

## Conversion Options

### Container Formats & Compatible Codecs
| Container | Codecs |
|-----------|--------|
| `.mp3`    | libmp3lame |
| `.flac`   | flac |
| `.wav`    | pcm_s16le, pcm_s24le, pcm_s32le |
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
- All long-running work (conversion, playback, file probing) runs in background threads via Textual's `@work(thread=True)`. UI updates marshalled back via `call_from_thread`.
- Codec select is dynamically repopulated when the container format changes.
- Bitrate select is hidden/disabled when a lossless container is selected.
- Drag-and-drop is the primary input method; `FileBrowserScreen` is the fallback.
- `_AudioTree` must always hide hidden files/folders (`filter_paths` checks `path.name.startswith(".")`).
- ffmpeg and ffplay are sourced from the system `$PATH` — no bundled binary.

## Drag-and-Drop
- Textual's built-in `on_paste` or OS-level drag-and-drop events are used to accept file paths dropped onto the app.
- If drag-and-drop is unavailable (terminal does not support it), the Browse button opens `FileBrowserScreen`.

## Running / Installing
```bash
pip install -e .
afctui
```

### Prerequisites
```bash
# Arch / Manjaro
sudo pacman -S ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

## ffmpeg Dependency Check
On startup, `check_ffmpeg()` verifies both `ffmpeg` and `ffplay` exist on `$PATH`. If missing, the app displays an error and exits gracefully with instructions to install ffmpeg.

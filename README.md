# AFCTUI — Audio File Converter TUI

A terminal UI application for converting audio files between formats, with built-in playback and trim support. Built with [Textual](https://textual.textualize.io/) and system ffmpeg.

## Features

- **Drag and drop** — drop an audio file directly into the terminal; falls back to a built-in file browser (no hidden files or folders shown)
- **Audio playback** — play the original file and the converted output without leaving the app
- **Trim / scrubber** — visual timeline with adjustable start and end handles to convert only a portion of the file
- **Conversion options** — container format, codec, bitrate (hidden for lossless), mono/stereo channels
- **Progress tracking** — live progress bar and cancellation via `Escape`

## Supported Formats

### Input
`.mp3` `.flac` `.wav` `.aac` `.ogg` `.opus` `.m4a` `.wma` `.aiff` `.alac` `.ape` `.mka`

### Output

| Format | Codecs |
|--------|--------|
| MP3 | libmp3lame |
| FLAC | flac |
| WAV | pcm_s16le, pcm_s24le, pcm_s32le, pcm_alaw\* |
| AAC | aac, libfdk_aac |
| M4A | aac, libfdk_aac |
| OGG | libvorbis, libopus |
| OPUS | libopus |
| MKA | copy, libvorbis, libopus, aac |

\* `pcm_alaw` (G.711 A-law) is fixed at 8000 Hz, 8-bit — used for telephony.

## Requirements

- Python 3.11+
- ffmpeg (includes ffplay) installed on your system

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

## Installation

```bash
pipx install git+https://github.com/Ripped-Kanga/AFCTUI.git
```

## Usage

```bash
afctui
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

## Project Structure

```
src/afctui/
├── __init__.py      — package version
├── __main__.py      — entry point, ffmpeg startup check
├── app.py           — main Textual application
├── app.tcss         — stylesheet
├── browse.py        — FileBrowserScreen modal (_AudioTree, no hidden files)
├── converter.py     — ffmpeg/ffprobe wrapper, conversion logic
├── player.py        — ffplay-based audio playback
└── scrubber.py      — AudioScrubber widget (visual trim timeline)
```

## License

MIT

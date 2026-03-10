"""Audio conversion using system ffmpeg/ffprobe."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_TIME_PATTERN = re.compile(r"out_time_us=(\d+)")
_DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")

SUPPORTED_INPUT_FORMATS: frozenset[str] = frozenset({
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".opus",
    ".m4a", ".wma", ".aiff", ".alac", ".ape", ".mka",
})

OUTPUT_FORMATS: dict[str, list[str]] = {
    ".mp3":  ["libmp3lame"],
    ".flac": ["flac"],
    ".wav":  ["pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_alaw"],
    ".aac":  ["aac", "libfdk_aac"],
    ".m4a":  ["aac", "libfdk_aac"],
    ".ogg":  ["libvorbis", "libopus"],
    ".opus": ["libopus"],
    ".mka":  ["copy", "libvorbis", "libopus", "aac"],
}

LOSSLESS_CONTAINERS: frozenset[str] = frozenset({".flac", ".wav"})

BITRATE_OPTIONS: list[str] = ["64k", "96k", "128k", "192k", "256k", "320k"]
DEFAULT_BITRATE = "192k"


@dataclass
class AudioInfo:
    duration: float
    codec: str
    bitrate: Optional[int]  # bps, may be None
    channels: int
    sample_rate: int


@dataclass
class ConversionOptions:
    container: str    # e.g. ".mp3"
    codec: str        # e.g. "libmp3lame"
    bitrate: Optional[str]  # e.g. "192k", None for lossless
    channels: int     # 1 = mono, 2 = stereo


def check_ffmpeg() -> None:
    """Verify ffmpeg and ffplay are available on PATH.

    Raises RuntimeError with install instructions if either is missing.
    """
    missing = [tool for tool in ("ffmpeg", "ffplay") if not shutil.which(tool)]
    if missing:
        tools = " and ".join(missing)
        raise RuntimeError(
            f"{tools} not found on PATH.\n\n"
            "Install ffmpeg to use AFCTUI:\n"
            "  Windows:        winget install --id Gyan.FFmpeg\n"
            "  Arch/Manjaro:   sudo pacman -S ffmpeg\n"
            "  Ubuntu/Debian:  sudo apt install ffmpeg\n"
            "  Fedora:         sudo dnf install ffmpeg\n"
            "  macOS:          brew install ffmpeg"
        )


def get_audio_info(path: str | Path) -> AudioInfo:
    """Probe an audio file for metadata using ffprobe (falls back to ffmpeg -i)."""
    path = Path(path)
    ffprobe = shutil.which("ffprobe")

    if ffprobe:
        return _probe_with_ffprobe(ffprobe, path)
    return _probe_with_ffmpeg(path)


def _probe_with_ffprobe(ffprobe: str, path: Path) -> AudioInfo:
    result = subprocess.run(
        [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(path),
        ],
        capture_output=True, text=True, timeout=15,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"ffprobe returned invalid JSON: {e}") from e

    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise RuntimeError("No audio stream found in file")

    fmt = data.get("format", {})

    try:
        duration = float(fmt.get("duration") or audio_stream.get("duration") or 0)
    except (ValueError, TypeError):
        duration = 0.0

    codec = audio_stream.get("codec_name", "unknown")

    try:
        bitrate_str = audio_stream.get("bit_rate") or fmt.get("bit_rate")
        bitrate = int(bitrate_str) if bitrate_str else None
    except (ValueError, TypeError):
        bitrate = None

    try:
        channels = int(audio_stream.get("channels", 2))
    except (ValueError, TypeError):
        channels = 2

    try:
        sample_rate = int(audio_stream.get("sample_rate", 44100))
    except (ValueError, TypeError):
        sample_rate = 44100

    return AudioInfo(
        duration=duration,
        codec=codec,
        bitrate=bitrate,
        channels=channels,
        sample_rate=sample_rate,
    )


def _probe_with_ffmpeg(path: Path) -> AudioInfo:
    """Fallback probe using ffmpeg -i stderr parsing."""
    result = subprocess.run(
        ["ffmpeg", "-i", str(path)],
        capture_output=True, text=True, timeout=15,
    )
    stderr = result.stderr

    duration = 0.0
    dur_match = _DURATION_PATTERN.search(stderr)
    if dur_match:
        h, m, s = dur_match.group(1), dur_match.group(2), dur_match.group(3)
        duration = int(h) * 3600 + int(m) * 60 + float(s)

    codec = "unknown"
    channels = 2
    sample_rate = 44100
    bitrate = None

    # Parse audio stream line e.g.: Stream #0:0: Audio: mp3, 44100 Hz, stereo, fltp, 192 kb/s
    stream_match = re.search(r"Audio:\s+(\w+).*?(\d+)\s+Hz", stderr)
    if stream_match:
        codec = stream_match.group(1)
        sample_rate = int(stream_match.group(2))

    if "stereo" in stderr:
        channels = 2
    elif "mono" in stderr:
        channels = 1
    else:
        ch_match = re.search(r"(\d+)\s+channels?", stderr)
        if ch_match:
            channels = int(ch_match.group(1))

    br_match = re.search(r"(\d+)\s+kb/s", stderr)
    if br_match:
        bitrate = int(br_match.group(1)) * 1000

    return AudioInfo(
        duration=duration,
        codec=codec,
        bitrate=bitrate,
        channels=channels,
        sample_rate=sample_rate,
    )


def convert_audio(
    input_path: str | Path,
    output_path: str | Path,
    options: ConversionOptions,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> None:
    """Convert an audio file using ffmpeg with the given options.

    start_time and end_time are in seconds. When both are at the full
    file bounds (start=0, end=duration) no trim flags are added.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Probe duration for progress reporting and trim validation
    try:
        info = get_audio_info(input_path)
        duration = info.duration
    except Exception:
        duration = 0.0

    # Clamp trim bounds to the actual file duration
    trim_start = max(0.0, start_time)
    trim_end   = min(end_time, duration) if end_time is not None else duration
    trim_dur   = max(trim_end - trim_start, 0.0) if duration > 0 else duration

    cmd = ["ffmpeg", "-y", "-progress", "pipe:1", "-i", str(input_path)]

    cmd.extend(["-c:a", options.codec])

    if options.bitrate and options.container not in LOSSLESS_CONTAINERS and options.codec != "copy":
        cmd.extend(["-b:a", options.bitrate])

    # pcm_alaw is G.711 A-law: fixed 8000 Hz, 8-bit — enforce sample rate
    if options.codec == "pcm_alaw":
        cmd.extend(["-ar", "8000"])

    cmd.extend(["-ac", str(options.channels)])

    # Output-side trim: accurate sample-level seeking
    if trim_start > 0:
        cmd.extend(["-ss", f"{trim_start:.3f}"])
    if end_time is not None and trim_end < duration:
        cmd.extend(["-to", f"{trim_end:.3f}"])

    cmd.append(str(output_path))

    _run_ffmpeg(cmd, trim_dur or duration, progress_callback, cancel_check)


def is_audio_file(path: str | Path) -> bool:
    """Return True if the file has a supported audio extension."""
    return Path(path).suffix.lower() in SUPPORTED_INPUT_FORMATS


def _run_ffmpeg(
    cmd: list[str],
    duration: float,
    progress_callback: Optional[Callable[[float], None]],
    cancel_check: Optional[Callable[[], bool]],
) -> None:
    """Run an ffmpeg command and parse progress from stdout."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        for line in iter(process.stdout.readline, ""):
            if cancel_check and cancel_check():
                process.terminate()
                process.wait()
                return

            match = _TIME_PATTERN.search(line)
            if match and duration > 0 and progress_callback:
                current_us = int(match.group(1))
                current_s = current_us / 1_000_000
                pct = min((current_s / duration) * 100, 100)
                progress_callback(pct)

        process.wait()
        if process.returncode != 0:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"ffmpeg failed (exit {process.returncode}): {stderr}")
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

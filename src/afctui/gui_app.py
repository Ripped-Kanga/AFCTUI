"""AFCTUI Windows GUI — PySide6 main application window."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QShortcut, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from afctui.converter import (
    BITRATE_OPTIONS,
    CODEC_CONSTRAINTS,
    DEFAULT_BITRATE,
    LOSSLESS_CONTAINERS,
    OUTPUT_FORMATS,
    SUPPORTED_INPUT_FORMATS,
    AudioInfo,
    ConversionOptions,
    convert_audio,
    get_audio_info,
    is_audio_file,
)
from afctui.gui_scrubber import AudioScrubberWidget
from afctui.player import play_audio, stop_audio
from afctui.presets import (
    all_presets,
    delete_preset,
    load_user_presets,
    save_preset,
)
from afctui.utils import fmt_time, parse_trim_time


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class _ProbeWorker(QThread):
    result = Signal(object)  # AudioInfo
    error = Signal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            self.result.emit(get_audio_info(self._path))
        except Exception as exc:
            self.error.emit(str(exc))


class _ConversionWorker(QThread):
    progress = Signal(int)   # 0–100
    finished = Signal(bool)  # True = success, False = cancelled
    error = Signal(str)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        options: ConversionOptions,
        start_time: float,
        end_time: float | None,
        audio_info: AudioInfo | None = None,
    ) -> None:
        super().__init__()
        self._input = input_path
        self._output = output_path
        self._options = options
        self._start = start_time
        self._end = end_time
        self._audio_info = audio_info
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            convert_audio(
                self._input,
                self._output,
                self._options,
                self._start,
                self._end,
                progress_callback=lambda pct: self.progress.emit(min(int(pct), 100)),
                cancel_check=lambda: self._cancelled,
                audio_info=self._audio_info,
            )
            self.finished.emit(not self._cancelled)
        except Exception as exc:
            self.error.emit(str(exc))


class _PlaybackWorker(QThread):
    stopped = Signal()

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path
        self._process = None

    def stop(self) -> None:
        stop_audio(self._process)

    def run(self) -> None:
        self._process = play_audio(self._path)
        self._process.wait()
        self.stopped.emit()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class AFCGuiApp(QMainWindow):
    """PySide6 main window — feature-equivalent to the Textual AFCApp."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AFCGUI — Audio File Converter")
        self._apply_icon()
        self.setMinimumSize(720, 640)

        self._current_input_path: str | None = None
        self._audio_info: AudioInfo | None = None
        self._converting = False
        self._converted_path: str | None = None
        self._syncing_scrubber = False

        self._probe_worker: _ProbeWorker | None = None
        self._conversion_worker: _ConversionWorker | None = None
        self._playback_worker: _PlaybackWorker | None = None
        self._prev_codec: str = ""
        self._syncing_codec: bool = False
        self._syncing_preset: bool = False

        self._build_ui()
        self._connect_signals()
        self.setAcceptDrops(True)

        # Escape cancels an in-progress conversion
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_cancel)

        self._repopulate_preset_combo()
        self._refresh_settings_summary()
        self._log("Ready. Drop an audio file or click Browse to select one.")
        self._log("Supported input formats: " + ", ".join(sorted(SUPPORTED_INPUT_FORMATS)))

    # ------------------------------------------------------------------
    # Window icon
    # ------------------------------------------------------------------

    def _apply_icon(self) -> None:
        """Set the window/taskbar icon from the bundled ICO asset."""
        import sys
        # PyInstaller extracts to sys._MEIPASS; in dev, resolve from source tree
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        ico = base / "assets" / "afctui.ico"
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # ── Input row ─────────────────────────────────────────────────
        input_row = QHBoxLayout()
        lbl = QLabel("Input:")
        lbl.setFixedWidth(55)
        input_row.addWidget(lbl)
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("Path to audio file…")
        input_row.addWidget(self._input_edit, 1)
        self._browse_btn = QPushButton("Browse…")
        input_row.addWidget(self._browse_btn)
        root.addLayout(input_row)

        # ── Drop zone ─────────────────────────────────────────────────
        self._drop_label = QLabel("Drop an audio file here  /  paste a path in the field above")
        self._drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_label.setStyleSheet(
            "border: 2px dashed #888; border-radius: 4px;"
            "padding: 10px; color: #999;"
        )
        self._drop_label.setMinimumHeight(48)
        root.addWidget(self._drop_label)

        # ── Output row ────────────────────────────────────────────────
        output_row = QHBoxLayout()
        lbl = QLabel("Output:")
        lbl.setFixedWidth(55)
        output_row.addWidget(lbl)
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Output path (auto-derived)…")
        output_row.addWidget(self._output_edit, 1)
        root.addLayout(output_row)

        # ── Format / Codec / Bitrate / Channels row ───────────────────
        opts_row = QHBoxLayout()

        opts_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(160)
        opts_row.addWidget(self._preset_combo)

        opts_row.addWidget(QLabel("  Format:"))
        self._format_combo = QComboBox()
        for ext in OUTPUT_FORMATS:
            self._format_combo.addItem(ext.lstrip(".").upper(), ext)
        opts_row.addWidget(self._format_combo)

        opts_row.addWidget(QLabel("  Codec:"))
        self._codec_combo = QComboBox()
        self._repopulate_codec_combo(list(OUTPUT_FORMATS.keys())[0])
        opts_row.addWidget(self._codec_combo)

        self._bitrate_label = QLabel("  Bitrate:")
        opts_row.addWidget(self._bitrate_label)
        self._bitrate_combo = QComboBox()
        for b in BITRATE_OPTIONS:
            self._bitrate_combo.addItem(b, b)
        self._bitrate_combo.setCurrentText(DEFAULT_BITRATE)
        opts_row.addWidget(self._bitrate_combo)

        opts_row.addWidget(QLabel("  Channels:"))
        self._channels_combo = QComboBox()
        self._channels_combo.addItem("Stereo", 2)
        self._channels_combo.addItem("Mono", 1)
        opts_row.addWidget(self._channels_combo)

        opts_row.addStretch()
        root.addLayout(opts_row)

        # ── Scrubber ──────────────────────────────────────────────────
        self._scrubber = AudioScrubberWidget()
        root.addWidget(self._scrubber)

        # ── Trim inputs ───────────────────────────────────────────────
        trim_row = QHBoxLayout()
        trim_row.addWidget(QLabel("Start:"))
        self._trim_start_edit = QLineEdit("0:00.0")
        self._trim_start_edit.setFixedWidth(72)
        trim_row.addWidget(self._trim_start_edit)
        trim_row.addStretch()
        trim_row.addWidget(QLabel("End:"))
        self._trim_end_edit = QLineEdit("0:00.0")
        self._trim_end_edit.setFixedWidth(72)
        trim_row.addWidget(self._trim_end_edit)
        root.addLayout(trim_row)

        # ── Playback row ──────────────────────────────────────────────
        play_row = QHBoxLayout()
        self._play_orig_btn = QPushButton("Play Original")
        self._play_orig_btn.setEnabled(False)
        self._play_conv_btn = QPushButton("Play Converted")
        self._play_conv_btn.setEnabled(False)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        play_row.addWidget(self._play_orig_btn)
        play_row.addWidget(self._play_conv_btn)
        play_row.addWidget(self._stop_btn)
        play_row.addStretch()
        root.addLayout(play_row)

        # ── Convert button ────────────────────────────────────────────
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setFixedHeight(36)
        self._convert_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        root.addWidget(self._convert_btn)

        # ── Progress bar ──────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        root.addWidget(self._progress)

        mono = QFont()
        mono.setFamily("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(9)

        # ── Settings summary ──────────────────────────────────────────
        self._settings_label = QLabel()
        self._settings_label.setFont(mono)
        self._settings_label.setStyleSheet(
            "padding: 4px 6px;"
            "color: #aaaaaa;"
            "border-top: 1px solid #444;"
            "border-left: 1px solid #444;"
            "border-right: 1px solid #444;"
            "border-top-left-radius: 3px;"
            "border-top-right-radius: 3px;"
            "background: transparent;"
        )
        root.addWidget(self._settings_label)

        # ── Log ───────────────────────────────────────────────────────
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(mono)
        self._log_edit.setMinimumHeight(100)
        self._log_edit.setStyleSheet(
            "border-top: none;"
            "border-top-left-radius: 0;"
            "border-top-right-radius: 0;"
        )
        root.addWidget(self._log_edit, 1)

    def _repopulate_codec_combo(self, container_ext: str) -> None:
        self._syncing_codec = True
        self._codec_combo.clear()
        for codec in OUTPUT_FORMATS.get(container_ext, []):
            self._codec_combo.addItem(codec, codec)
        self._syncing_codec = False

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._browse_btn.clicked.connect(self._on_browse)
        self._convert_btn.clicked.connect(self._on_convert)
        self._play_orig_btn.clicked.connect(self._on_play_original)
        self._play_conv_btn.clicked.connect(self._on_play_converted)
        self._stop_btn.clicked.connect(self._on_stop_playback)

        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._codec_combo.currentIndexChanged.connect(self._on_codec_changed)
        self._bitrate_combo.currentIndexChanged.connect(self._refresh_settings_summary)
        self._channels_combo.currentIndexChanged.connect(self._refresh_settings_summary)

        self._input_edit.textChanged.connect(self._on_input_text_changed)
        self._input_edit.returnPressed.connect(self._on_input_submitted)

        self._trim_start_edit.textChanged.connect(self._on_trim_start_changed)
        self._trim_end_edit.textChanged.connect(self._on_trim_end_changed)

        self._scrubber.start_changed.connect(self._on_scrubber_start_changed)
        self._scrubber.end_changed.connect(self._on_scrubber_end_changed)

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and is_audio_file(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if is_audio_file(path):
                    self._set_input_file(path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    # ------------------------------------------------------------------
    # Input file handling
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_INPUT_FORMATS))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            str(Path.home()),
            f"Audio Files ({exts});;All Files (*)",
        )
        if path:
            self._set_input_file(path)

    def _set_input_file(self, path: str) -> None:
        resolved = str(Path(path).resolve())
        if self._current_input_path == resolved:
            return
        self._current_input_path = resolved
        self._converted_path = None
        self._play_conv_btn.setEnabled(False)

        self._syncing_scrubber = True
        self._input_edit.setText(path)
        self._syncing_scrubber = False

        self._update_output_path()
        self._log(f"Selected: {Path(path).name}")
        self._start_probe(resolved)

    def _update_output_path(self) -> None:
        if not self._current_input_path:
            return
        container = self._format_combo.currentData()
        self._output_edit.setText(str(Path(self._current_input_path).with_suffix(container)))

    def _on_input_text_changed(self, text: str) -> None:
        if self._syncing_scrubber:
            return
        path = text.strip().strip("'\"")
        if os.path.isfile(path) and is_audio_file(path):
            self._set_input_file(path)

    def _on_input_submitted(self) -> None:
        text = self._input_edit.text().strip().strip("'\"")
        if not text:
            return
        if os.path.isfile(text) and is_audio_file(text):
            self._set_input_file(text)
        elif os.path.isfile(text):
            self._log_warn(f"Unsupported format: {Path(text).suffix or '(none)'}")
        else:
            self._log_error(f"File not found: {text}")

    # ------------------------------------------------------------------
    # File probing
    # ------------------------------------------------------------------

    def _start_probe(self, path: str) -> None:
        if self._probe_worker and self._probe_worker.isRunning():
            self._probe_worker.quit()
        worker = _ProbeWorker(path)
        worker.result.connect(lambda info: self._on_probe_done(path, info))
        worker.error.connect(lambda e: self._log_error(f"Probe failed: {e}"))
        worker.finished.connect(worker.deleteLater)
        self._probe_worker = worker
        worker.start()

    def _on_probe_done(self, path: str, info: AudioInfo) -> None:
        self._audio_info = info
        self._play_orig_btn.setEnabled(True)

        self._syncing_scrubber = True
        self._scrubber.set_duration(info.duration)
        self._trim_start_edit.setText("0:00.0")
        self._trim_end_edit.setText(fmt_time(info.duration))
        self._syncing_scrubber = False

        bitrate_str = f"{info.bitrate // 1000}k" if info.bitrate else "unknown"
        mins, secs = divmod(info.duration, 60)
        self._log(
            f"{Path(path).name} — {info.codec}, "
            f"{info.channels}ch, {info.sample_rate} Hz, "
            f"{bitrate_str}, {int(mins)}m {secs:.1f}s"
        )

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    _SAVE_SENTINEL = "__SAVE__"
    _DELETE_SENTINEL = "__DELETE__"

    def _repopulate_preset_combo(self, select_name: str | None = None) -> None:
        """Rebuild the preset combo. Optionally re-select *select_name* after."""
        self._syncing_preset = True
        self._preset_combo.clear()
        self._preset_combo.addItem("(Select preset…)", None)

        presets = all_presets()
        user = load_user_presets()

        for name, _ in presets.items():
            label = name if name in user else f"{name}  ★"
            self._preset_combo.addItem(label, name)

        self._preset_combo.insertSeparator(self._preset_combo.count())
        self._preset_combo.addItem("Save as Preset…", self._SAVE_SENTINEL)
        self._preset_combo.addItem("Delete Preset…", self._DELETE_SENTINEL)

        if select_name is not None:
            idx = self._preset_combo.findData(select_name)
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)

        self._syncing_preset = False

    def _on_preset_changed(self, index: int) -> None:
        if self._syncing_preset:
            return
        data = self._preset_combo.itemData(index)
        if data is None:
            return
        if data == self._SAVE_SENTINEL:
            self._syncing_preset = True
            self._preset_combo.setCurrentIndex(0)
            self._syncing_preset = False
            self._do_save_preset()
        elif data == self._DELETE_SENTINEL:
            self._syncing_preset = True
            self._preset_combo.setCurrentIndex(0)
            self._syncing_preset = False
            self._do_delete_preset()
        else:
            presets = all_presets()
            if data in presets:
                self._apply_preset(data, presets[data])

    def _apply_preset(self, name: str, preset: dict) -> None:
        """Apply a preset's settings to all option combos."""
        self._syncing_preset = True

        container = preset.get("container", "")
        codec = preset.get("codec", "")
        bitrate = preset.get("bitrate")
        channels = preset.get("channels", 2)

        idx = self._format_combo.findData(container)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)
            self._repopulate_codec_combo(container)

        idx = self._codec_combo.findData(codec)
        if idx >= 0:
            self._codec_combo.setCurrentIndex(idx)

        if bitrate:
            idx = self._bitrate_combo.findData(bitrate)
            if idx >= 0:
                self._bitrate_combo.setCurrentIndex(idx)

        idx = self._channels_combo.findData(channels)
        if idx >= 0:
            self._channels_combo.setCurrentIndex(idx)

        self._update_bitrate_visibility()
        self._syncing_preset = False

        self._update_output_path()
        self._refresh_settings_summary()
        self._log(f"Preset loaded: {name}")

    def _do_save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        container = self._format_combo.currentData() or ""
        codec = self._codec_combo.currentData() or ""
        bitrate = self._bitrate_combo.currentData() if self._bitrate_combo.isVisible() else None
        channels = self._channels_combo.currentData() or 2
        save_preset(name, container, codec, bitrate, channels)
        self._repopulate_preset_combo(select_name=name)
        self._log(f"Preset saved: {name}")

    def _do_delete_preset(self) -> None:
        user = load_user_presets()
        if not user:
            QMessageBox.information(self, "Delete Preset", "You have no saved presets to delete.")
            return
        name, ok = QInputDialog.getItem(
            self, "Delete Preset", "Select preset to delete:",
            list(user.keys()), 0, False,
        )
        if not ok:
            return
        delete_preset(name)
        self._repopulate_preset_combo()
        self._log(f"Preset deleted: {name}")

    # ------------------------------------------------------------------
    # Format / codec / bitrate options
    # ------------------------------------------------------------------

    def _on_format_changed(self) -> None:
        container = self._format_combo.currentData()
        self._repopulate_codec_combo(container)
        self._update_bitrate_visibility()
        self._refresh_settings_summary()

        current_out = self._output_edit.text().strip()
        if current_out:
            self._output_edit.setText(str(Path(current_out).with_suffix(container)))
        elif self._current_input_path:
            self._output_edit.setText(str(Path(self._current_input_path).with_suffix(container)))

    def _on_codec_changed(self) -> None:
        if self._syncing_codec:
            return
        self._update_bitrate_visibility()
        codec = self._codec_combo.currentData() or ""
        if codec == self._prev_codec:
            return
        if codec in CODEC_CONSTRAINTS:
            self._log_warn(f"{codec}: output will be resampled to 8000 Hz, 8-bit.")
        elif self._prev_codec in CODEC_CONSTRAINTS:
            self._log("8000 Hz resampling constraint removed.")
        self._prev_codec = codec
        self._refresh_settings_summary()

    def _refresh_settings_summary(self) -> None:
        """Update the settings summary label above the log."""
        container = self._format_combo.currentData() or ""
        codec = self._codec_combo.currentData() or ""
        channels = self._channels_combo.currentData()

        fmt_name = container.lstrip(".").upper() or "—"
        channels_name = "Mono" if channels == 1 else "Stereo"

        lossless = container in LOSSLESS_CONTAINERS or codec == "copy"

        if codec in CODEC_CONSTRAINTS:
            codec_display = f"{codec}  ⚠ 8000 Hz (fixed)"
        else:
            codec_display = codec or "—"

        if lossless:
            text = f"Output:  {fmt_name}  ·  {codec_display}  ·  {channels_name}"
        else:
            bitrate = self._bitrate_combo.currentData() or "—"
            text = f"Output:  {fmt_name}  ·  {codec_display}  ·  {bitrate}  ·  {channels_name}"

        self._settings_label.setText(text)

    def _update_bitrate_visibility(self) -> None:
        container = self._format_combo.currentData() or ""
        codec = self._codec_combo.currentData() or ""
        show = container not in LOSSLESS_CONTAINERS and codec != "copy"
        self._bitrate_label.setVisible(show)
        self._bitrate_combo.setVisible(show)

    # ------------------------------------------------------------------
    # Scrubber ↔ trim input sync
    # ------------------------------------------------------------------

    def _on_scrubber_start_changed(self, value: float) -> None:
        if self._syncing_scrubber:
            return
        self._syncing_scrubber = True
        self._trim_start_edit.setText(fmt_time(value))
        self._syncing_scrubber = False

    def _on_scrubber_end_changed(self, value: float) -> None:
        if self._syncing_scrubber:
            return
        self._syncing_scrubber = True
        self._trim_end_edit.setText(fmt_time(value))
        self._syncing_scrubber = False

    def _on_trim_start_changed(self, text: str) -> None:
        if self._syncing_scrubber or self._scrubber.duration <= 0:
            return
        t = parse_trim_time(text)
        if t is not None:
            self._syncing_scrubber = True
            self._scrubber.set_start_time(t)
            self._syncing_scrubber = False

    def _on_trim_end_changed(self, text: str) -> None:
        if self._syncing_scrubber or self._scrubber.duration <= 0:
            return
        t = parse_trim_time(text)
        if t is not None:
            self._syncing_scrubber = True
            self._scrubber.set_end_time(t)
            self._syncing_scrubber = False

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _on_convert(self) -> None:
        if self._converting:
            self._log("Conversion already in progress.")
            return

        input_path = self._input_edit.text().strip().strip("'\"")
        if not input_path:
            self._log_warn("No input file specified.")
            return
        if not os.path.isfile(input_path):
            self._log_error(f"File not found: {input_path}")
            return
        if not is_audio_file(input_path):
            self._log_warn(f"Unsupported format: {Path(input_path).suffix}")
            return

        output_path = self._output_edit.text().strip()
        container = self._format_combo.currentData()
        if not output_path:
            output_path = str(Path(input_path).with_suffix(container))
            self._output_edit.setText(output_path)

        codec = self._codec_combo.currentData() or ""
        bitrate = self._bitrate_combo.currentData() if self._bitrate_combo.isVisible() else None
        channels = self._channels_combo.currentData()

        options = ConversionOptions(
            container=container,
            codec=codec,
            bitrate=bitrate,
            channels=channels,
        )

        start_time = self._scrubber.start_time if self._scrubber.duration > 0 else 0.0
        end_time = self._scrubber.end_time if self._scrubber.duration > 0 else None

        trim_info = ""
        if start_time > 0 or (
            end_time is not None
            and self._audio_info
            and end_time < self._audio_info.duration
        ):
            trim_info = f", trim {fmt_time(start_time)}→{fmt_time(end_time or 0)}"

        self._log(
            f"Converting to {container.lstrip('.')} "
            f"({codec}"
            + (f", {bitrate}" if bitrate else "")
            + f", {'mono' if channels == 1 else 'stereo'}"
            + trim_info + ")…"
        )

        self._converting = True
        self._convert_btn.setEnabled(False)
        self._convert_btn.setText("Converting…")
        self._progress.setValue(0)

        worker = _ConversionWorker(
            input_path, output_path, options, start_time, end_time,
            audio_info=self._audio_info,
        )
        worker.progress.connect(self._progress.setValue)
        worker.error.connect(self._on_conversion_error)
        worker.finished.connect(lambda ok: self._on_conversion_finished(ok, output_path))
        worker.finished.connect(worker.deleteLater)
        self._conversion_worker = worker
        worker.start()

    def _on_cancel(self) -> None:
        if self._converting and self._conversion_worker:
            self._conversion_worker.cancel()
            self._log("Cancelling conversion…")

    def _on_conversion_error(self, msg: str) -> None:
        self._log_error(f"Error: {msg}")
        self._converting = False
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("Convert")

    def _on_conversion_finished(self, success: bool, output_path: str) -> None:
        self._converting = False
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("Convert")

        if success:
            try:
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                self._log(f"Done! Saved to {output_path} ({size_mb:.1f} MB)")
            except OSError:
                self._log(f"Done! Saved to {output_path}")
            self._progress.setValue(100)
            self._converted_path = output_path
            self._play_conv_btn.setEnabled(True)
        else:
            self._log_warn("Conversion cancelled.")
            if os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _on_play_original(self) -> None:
        if not self._current_input_path:
            return
        self._stop_current_playback()
        self._play_orig_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        worker = _PlaybackWorker(self._current_input_path)
        worker.stopped.connect(self._on_playback_stopped)
        worker.finished.connect(worker.deleteLater)
        self._playback_worker = worker
        worker.start()

    def _on_play_converted(self) -> None:
        if not self._converted_path or not os.path.isfile(self._converted_path):
            self._log_error("Converted file not found.")
            return
        self._stop_current_playback()
        self._play_conv_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        worker = _PlaybackWorker(self._converted_path)
        worker.stopped.connect(self._on_playback_stopped)
        worker.finished.connect(worker.deleteLater)
        self._playback_worker = worker
        worker.start()

    def _on_stop_playback(self) -> None:
        self._stop_current_playback()

    def _stop_current_playback(self) -> None:
        if self._playback_worker and self._playback_worker.isRunning():
            self._playback_worker.stop()
            self._playback_worker.wait(2000)

    def _on_playback_stopped(self) -> None:
        self._play_orig_btn.setEnabled(self._current_input_path is not None)
        self._play_conv_btn.setEnabled(self._converted_path is not None)
        self._stop_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._stop_current_playback()
        if self._conversion_worker and self._conversion_worker.isRunning():
            self._conversion_worker.cancel()
            self._conversion_worker.wait(3000)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self._log_edit.append(msg)

    def _log_coloured(self, msg: str, colour: str) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colour))
        cursor = self._log_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(msg + "\n", fmt)
        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()

    def _log_warn(self, msg: str) -> None:
        self._log_coloured(msg, "#E8A000")

    def _log_error(self, msg: str) -> None:
        self._log_coloured(msg, "#D94040")

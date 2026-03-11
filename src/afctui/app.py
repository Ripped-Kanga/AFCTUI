"""AFCTUI — Audio File Converter TUI Application."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import unquote

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key, Paste
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Static,
)

from afctui.browse import FileBrowserScreen
from afctui.presets import (
    all_presets,
    delete_preset,
    load_user_presets,
    save_preset,
)
from afctui.scrubber import AudioScrubber
from afctui.utils import fmt_time, parse_trim_time
from afctui.converter import (
    BITRATE_OPTIONS,
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
from afctui.player import play_audio, stop_audio


_PRESET_SAVE = "__SAVE__"
_PRESET_DELETE = "__DELETE__"


class _PresetSaveScreen(ModalScreen[str | None]):
    """Modal dialog for entering a new preset name."""

    DEFAULT_CSS = """
    _PresetSaveScreen {
        align: center middle;
    }
    _PresetSaveScreen > Vertical {
        width: 52;
        height: auto;
        border: thick $panel;
        padding: 1 2;
        background: $surface;
    }
    _PresetSaveScreen Label {
        margin-bottom: 1;
    }
    _PresetSaveScreen Input {
        margin-bottom: 1;
    }
    _PresetSaveScreen .dialog-buttons {
        height: 3;
        layout: horizontal;
    }
    _PresetSaveScreen .dialog-buttons Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Enter a name for this preset:")
            yield Input(id="preset-name-input", placeholder="Preset name…")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Save", variant="primary", id="dialog-save-btn")
                yield Button("Cancel", id="dialog-cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#preset-name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dialog-save-btn":
            name = self.query_one("#preset-name-input", Input).value.strip()
            self.dismiss(name if name else None)
        else:
            self.dismiss(None)

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class _PresetDeleteScreen(ModalScreen[str | None]):
    """Modal dialog for selecting a user preset to delete."""

    DEFAULT_CSS = """
    _PresetDeleteScreen {
        align: center middle;
    }
    _PresetDeleteScreen > Vertical {
        width: 52;
        height: auto;
        border: thick $panel;
        padding: 1 2;
        background: $surface;
    }
    _PresetDeleteScreen Label {
        margin-bottom: 1;
    }
    _PresetDeleteScreen Select {
        margin-bottom: 1;
    }
    _PresetDeleteScreen .dialog-buttons {
        height: 3;
        layout: horizontal;
    }
    _PresetDeleteScreen .dialog-buttons Button {
        margin-right: 1;
    }
    """

    def __init__(self, user_preset_names: list[str]) -> None:
        super().__init__()
        self._names = user_preset_names

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Select a preset to delete:")
            yield Select(
                [(name, name) for name in self._names],
                value=self._names[0] if self._names else Select.BLANK,
                id="preset-delete-select",
                allow_blank=False,
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Delete", variant="error", id="dialog-delete-btn")
                yield Button("Cancel", id="dialog-cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dialog-delete-btn":
            val = self.query_one("#preset-delete-select", Select).value
            self.dismiss(str(val) if val != Select.BLANK else None)
        else:
            self.dismiss(None)

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class AFCApp(App):
    """Audio File Converter TUI Application."""

    TITLE = "AFCTUI — Audio File Converter"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+o", "focus_input", "Open", show=True),
        Binding("ctrl+b", "browse", "Browse", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._converting = False
        self._cancelled = False
        self._playback_process: subprocess.Popen | None = None
        self._audio_info: AudioInfo | None = None
        self._current_input_path: str | None = None
        self._converted_path: str | None = None
        self._syncing_scrubber = False
        self._syncing_preset = False
        self._prev_codec: str = ""

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="main-container"):
            # Input row
            with Horizontal(classes="field-row"):
                yield Label("Input:", classes="field-label")
                yield Input(
                    placeholder="Path to audio file...",
                    id="input-path",
                    classes="field-input",
                )
                yield Button("Browse", variant="primary", id="browse-btn", classes="browse-btn")

            # Drag-and-drop zone
            yield Static(
                "Drag and drop an audio file here\nor paste a file path",
                id="drop-zone",
            )

            # Output row
            with Horizontal(classes="field-row"):
                yield Label("Output:", classes="field-label")
                yield Input(
                    placeholder="Output path (auto-derived)...",
                    id="output-path",
                    classes="field-input",
                )

            # Preset row
            with Horizontal(id="preset-row", classes="field-row"):
                yield Label("Preset:", classes="field-label")
                yield Select(
                    [],
                    value=Select.BLANK,
                    id="preset-select",
                    allow_blank=True,
                    classes="field-input",
                )

            # Format row
            with Horizontal(id="format-row", classes="field-row"):
                yield Label("Format:", classes="field-label")
                yield Select(
                    [(ext.lstrip(".").upper(), ext) for ext in OUTPUT_FORMATS],
                    value=".mp3",
                    id="format-select",
                    allow_blank=False,
                    classes="field-input",
                )

            # Codec row
            with Horizontal(id="codec-row", classes="field-row"):
                yield Label("Codec:", classes="field-label")
                yield Select(
                    [(c, c) for c in OUTPUT_FORMATS[".mp3"]],
                    value=OUTPUT_FORMATS[".mp3"][0],
                    id="codec-select",
                    allow_blank=False,
                    classes="field-input",
                )

            # Bitrate row (hidden for lossless)
            with Horizontal(id="bitrate-row", classes="field-row"):
                yield Label("Bitrate:", classes="field-label")
                yield Select(
                    [(b, b) for b in BITRATE_OPTIONS],
                    value=DEFAULT_BITRATE,
                    id="bitrate-select",
                    allow_blank=False,
                    classes="field-input",
                )

            # Channels row
            with Horizontal(id="channels-row", classes="field-row"):
                yield Label("Channels:", classes="field-label")
                yield Select(
                    [("Stereo", 2), ("Mono", 1)],
                    value=2,
                    id="channels-select",
                    allow_blank=False,
                    classes="field-input",
                )

            # Scrubber
            yield AudioScrubber(id="scrubber")

            # Trim row
            with Horizontal(id="trim-row"):
                yield Label("Start:", classes="field-label")
                yield Input(value="0:00.0", id="trim-start", classes="trim-input")
                yield Label("End:", classes="field-label")
                yield Input(value="0:00.0", id="trim-end", classes="trim-input")

            # Playback row
            with Horizontal(id="playback-row"):
                yield Button("Play Original", id="play-original-btn", disabled=True)
                yield Button("Play Converted", id="play-converted-btn", disabled=True)
                yield Button("Stop", id="stop-btn", variant="error", disabled=True)

            yield Button("Convert", variant="primary", id="convert-btn")
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Static("", id="settings-summary")
            yield RichLog(highlight=True, markup=True, id="log")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#progress-bar", ProgressBar).update(progress=0)
        self._repopulate_preset_select()
        self._refresh_settings_summary()
        self.log_message("[dim]Ready. Drop an audio file or browse to select one.[/]")
        formats = ", ".join(sorted(SUPPORTED_INPUT_FORMATS))
        self.log_message(f"[dim]Supported input formats: {formats}[/]")

    # ------------------------------------------------------------------
    # Drag-and-drop via bracketed paste
    # ------------------------------------------------------------------

    def on_paste(self, event: Paste) -> None:
        text = event.text.strip()
        if not text:
            return

        # Strip file:// URI prefix
        if text.startswith("file://"):
            text = unquote(text[7:])

        # Take the first line (some terminals paste multiple paths)
        path = text.splitlines()[0].strip().strip("'\"")

        if not path or not os.path.isfile(path):
            return  # Plain text paste — ignore silently

        if is_audio_file(path):
            self.set_input_file(path)
        else:
            suffix = Path(path).suffix or "(none)"
            self.log_message(f"[red]Unsupported format:[/] {suffix}")

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------

    def set_input_file(self, path: str) -> None:
        """Set input path, auto-derive output, and probe the file."""
        resolved = str(Path(path).resolve())
        if self._current_input_path == resolved:
            return

        self._current_input_path = resolved
        self._converted_path = None
        self.query_one("#play-converted-btn", Button).disabled = True

        self.query_one("#input-path", Input).value = path
        self._update_output_path(path)
        self.log_message(f"Selected: [bold]{Path(path).name}[/]")
        self._probe_file(path)

    def _update_output_path(self, input_path: str) -> None:
        """Derive output path from input path + current format extension."""
        container = self.query_one("#format-select", Select).value
        output = str(Path(input_path).with_suffix(container))
        self.query_one("#output-path", Input).value = output

    @work(thread=True)
    def _probe_file(self, path: str) -> None:
        try:
            info = get_audio_info(path)
            self.call_from_thread(self._on_probe_complete, path, info)
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]Probe failed:[/] {e}")

    def _on_probe_complete(self, path: str, info: AudioInfo) -> None:
        self._audio_info = info
        self.query_one("#play-original-btn", Button).disabled = False

        # Initialise scrubber and trim inputs to full file duration
        scrubber = self.query_one("#scrubber", AudioScrubber)
        scrubber.duration   = info.duration
        scrubber.start_time = 0.0
        scrubber.end_time   = info.duration
        self._syncing_scrubber = True
        self.query_one("#trim-start", Input).value = "0:00.0"
        self.query_one("#trim-end",   Input).value = fmt_time(info.duration)
        self._syncing_scrubber = False

        bitrate_str = f"{info.bitrate // 1000}k" if info.bitrate else "unknown"
        mins, secs = divmod(info.duration, 60)
        self.log_message(
            f"[bold]{Path(path).name}[/] — {info.codec}, "
            f"{info.channels}ch, {info.sample_rate} Hz, "
            f"{bitrate_str}, {int(mins)}m {secs:.1f}s"
        )

    # ------------------------------------------------------------------
    # Dynamic options UI
    # ------------------------------------------------------------------

    @on(Select.Changed, "#format-select")
    def _on_format_changed(self, event: Select.Changed) -> None:
        container = event.value
        codecs = OUTPUT_FORMATS.get(container, [])

        codec_select = self.query_one("#codec-select", Select)
        codec_select.set_options([(c, c) for c in codecs])

        self.query_one("#bitrate-row").display = self._should_show_bitrate()
        self._refresh_settings_summary()

        current_output = self.query_one("#output-path", Input).value.strip()
        if current_output:
            self.query_one("#output-path", Input).value = str(Path(current_output).with_suffix(container))
        elif self._current_input_path:
            self.query_one("#output-path", Input).value = str(Path(self._current_input_path).with_suffix(container))

    @on(Select.Changed, "#codec-select")
    def _on_codec_changed(self, event: Select.Changed) -> None:
        self.query_one("#bitrate-row").display = self._should_show_bitrate()
        codec = str(event.value)
        if codec == self._prev_codec:
            return
        if codec == "pcm_alaw":
            self.log_message("[yellow]pcm_alaw (G.711 A-law): output will be resampled to 8000 Hz, 8-bit.[/]")
        elif self._prev_codec == "pcm_alaw":
            self.log_message("[dim]8000 Hz resampling constraint removed.[/]")
        self._prev_codec = codec
        self._refresh_settings_summary()

    @on(Select.Changed, "#bitrate-select")
    def _on_bitrate_changed(self, _event: Select.Changed) -> None:
        self._refresh_settings_summary()

    @on(Select.Changed, "#channels-select")
    def _on_channels_changed(self, _event: Select.Changed) -> None:
        self._refresh_settings_summary()

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def _repopulate_preset_select(self, select_name: str | None = None) -> None:
        """Rebuild the preset Select options."""
        presets = all_presets()
        user = load_user_presets()

        options: list[tuple[str, str]] = []
        for name in presets:
            label = name if name in user else f"{name}  ★"
            options.append((label, name))
        options.append(("Save as Preset…", _PRESET_SAVE))
        options.append(("Delete Preset…", _PRESET_DELETE))

        self._syncing_preset = True
        preset_select = self.query_one("#preset-select", Select)
        preset_select.set_options(options)
        if select_name is not None:
            preset_select.value = select_name
        else:
            preset_select.value = Select.BLANK
        self._syncing_preset = False

    @on(Select.Changed, "#preset-select")
    def _on_preset_changed(self, event: Select.Changed) -> None:
        if self._syncing_preset:
            return
        val = event.value
        if val == Select.BLANK:
            return
        val = str(val)
        if val == _PRESET_SAVE:
            # Reset combo to blank, then open save dialog
            self._syncing_preset = True
            self.query_one("#preset-select", Select).value = Select.BLANK
            self._syncing_preset = False
            self.push_screen(_PresetSaveScreen(), self._on_save_preset_result)
        elif val == _PRESET_DELETE:
            self._syncing_preset = True
            self.query_one("#preset-select", Select).value = Select.BLANK
            self._syncing_preset = False
            user = load_user_presets()
            if not user:
                self.log_message("[yellow]No saved presets to delete.[/]")
                return
            self.push_screen(_PresetDeleteScreen(list(user.keys())), self._on_delete_preset_result)
        else:
            presets = all_presets()
            if val in presets:
                self._apply_preset(val, presets[val])

    def _apply_preset(self, name: str, preset: dict) -> None:
        """Apply a preset's settings to all option selects."""
        container = preset.get("container", "")
        codec = preset.get("codec", "")
        bitrate = preset.get("bitrate")
        channels = preset.get("channels", 2)

        self._syncing_preset = True

        if container:
            self.query_one("#format-select", Select).value = container
            codecs = [(c, c) for c in OUTPUT_FORMATS.get(container, [])]
            self.query_one("#codec-select", Select).set_options(codecs)

        if codec:
            self.query_one("#codec-select", Select).value = codec

        if bitrate:
            self.query_one("#bitrate-select", Select).value = bitrate

        self.query_one("#channels-select", Select).value = channels

        self._syncing_preset = False

        self.query_one("#bitrate-row").display = self._should_show_bitrate()
        self._refresh_settings_summary()
        self.log_message(f"Preset loaded: [bold]{name}[/]")

    def _on_save_preset_result(self, name: str | None) -> None:
        if not name:
            return
        container = self.query_one("#format-select", Select).value
        codec = self.query_one("#codec-select", Select).value
        bitrate_visible = self.query_one("#bitrate-row").display
        bitrate = self.query_one("#bitrate-select", Select).value if bitrate_visible else None
        channels = self.query_one("#channels-select", Select).value
        save_preset(str(name), str(container), str(codec), bitrate, int(channels))
        self._repopulate_preset_select(select_name=name)
        self.log_message(f"Preset saved: [bold]{name}[/]")

    def _on_delete_preset_result(self, name: str | None) -> None:
        if not name:
            return
        delete_preset(name)
        self._repopulate_preset_select()
        self.log_message(f"Preset deleted: [bold]{name}[/]")

    def _refresh_settings_summary(self) -> None:
        """Update the settings summary line above the log."""
        container = self.query_one("#format-select", Select).value
        codec = self.query_one("#codec-select", Select).value
        channels = self.query_one("#channels-select", Select).value

        fmt_name = str(container).lstrip(".").upper()
        channels_name = "Mono" if channels == 1 else "Stereo"
        lossless = container in LOSSLESS_CONTAINERS or str(codec) == "copy"

        if str(codec) == "pcm_alaw":
            codec_display = "pcm_alaw  ⚠ 8000 Hz (fixed)"
        else:
            codec_display = str(codec)

        if lossless:
            text = f"Output:  {fmt_name}  ·  {codec_display}  ·  {channels_name}"
        else:
            bitrate = self.query_one("#bitrate-select", Select).value
            text = f"Output:  {fmt_name}  ·  {codec_display}  ·  {bitrate}  ·  {channels_name}"

        self.query_one("#settings-summary", Static).update(text)

    def _should_show_bitrate(self) -> bool:
        container = self.query_one("#format-select", Select).value
        if container in LOSSLESS_CONTAINERS:
            return False
        codec = self.query_one("#codec-select", Select).value
        return codec != "copy"

    # ------------------------------------------------------------------
    # Scrubber ↔ trim input sync
    # ------------------------------------------------------------------

    @on(AudioScrubber.StartChanged)
    def _on_scrubber_start_changed(self, event: AudioScrubber.StartChanged) -> None:
        if self._syncing_scrubber:
            return
        self._syncing_scrubber = True
        self.query_one("#trim-start", Input).value = fmt_time(event.value)
        self._syncing_scrubber = False

    @on(AudioScrubber.EndChanged)
    def _on_scrubber_end_changed(self, event: AudioScrubber.EndChanged) -> None:
        if self._syncing_scrubber:
            return
        self._syncing_scrubber = True
        self.query_one("#trim-end", Input).value = fmt_time(event.value)
        self._syncing_scrubber = False

    # ------------------------------------------------------------------
    # Input handlers
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-path" and event.value:
            path = event.value.strip().strip("'\"")
            if os.path.isfile(path) and is_audio_file(path):
                self.set_input_file(path)
            elif os.path.isfile(path):
                self.log_message(f"[red]Unsupported format:[/] {Path(path).suffix or '(none)'}")
            else:
                self.log_message(f"[red]File not found:[/] {path}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "output-path":
            return

        if event.input.id in ("trim-start", "trim-end") and not self._syncing_scrubber:
            scrubber = self.query_one("#scrubber", AudioScrubber)
            if scrubber.duration > 0:
                t = parse_trim_time(event.value)
                if t is not None:
                    self._syncing_scrubber = True
                    if event.input.id == "trim-start":
                        scrubber.start_time = max(0.0, min(t, scrubber.end_time - 0.1))
                    else:
                        scrubber.end_time = max(scrubber.start_time + 0.1, min(t, scrubber.duration))
                    self._syncing_scrubber = False
            return

        if event.input.id == "input-path" and event.value:
            path = event.value.strip().strip("'\"")
            if os.path.isfile(path) and is_audio_file(path):
                self.set_input_file(path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "browse-btn":
                self.action_browse()
            case "convert-btn":
                self.action_convert()
            case "play-original-btn":
                self._do_play_original()
            case "play-converted-btn":
                self._do_play_converted()
            case "stop-btn":
                self._do_stop_playback()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_input(self) -> None:
        self.query_one("#input-path", Input).focus()

    def action_browse(self) -> None:
        self.push_screen(FileBrowserScreen(), self._on_file_browser_result)

    def _on_file_browser_result(self, path: str | None) -> None:
        if path:
            self.set_input_file(path)
        else:
            self.log_message("[dim]No file selected.[/]")

    def action_cancel(self) -> None:
        if self._converting:
            self._cancelled = True
            self.log_message("[yellow]Cancelling conversion...[/]")

    def action_convert(self) -> None:
        if self._converting:
            self.log_message("[yellow]Conversion already in progress.[/]")
            return

        input_path = self.query_one("#input-path", Input).value.strip().strip("'\"")
        if not input_path:
            self.log_message("[red]No input file specified.[/]")
            return
        if not os.path.isfile(input_path):
            self.log_message(f"[red]File not found:[/] {input_path}")
            return
        if not is_audio_file(input_path):
            self.log_message(f"[red]Unsupported format:[/] {Path(input_path).suffix}")
            return

        output_path = self.query_one("#output-path", Input).value.strip()
        container = self.query_one("#format-select", Select).value
        if not output_path:
            output_path = str(Path(input_path).with_suffix(container))
            self.query_one("#output-path", Input).value = output_path

        codec = self.query_one("#codec-select", Select).value
        bitrate_row_visible = self.query_one("#bitrate-row").display
        bitrate = self.query_one("#bitrate-select", Select).value if bitrate_row_visible else None
        channels = self.query_one("#channels-select", Select).value

        options = ConversionOptions(
            container=container,
            codec=codec,
            bitrate=bitrate,
            channels=channels,
        )

        scrubber = self.query_one("#scrubber", AudioScrubber)
        start_time = scrubber.start_time if scrubber.duration > 0 else 0.0
        end_time   = scrubber.end_time   if scrubber.duration > 0 else None

        self._run_conversion(input_path, output_path, options, start_time, end_time)

    # ------------------------------------------------------------------
    # Conversion worker
    # ------------------------------------------------------------------

    @work(thread=True)
    def _run_conversion(
        self,
        input_path: str,
        output_path: str,
        options: ConversionOptions,
        start_time: float = 0.0,
        end_time: float | None = None,
    ) -> None:
        self._converting = True
        self._cancelled = False

        btn = self.query_one("#convert-btn", Button)
        self.call_from_thread(setattr, btn, "disabled", True)
        self.call_from_thread(setattr, btn, "label", "Converting...")

        progress_bar = self.query_one("#progress-bar", ProgressBar)
        self.call_from_thread(progress_bar.update, progress=0)

        trim_info = ""
        if start_time > 0 or (end_time is not None and self._audio_info and end_time < self._audio_info.duration):
            trim_info = f", trim {fmt_time(start_time)}→{fmt_time(end_time or 0)}"
        self.call_from_thread(
            self.log_message,
            f"Converting to [bold]{options.container.lstrip('.')}[/] "
            f"({options.codec}"
            + (f", {options.bitrate}" if options.bitrate else "")
            + f", {'mono' if options.channels == 1 else 'stereo'}"
            + trim_info + ")...",
        )

        def on_progress(pct: float) -> None:
            self.call_from_thread(progress_bar.update, progress=min(int(pct), 100))

        def check_cancel() -> bool:
            return self._cancelled

        try:
            convert_audio(
                input_path=input_path,
                output_path=output_path,
                options=options,
                start_time=start_time,
                end_time=end_time,
                progress_callback=on_progress,
                cancel_check=check_cancel,
                audio_info=self._audio_info,
            )

            if self._cancelled:
                self.call_from_thread(self.log_message, "[yellow]Conversion cancelled.[/]")
                if os.path.exists(output_path):
                    os.unlink(output_path)
            else:
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                self.call_from_thread(
                    self.log_message,
                    f"[green]Done![/] Saved to [bold]{output_path}[/] ({size_mb:.1f} MB)",
                )
                on_progress(100)
                self._converted_path = output_path
                play_btn = self.query_one("#play-converted-btn", Button)
                self.call_from_thread(setattr, play_btn, "disabled", False)

        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]Error:[/] {e}")
        finally:
            self._converting = False
            self._cancelled = False
            self.call_from_thread(setattr, btn, "disabled", False)
            self.call_from_thread(setattr, btn, "label", "Convert")

    # ------------------------------------------------------------------
    # Playback workers
    # ------------------------------------------------------------------

    @work(thread=True)
    def _do_play_original(self) -> None:
        if not self._current_input_path:
            return
        stop_audio(self._playback_process)
        self._playback_process = None

        btn = self.query_one("#play-original-btn", Button)
        stop_btn = self.query_one("#stop-btn", Button)
        self.call_from_thread(setattr, btn, "disabled", True)
        self.call_from_thread(setattr, stop_btn, "disabled", False)

        self._playback_process = play_audio(self._current_input_path)
        self._playback_process.wait()

        self.call_from_thread(setattr, btn, "disabled", False)
        self.call_from_thread(setattr, stop_btn, "disabled", True)

    @work(thread=True)
    def _do_play_converted(self) -> None:
        # Capture path before entering thread to avoid reading widget state
        # from a background thread.
        converted_path = self._converted_path
        if not converted_path or not os.path.isfile(converted_path):
            self.call_from_thread(self.log_message, "[red]Converted file not found.[/]")
            return
        stop_audio(self._playback_process)
        self._playback_process = None

        btn = self.query_one("#play-converted-btn", Button)
        stop_btn = self.query_one("#stop-btn", Button)
        self.call_from_thread(setattr, btn, "disabled", True)
        self.call_from_thread(setattr, stop_btn, "disabled", False)

        self._playback_process = play_audio(converted_path)
        self._playback_process.wait()

        self.call_from_thread(setattr, btn, "disabled", False)
        self.call_from_thread(setattr, stop_btn, "disabled", True)

    @work(thread=True)
    def _do_stop_playback(self) -> None:
        stop_audio(self._playback_process)
        self._playback_process = None
        stop_btn = self.query_one("#stop-btn", Button)
        self.call_from_thread(setattr, stop_btn, "disabled", True)

    def on_unmount(self) -> None:
        stop_audio(self._playback_process)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def log_message(self, message: str) -> None:
        self.query_one("#log", RichLog).write(message)

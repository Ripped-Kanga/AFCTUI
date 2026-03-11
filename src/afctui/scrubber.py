"""Audio scrubber widget for trim point selection."""

from __future__ import annotations

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.events import Key, MouseDown, MouseMove, MouseUp
from rich.text import Text

from afctui.utils import fmt_time


class AudioScrubber(Widget, can_focus=True):
    """Visual audio timeline with adjustable start and end trim handles.

    Keyboard:
      Tab         — switch active handle (start / end)
      Left/Right  — nudge active handle by ~0.5% of duration
      Home        — jump active handle to beginning / end of track
      End         — jump active handle to end of track
    Mouse:
      Click on bar   — snap nearest handle to click position
      Drag on bar    — drag the active handle
    """

    class StartChanged(Message):
        def __init__(self, value: float) -> None:
            super().__init__()
            self.value = value

    class EndChanged(Message):
        def __init__(self, value: float) -> None:
            super().__init__()
            self.value = value

    duration:   reactive[float] = reactive(0.0)
    start_time: reactive[float] = reactive(0.0)
    end_time:   reactive[float] = reactive(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._active_handle = "start"
        self._dragging = False

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _clamp(self, value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def _x_to_time(self, x: int) -> float:
        w = self.size.width
        if w <= 1 or self.duration <= 0:
            return 0.0
        return self._clamp(x / (w - 1) * self.duration, 0.0, self.duration)

    def _time_to_x(self, t: float) -> int:
        w = self.size.width
        if self.duration <= 0 or w <= 1:
            return 0
        return round(self._clamp(t / self.duration, 0.0, 1.0) * (w - 1))

    # ------------------------------------------------------------------
    # Rendering (4 lines inside the border)
    # ------------------------------------------------------------------

    def render(self) -> Text:
        w = self.size.width
        if w < 4:
            return Text()

        if self.duration <= 0:
            msg = "No audio loaded — select a file to enable trimming"
            return Text(msg[:w], style="dim", justify="center")

        start_x = self._time_to_x(self.start_time)
        end_x   = self._time_to_x(self.end_time)

        # ── Line 1: ruler ─────────────────────────────────────────────
        zero_lbl = "0:00.0"
        dur_lbl  = fmt_time(self.duration)
        gap      = w - len(zero_lbl) - len(dur_lbl)
        ruler    = zero_lbl + (" " * max(0, gap)) + dur_lbl

        # ── Line 2: bar ───────────────────────────────────────────────
        bar = Text()
        for i in range(w):
            if i == start_x:
                style = "bold green" if self._active_handle == "start" else "bold white"
                bar.append("[", style=style)
            elif i == end_x:
                style = "bold yellow" if self._active_handle == "end" else "bold white"
                bar.append("]", style=style)
            elif start_x < i < end_x:
                bar.append("█", style="blue")
            else:
                bar.append("─", style="dim")

        # ── Line 3: handle time labels positioned under handles ────────
        start_lbl = fmt_time(self.start_time)
        end_lbl   = fmt_time(self.end_time)

        cells = [" "] * w

        # Start label centred on handle, clamped to widget bounds
        sl = max(0, min(start_x - len(start_lbl) // 2, w - len(start_lbl)))
        for i, c in enumerate(start_lbl):
            if sl + i < w:
                cells[sl + i] = c

        # End label centred on handle, pushed right if it overlaps start label
        el = max(0, min(end_x - len(end_lbl) // 2, w - len(end_lbl)))
        if el < sl + len(start_lbl) + 1:
            el = sl + len(start_lbl) + 1
        for i, c in enumerate(end_lbl):
            if el + i < w:
                cells[el + i] = c

        label_line = "".join(cells)

        # ── Line 4: stats ─────────────────────────────────────────────
        sel_dur = max(0.0, self.end_time - self.start_time)
        active_name = "start" if self._active_handle == "start" else "end"
        stats = (
            f" Selected: {fmt_time(sel_dur)} of {fmt_time(self.duration)}"
            f"  |  active: {active_name} handle"
            f"  |  [Tab] switch  [← →] nudge"
        )

        result = Text()
        result.append(ruler + "\n", style="dim")
        result.append_text(bar)
        result.append("\n")
        result.append(label_line + "\n", style="dim")
        result.append(stats[:w], style="dim italic")
        return result

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def on_mouse_down(self, event: MouseDown) -> None:
        if self.duration <= 0:
            return
        self.capture_mouse()
        self._dragging = False  # first click snaps, then drag begins
        self._click_handle(event.x)
        self.focus()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not event.button and not self._dragging:
            return
        if self.duration <= 0:
            return
        self._dragging = True
        self._drag_active_handle(event.x)

    def on_mouse_up(self, _event: MouseUp) -> None:
        self._dragging = False
        self.release_mouse()

    def _click_handle(self, x: int) -> None:
        """Snap the nearest handle to x and make it active."""
        start_x = self._time_to_x(self.start_time)
        end_x   = self._time_to_x(self.end_time)
        t = self._x_to_time(x)

        if abs(x - start_x) <= abs(x - end_x):
            self._active_handle = "start"
            self.start_time = self._clamp(t, 0.0, self.end_time - 0.1)
            self.post_message(self.StartChanged(self.start_time))
        else:
            self._active_handle = "end"
            self.end_time = self._clamp(t, self.start_time + 0.1, self.duration)
            self.post_message(self.EndChanged(self.end_time))

    def _drag_active_handle(self, x: int) -> None:
        """Move the active handle to x."""
        t = self._x_to_time(x)
        if self._active_handle == "start":
            self.start_time = self._clamp(t, 0.0, self.end_time - 0.1)
            self.post_message(self.StartChanged(self.start_time))
        else:
            self.end_time = self._clamp(t, self.start_time + 0.1, self.duration)
            self.post_message(self.EndChanged(self.end_time))

    # ------------------------------------------------------------------
    # Keyboard interaction
    # ------------------------------------------------------------------

    def on_key(self, event: Key) -> None:
        if self.duration <= 0:
            return

        step = max(0.1, self.duration / 200)  # ~0.5% of duration, min 0.1s

        match event.key:
            case "tab":
                self._active_handle = "end" if self._active_handle == "start" else "start"
                self.refresh()
                event.prevent_default()

            case "left":
                if self._active_handle == "start":
                    self.start_time = self._clamp(self.start_time - step, 0.0, self.end_time - 0.1)
                    self.post_message(self.StartChanged(self.start_time))
                else:
                    self.end_time = self._clamp(self.end_time - step, self.start_time + 0.1, self.duration)
                    self.post_message(self.EndChanged(self.end_time))
                event.prevent_default()

            case "right":
                if self._active_handle == "start":
                    self.start_time = self._clamp(self.start_time + step, 0.0, self.end_time - 0.1)
                    self.post_message(self.StartChanged(self.start_time))
                else:
                    self.end_time = self._clamp(self.end_time + step, self.start_time + 0.1, self.duration)
                    self.post_message(self.EndChanged(self.end_time))
                event.prevent_default()

            case "home":
                if self._active_handle == "start":
                    self.start_time = 0.0
                    self.post_message(self.StartChanged(self.start_time))
                else:
                    # End handle: jump as far left as possible without crossing start
                    self.end_time = self.start_time + 0.1
                    self.post_message(self.EndChanged(self.end_time))
                event.prevent_default()

            case "end":
                if self._active_handle == "end":
                    self.end_time = self.duration
                    self.post_message(self.EndChanged(self.end_time))
                else:
                    # Start handle: jump as far right as possible without crossing end
                    self.start_time = self.end_time - 0.1
                    self.post_message(self.StartChanged(self.start_time))
                event.prevent_default()

"""PySide6 audio scrubber widget for trim point selection."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

def fmt_time(seconds: float) -> str:
    """Format seconds as M:SS.s"""
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:04.1f}"


class AudioScrubberWidget(QWidget):
    """Visual audio timeline with adjustable start/end trim handles.

    Keyboard:
      Tab        — switch active handle (start / end)
      Left/Right — nudge active handle by ~0.5% of duration
      Home       — jump active handle to beginning / far boundary
      End        — jump active handle to end / far boundary
    Mouse:
      Click      — snap nearest handle to click position
      Drag       — drag the active handle
    """

    start_changed = Signal(float)
    end_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._duration = 0.0
        self._start_time = 0.0
        self._end_time = 0.0
        self._active_handle = "start"
        self._dragging = False

        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_duration(self, d: float) -> None:
        self._duration = max(0.0, d)
        self._start_time = 0.0
        self._end_time = self._duration
        self.update()

    def set_start_time(self, t: float) -> None:
        self._start_time = self._clamp(t, 0.0, self._end_time - 0.1)
        self.update()

    def set_end_time(self, t: float) -> None:
        self._end_time = self._clamp(t, self._start_time + 0.1, self._duration)
        self.update()

    @property
    def start_time(self) -> float:
        return self._start_time

    @property
    def end_time(self) -> float:
        return self._end_time

    @property
    def duration(self) -> float:
        return self._duration

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def _time_to_px(self, t: float) -> int:
        w = self.width()
        if self._duration <= 0 or w <= 1:
            return 0
        return round(self._clamp(t / self._duration, 0.0, 1.0) * (w - 1))

    def _px_to_time(self, x: int) -> float:
        w = self.width()
        if w <= 1 or self._duration <= 0:
            return 0.0
        return self._clamp(x / (w - 1) * self._duration, 0.0, self._duration)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()
        row_h = h // 4

        # Background
        painter.fillRect(self.rect(), self.palette().base())

        # Border (accent when focused, dim otherwise)
        border_color = QColor("#2196F3") if self.hasFocus() else QColor("#666666")
        painter.setPen(QPen(border_color, 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        dim = QColor("#888888")

        if self._duration <= 0:
            painter.setPen(dim)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No audio loaded — select a file to enable trimming",
            )
            return

        start_x = self._time_to_px(self._start_time)
        end_x = self._time_to_px(self._end_time)

        # ── Row 1: ruler ──────────────────────────────────────────────
        y0 = 2
        painter.setPen(dim)
        painter.drawText(
            QRect(4, y0, w // 2, row_h - 2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "0:00.0",
        )
        painter.drawText(
            QRect(w // 2, y0, w // 2 - 4, row_h - 2),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            fmt_time(self._duration),
        )

        # ── Row 2: bar ────────────────────────────────────────────────
        y1 = row_h
        bar_h = row_h
        bar_mid = y1 + bar_h // 2

        # Unselected left track
        if start_x > 4:
            painter.fillRect(4, bar_mid - 1, start_x - 4, 2, dim)

        # Selected region fill
        if end_x > start_x:
            painter.fillRect(
                start_x, y1 + 2, end_x - start_x, bar_h - 4,
                QColor(50, 130, 220, 100),
            )

        # Unselected right track
        if end_x < w - 4:
            painter.fillRect(end_x, bar_mid - 1, w - 4 - end_x, 2, dim)

        # Start handle [ — green when active, grey otherwise
        start_color = QColor("#4CAF50") if self._active_handle == "start" else QColor("#BBBBBB")
        pen = QPen(start_color, 2)
        painter.setPen(pen)
        painter.drawLine(start_x, y1, start_x, y1 + bar_h)
        painter.drawLine(start_x, y1, start_x + 6, y1)
        painter.drawLine(start_x, y1 + bar_h, start_x + 6, y1 + bar_h)

        # End handle ] — amber when active, grey otherwise
        end_color = QColor("#FFC107") if self._active_handle == "end" else QColor("#BBBBBB")
        pen = QPen(end_color, 2)
        painter.setPen(pen)
        painter.drawLine(end_x, y1, end_x, y1 + bar_h)
        painter.drawLine(end_x - 6, y1, end_x, y1)
        painter.drawLine(end_x - 6, y1 + bar_h, end_x, y1 + bar_h)

        # ── Row 3: handle time labels ─────────────────────────────────
        y2 = y1 + bar_h
        fm = painter.fontMetrics()
        start_lbl = fmt_time(self._start_time)
        end_lbl = fmt_time(self._end_time)
        sl_w = fm.horizontalAdvance(start_lbl)
        el_w = fm.horizontalAdvance(end_lbl)

        sl_x = max(0, min(start_x - sl_w // 2, w - sl_w))
        el_x = max(0, min(end_x - el_w // 2, w - el_w))
        if el_x < sl_x + sl_w + 4:
            el_x = sl_x + sl_w + 4

        painter.setPen(dim)
        painter.drawText(QRect(sl_x, y2, sl_w + 2, row_h), Qt.AlignmentFlag.AlignLeft, start_lbl)
        painter.drawText(QRect(el_x, y2, el_w + 2, row_h), Qt.AlignmentFlag.AlignLeft, end_lbl)

        # ── Row 4: stats ──────────────────────────────────────────────
        y3 = y2 + row_h
        sel_dur = max(0.0, self._end_time - self._start_time)
        active_name = "start" if self._active_handle == "start" else "end"
        stats = (
            f" Selected: {fmt_time(sel_dur)} of {fmt_time(self._duration)}"
            f"  |  active: {active_name} handle"
            f"  |  [Tab] switch  [\u2190 \u2192] nudge"
        )
        painter.drawText(
            QRect(0, y3, w, row_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            stats,
        )

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if self._duration <= 0:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._click_handle(int(event.position().x()))
            self.setFocus()

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._duration <= 0:
            return
        self._dragging = True
        self._drag_active_handle(int(event.position().x()))

    def mouseReleaseEvent(self, _event) -> None:
        self._dragging = False

    def _click_handle(self, x: int) -> None:
        start_x = self._time_to_px(self._start_time)
        end_x = self._time_to_px(self._end_time)
        t = self._px_to_time(x)

        if abs(x - start_x) <= abs(x - end_x):
            self._active_handle = "start"
            self._start_time = self._clamp(t, 0.0, self._end_time - 0.1)
            self.start_changed.emit(self._start_time)
        else:
            self._active_handle = "end"
            self._end_time = self._clamp(t, self._start_time + 0.1, self._duration)
            self.end_changed.emit(self._end_time)
        self.update()

    def _drag_active_handle(self, x: int) -> None:
        t = self._px_to_time(x)
        if self._active_handle == "start":
            self._start_time = self._clamp(t, 0.0, self._end_time - 0.1)
            self.start_changed.emit(self._start_time)
        else:
            self._end_time = self._clamp(t, self._start_time + 0.1, self._duration)
            self.end_changed.emit(self._end_time)
        self.update()

    # ------------------------------------------------------------------
    # Keyboard interaction
    # ------------------------------------------------------------------

    def event(self, event) -> bool:
        """Intercept Tab before Qt moves focus away."""
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            self._active_handle = "end" if self._active_handle == "start" else "start"
            self.update()
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event) -> None:
        if self._duration <= 0:
            super().keyPressEvent(event)
            return

        step = max(0.1, self._duration / 200)
        k = event.key()

        if k == Qt.Key.Key_Left:
            if self._active_handle == "start":
                self._start_time = self._clamp(self._start_time - step, 0.0, self._end_time - 0.1)
                self.start_changed.emit(self._start_time)
            else:
                self._end_time = self._clamp(self._end_time - step, self._start_time + 0.1, self._duration)
                self.end_changed.emit(self._end_time)
            self.update()
            event.accept()

        elif k == Qt.Key.Key_Right:
            if self._active_handle == "start":
                self._start_time = self._clamp(self._start_time + step, 0.0, self._end_time - 0.1)
                self.start_changed.emit(self._start_time)
            else:
                self._end_time = self._clamp(self._end_time + step, self._start_time + 0.1, self._duration)
                self.end_changed.emit(self._end_time)
            self.update()
            event.accept()

        elif k == Qt.Key.Key_Home:
            if self._active_handle == "start":
                self._start_time = 0.0
                self.start_changed.emit(self._start_time)
            else:
                self._end_time = self._start_time + 0.1
                self.end_changed.emit(self._end_time)
            self.update()
            event.accept()

        elif k == Qt.Key.Key_End:
            if self._active_handle == "end":
                self._end_time = self._duration
                self.end_changed.emit(self._end_time)
            else:
                self._start_time = self._end_time - 0.1
                self.start_changed.emit(self._start_time)
            self.update()
            event.accept()

        else:
            super().keyPressEvent(event)

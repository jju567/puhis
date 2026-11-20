"""Kelluva, fokusta varastamaton puhekupla kissan yläpuolella."""

from enum import StrEnum

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import QWidget

from puhis.platform.win32_window import apply_floating_tool_style


class BubbleTone(StrEnum):
    """Puhekuplan värikorostuksen tyyppi."""

    PROCESSING = "processing"
    COMMAND = "command"
    DICTATING = "dictating"
    ERROR = "error"


_BORDER_COLORS: dict[BubbleTone, QColor] = {
    BubbleTone.PROCESSING: QColor("#FBBF24"),
    BubbleTone.COMMAND: QColor("#00E676"),
    BubbleTone.DICTATING: QColor("#2ECC71"),
    BubbleTone.ERROR: QColor("#F87171"),
}

_ACCENT_TEXT_COLORS: dict[BubbleTone, QColor] = {
    BubbleTone.PROCESSING: QColor("#FDE68A"),
    BubbleTone.COMMAND: QColor("#6EE7B7"),
    BubbleTone.DICTATING: QColor("#86EFAC"),
    BubbleTone.ERROR: QColor("#FCA5A5"),
}

BUBBLE_BG = QColor(20, 24, 33, 238)
HEARD_TEXT_COLOR = QColor("#F8FAFC")
MIN_WIDTH = 170
MAX_WIDTH = 340
PADDING_X = 14
PADDING_Y = 9
TAIL_HEIGHT = 8
CAT_GAP = 6


class SpeechBubble(QWidget):
    """Näyttää kissan vieressä, mitä puhetta tunnistettiin ja mitä komentoa suoritetaan."""

    def __init__(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._heard_line = ""
        self._action_line = ""
        self._tone = BubbleTone.COMMAND
        self._anchor_rect = QRect()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(
        self,
        heard_line: str,
        action_line: str,
        tone: BubbleTone,
        anchor_rect: QRect,
        *,
        duration_ms: int = 3800,
    ) -> None:
        """Näyttää puhekuplan annetun kissa-alueen (`anchor_rect`) yläpuolella."""
        self._heard_line = heard_line.strip()
        self._action_line = action_line.strip()
        self._tone = tone
        self._anchor_rect = QRect(anchor_rect)

        self._recalculate_geometry()
        self.update()
        if not self.isVisible():
            self.show()

        self._hide_timer.stop()
        if duration_ms > 0:
            self._hide_timer.start(duration_ms)

    def update_anchor(self, anchor_rect: QRect) -> None:
        """Siirtää puhekuplan seuraamaan kissan uutta sijaintia."""
        self._anchor_rect = QRect(anchor_rect)
        if self.isVisible():
            self._reposition()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        apply_floating_tool_style(int(self.winId()))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            border_color = _BORDER_COLORS.get(self._tone, _BORDER_COLORS[BubbleTone.COMMAND])
            accent_color = _ACCENT_TEXT_COLORS.get(self._tone, _ACCENT_TEXT_COLORS[BubbleTone.COMMAND])

            box_rect = QRectF(2.0, 2.0, self.width() - 4.0, self.height() - TAIL_HEIGHT - 4.0)
            path = QPainterPath()
            path.addRoundedRect(box_rect, 11.0, 11.0)

            # Pieni puhekuplan kärki osoittamaan kissaa kohti.
            cx = box_rect.center().x()
            by = box_rect.bottom()
            tail = QPainterPath()
            tail.moveTo(QPointF(cx - 7.0, by))
            tail.lineTo(QPointF(cx, by + TAIL_HEIGHT))
            tail.lineTo(QPointF(cx + 7.0, by))
            tail.closeSubpath()
            full_path = path.united(tail)

            pen = QPen(border_color, 2.2)
            painter.setPen(pen)
            painter.setBrush(BUBBLE_BG)
            painter.drawPath(full_path)

            heard_font = QFont("Segoe UI", 9, QFont.Weight.Normal)
            action_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            text_left = int(box_rect.left()) + PADDING_X
            text_width = int(box_rect.width()) - 2 * PADDING_X
            y_cursor = int(box_rect.top()) + PADDING_Y

            if self._heard_line:
                painter.setFont(heard_font)
                painter.setPen(HEARD_TEXT_COLOR)
                fm_heard = QFontMetrics(heard_font)
                elided_heard = fm_heard.elidedText(
                    self._heard_line,
                    Qt.TextElideMode.ElideRight,
                    text_width,
                )
                painter.drawText(
                    QRect(text_left, y_cursor, text_width, fm_heard.height()),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    elided_heard,
                )
                y_cursor += fm_heard.height() + 3

            if self._action_line:
                painter.setFont(action_font)
                painter.setPen(accent_color)
                fm_action = QFontMetrics(action_font)
                elided_action = fm_action.elidedText(
                    self._action_line,
                    Qt.TextElideMode.ElideRight,
                    text_width,
                )
                painter.drawText(
                    QRect(text_left, y_cursor, text_width, fm_action.height()),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    elided_action,
                )
        finally:
            painter.end()

    def _recalculate_geometry(self) -> None:
        heard_font = QFont("Segoe UI", 9, QFont.Weight.Normal)
        action_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        fm_heard = QFontMetrics(heard_font)
        fm_action = QFontMetrics(action_font)

        w_heard = fm_heard.horizontalAdvance(self._heard_line) if self._heard_line else 0
        w_action = fm_action.horizontalAdvance(self._action_line) if self._action_line else 0
        content_w = max(w_heard, w_action)
        width = max(MIN_WIDTH, min(MAX_WIDTH, content_w + 2 * PADDING_X + 12))

        height = 2 * PADDING_Y + TAIL_HEIGHT + 6
        if self._heard_line:
            height += fm_heard.height()
        if self._action_line:
            height += fm_action.height()
        if self._heard_line and self._action_line:
            height += 3

        self.setFixedSize(width, height)
        self._reposition()

    def _reposition(self) -> None:
        if self._anchor_rect.isNull():
            return
        x = self._anchor_rect.center().x() - self.width() // 2
        y = self._anchor_rect.top() - self.height() - CAT_GAP

        screen = QGuiApplication.screenAt(self._anchor_rect.center()) or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left() + 8, min(area.right() - self.width() - 8, x))
            if y < area.top() + 8:
                y = self._anchor_rect.bottom() + CAT_GAP

        self.move(QPoint(x, y))

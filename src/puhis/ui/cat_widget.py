"""Kelluva, fokusta varastamaton kissa-widget, jonka silmät seuraavat hiirtä."""

import logging
import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QContextMenuEvent, QCursor, QHideEvent, QMouseEvent, QMoveEvent, QPainter, QPaintEvent, QShowEvent
from PySide6.QtWidgets import QApplication, QWidget

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import CatTheme
from puhis.core.eye_math import pupil_offset
from puhis.platform.win32_window import apply_floating_tool_style
from puhis.ui.cat_painter import CatGeometry, Offset, paint_cat

logger = logging.getLogger(__name__)

# ~30 FPS riittää sulavaan silmien liikkeeseen ja hehkun sykkeeseen.
GAZE_INTERVAL_MS = 33
# Pyöristys estää turhat uudelleenpiirrot, kun kursori liikkuu vain murto-osan.
PUPIL_PRECISION = 1
BLINK_DURATION_MS = 140
BLINK_MIN_DELAY_MS = 4000
BLINK_MAX_DELAY_MS = 7000
_PULSING_MODES = frozenset({AssistantMode.DICTATING, AssistantMode.COMMAND, AssistantMode.ERROR})


class CatWidget(QWidget):
    """Kehyksetön, läpinäkyvä ja aina päällimmäisenä oleva kissa."""

    clicked = Signal()
    context_menu_requested = Signal(QPoint)
    position_committed = Signal(QPoint)
    geometry_changed = Signal(QRect)

    def __init__(self, size: int, theme: CatTheme = CatTheme.CHARCOAL) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(size, size)
        self.setToolTip("Puhis")

        self._geometry = CatGeometry(float(size))
        self._mode = AssistantMode.IDLE
        self._theme = theme
        self._badge_text = ""
        self._processing = False
        self._sleeping = False
        self._spinner_angle = 0.0
        self._pupils: tuple[Offset, Offset] = ((0.0, 0.0), (0.0, 0.0))
        self._blinking = False
        self._pulse_phase = 0.0
        self._press_global: QPoint | None = None
        self._drag_offset = QPoint()
        self._dragging = False

        self._gaze_timer = QTimer(self)
        self._gaze_timer.setInterval(GAZE_INTERVAL_MS)
        self._gaze_timer.timeout.connect(self._on_tick)

        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._on_blink_tick)

    def set_mode(self, mode: AssistantMode) -> None:
        """Päivittää kissan ulkoasun vastaamaan avustimen tilaa."""
        if mode is self._mode:
            return
        self._mode = mode
        self.update()

    def set_theme(self, theme: CatTheme) -> None:
        """Vaihtaa kissan turkin väriteeman."""
        if theme is self._theme:
            return
        self._theme = theme
        self.update()

    def set_cat_size(self, size: int) -> None:
        """Muuttaa kissan koon lennossa."""
        if size == self.width():
            return
        self._geometry = CatGeometry(float(size))
        self.setFixedSize(size, size)
        self.update()
        self.geometry_changed.emit(self.geometry())

    def set_badge_text(self, text: str) -> None:
        """Asettaa kissan päällä näytettävän lyhyen tilatekstin (esim. 'KUUNTELEN!')."""
        if text == self._badge_text:
            return
        self._badge_text = text
        self.update()

    def set_processing(self, processing: bool) -> None:
        """Näyttää tai piilottaa puheentunnistuksen pyörivän tulkkausanimaation."""
        if processing is self._processing:
            return
        self._processing = processing
        self.update()

    def set_sleeping(self, sleeping: bool) -> None:
        """Asettaa kissan nukkumaan alustuksen ajaksi tai herättää sen."""
        if sleeping is self._sleeping:
            return
        self._sleeping = sleeping
        self.update()

    # --- Qt-tapahtumat -------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Qt voi luoda natiivi-ikkunan uudelleen, joten tyyli asetetaan joka näytöllä.
        if not apply_floating_tool_style(int(self.winId())):
            logger.warning("Kelluvan ikkunan Win32-tyylien asetus epäonnistui")
        self._gaze_timer.start()
        self._schedule_next_blink()
        self.geometry_changed.emit(self.geometry())

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self.geometry_changed.emit(self.geometry())

    def hideEvent(self, event: QHideEvent) -> None:
        self._gaze_timer.stop()
        self._blink_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
            paint_cat(
                painter,
                self._geometry,
                self._mode,
                *self._pupils,
                theme=self._theme,
                blinking=self._blinking,
                halo_pulse=pulse,
                badge_text=self._badge_text,
                processing=self._processing,
                spinner_angle_deg=self._spinner_angle,
                sleeping=self._sleeping,
            )
        finally:
            painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._drag_offset = self._press_global - self.pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_global is None:
            return
        global_pos = event.globalPosition().toPoint()
        if not self._dragging:
            moved = (global_pos - self._press_global).manhattanLength()
            self._dragging = moved >= QApplication.startDragDistance()
        if self._dragging:
            self.move(global_pos - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() is not Qt.MouseButton.LeftButton or self._press_global is None:
            super().mouseReleaseEvent(event)
            return
        was_dragging = self._dragging
        self._press_global = None
        self._dragging = False
        if was_dragging:
            self.position_committed.emit(self.pos())
        else:
            self.clicked.emit()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.context_menu_requested.emit(event.globalPos())

    # --- Sisäiset ------------------------------------------------------

    def _on_tick(self) -> None:
        if self._mode is AssistantMode.MUTED or self._sleeping:
            return
        needs_repaint = False
        if self._mode in _PULSING_MODES or self._processing:
            self._pulse_phase = (self._pulse_phase + 0.14) % (2.0 * math.pi)
            if self._processing:
                self._spinner_angle = (self._spinner_angle - 18.0) % 360.0
            needs_repaint = True

        # QCursor.pos() palauttaa loogiset koordinaatit samassa järjestelmässä kuin
        # mapToGlobal(), joten DPI-skaalaus ei vääristä katseen suuntaa.
        cursor = QCursor.pos()
        max_offset = self._geometry.max_pupil_offset
        pupils = (
            self._offset_towards(self._geometry.left_eye, cursor, max_offset),
            self._offset_towards(self._geometry.right_eye, cursor, max_offset),
        )
        if pupils != self._pupils:
            self._pupils = pupils
            needs_repaint = True
        if needs_repaint:
            self.update()

    def _schedule_next_blink(self) -> None:
        self._blinking = False
        self._blink_timer.start(random.randint(BLINK_MIN_DELAY_MS, BLINK_MAX_DELAY_MS))

    def _on_blink_tick(self) -> None:
        if self._mode is AssistantMode.MUTED:
            self._schedule_next_blink()
            return
        if not self._blinking:
            self._blinking = True
            self.update()
            self._blink_timer.start(BLINK_DURATION_MS)
        else:
            self._blinking = False
            self.update()
            self._schedule_next_blink()

    def _offset_towards(self, eye: QPointF, cursor: QPoint, max_offset: float) -> Offset:
        eye_global = self.mapToGlobal(eye)
        ox, oy = pupil_offset(eye_global.x(), eye_global.y(), cursor.x(), cursor.y(), max_offset)
        return (round(ox, PUPIL_PRECISION), round(oy, PUPIL_PRECISION))

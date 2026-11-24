"""Kissa-avustimen vektoripiirto QPainterilla.

Kaikki mitat ovat suhteessa kissan kokoon, jotta kissa skaalautuu siististi
eri kokoihin ja High-DPI-näytöille.
"""

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import CatTheme

Offset = tuple[float, float]


@dataclass(frozen=True, slots=True)
class CatPalette:
    """Kissan turkin ja yksityiskohtien väripaletti."""

    fur_light: QColor
    fur_dark: QColor
    outline: QColor
    inner_ear: QColor
    whisker: QColor
    eye_iris: QColor
    pupil: QColor
    nose: QColor
    tongue: QColor
    cheek: QColor


CAT_THEMES: dict[CatTheme, CatPalette] = {
    CatTheme.CHARCOAL: CatPalette(
        fur_light=QColor("#828C9E"),
        fur_dark=QColor("#606878"),
        outline=QColor("#1F232B"),
        inner_ear=QColor("#F7BAC8"),
        whisker=QColor("#1F232B"),
        eye_iris=QColor("#A5B1C4"),
        pupil=QColor("#15181F"),
        nose=QColor("#F48FA8"),
        tongue=QColor("#F27896"),
        cheek=QColor(246, 150, 174, 85),
    ),
    CatTheme.ORANGE: CatPalette(
        fur_light=QColor("#F8BA73"),
        fur_dark=QColor("#E39649"),
        outline=QColor("#6E4627"),
        inner_ear=QColor("#F9C6D4"),
        whisker=QColor("#6E4627"),
        eye_iris=QColor("#7E8796"),
        pupil=QColor("#1E2026"),
        nose=QColor("#EE849D"),
        tongue=QColor("#EB6F8C"),
        cheek=QColor(245, 130, 145, 95),
    ),
    CatTheme.CREAM: CatPalette(
        fur_light=QColor("#FBF6EC"),
        fur_dark=QColor("#E9DFCE"),
        outline=QColor("#8C7D6B"),
        inner_ear=QColor("#F7C4D2"),
        whisker=QColor("#8C7D6B"),
        eye_iris=QColor("#7E8796"),
        pupil=QColor("#1E2026"),
        nose=QColor("#F28BA5"),
        tongue=QColor("#F07693"),
        cheek=QColor(244, 155, 175, 90),
    ),
}

MODE_RING_COLORS: dict[AssistantMode, QColor] = {
    AssistantMode.IDLE: QColor("#8E9AAF"),
    AssistantMode.DICTATING: QColor("#2ECC71"),
    AssistantMode.COMMAND: QColor("#00E676"),
    AssistantMode.MUTED: QColor("#6B7280"),
    AssistantMode.ERROR: QColor("#F05A3C"),
}

ALERT_IRIS_COLOR = QColor("#34D399")
PROCESSING_COLOR = QColor("#FBBF24")
PROCESSING_SECONDARY_COLOR = QColor("#38BDF8")
BADGE_BG_COMMAND = QColor(5, 150, 105, 240)
BADGE_BG_PROCESSING = QColor(217, 119, 6, 240)
BADGE_BG_ERROR = QColor(220, 38, 38, 240)
EYE_HIGHLIGHT = QColor("#FFFFFF")


@dataclass(frozen=True, slots=True)
class CatGeometry:
    """Kissan mittasuhteet pikseleinä annetulle koolle."""

    size: float

    def p(self, x: float, y: float) -> QPointF:
        return QPointF(x * self.size, y * self.size)

    @property
    def left_eye(self) -> QPointF:
        return self.p(0.375, 0.525)

    @property
    def right_eye(self) -> QPointF:
        return self.p(0.625, 0.525)

    @property
    def eye_radius(self) -> float:
        return 0.082 * self.size

    @property
    def pupil_radius(self) -> float:
        return 0.056 * self.size

    @property
    def max_pupil_offset(self) -> float:
        return max(0.0, self.eye_radius - self.pupil_radius)


def cat_widget_height(size: int, *, show_wake_word: bool = True) -> int:
    """Palauttaa kissa-ikkunan kokonaiskorkeuden (kissa + valinnainen herätesanakyltti)."""
    if not show_wake_word:
        return size
    return size + max(22, int(round(size * 0.25)))


def paint_cat(
    painter: QPainter,
    geometry: CatGeometry,
    mode: AssistantMode,
    left_pupil: Offset = (0.0, 0.0),
    right_pupil: Offset = (0.0, 0.0),
    theme: CatTheme = CatTheme.CHARCOAL,
    *,
    blinking: bool = False,
    halo_pulse: float = 0.5,
    badge_text: str = "",
    processing: bool = False,
    spinner_angle_deg: float = 0.0,
    sleeping: bool = False,
    wake_word: str = "",
) -> None:
    """Piirtää kissan annettuun maalariin."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    palette = CAT_THEMES.get(theme, CAT_THEMES[CatTheme.CHARCOAL])
    effective_mode = AssistantMode.MUTED if sleeping else mode
    ring_color = MODE_RING_COLORS.get(effective_mode, MODE_RING_COLORS[AssistantMode.IDLE])

    _paint_ring(
        painter,
        geometry,
        effective_mode,
        ring_color,
        halo_pulse,
        processing=processing and not sleeping,
        spinner_angle_deg=spinner_angle_deg,
    )

    perk = (0.55 + 0.45 * max(0.0, min(1.0, halo_pulse))) if (processing and not sleeping) else (
        0.45 if effective_mode is AssistantMode.COMMAND else 0.0
    )
    painter.save()
    if perk > 0.0:
        # Kissa kohottaa päätään valppaasti havahtuessaan ääneen.
        painter.translate(0.0, -0.022 * geometry.size * perk)

    _paint_drop_shadow(painter, geometry)
    _paint_ears(painter, geometry, palette, ear_perk=perk)
    _paint_head(painter, geometry, palette)

    if effective_mode is AssistantMode.MUTED or blinking:
        _paint_closed_eyes(painter, geometry, palette)
    else:
        _paint_eyes(
            painter,
            geometry,
            palette,
            left_pupil,
            right_pupil,
            worried=effective_mode is AssistantMode.ERROR,
            alert=effective_mode is AssistantMode.COMMAND or processing,
        )

    _paint_nose_and_mouth(painter, geometry, palette, effective_mode)
    _paint_whiskers(
        painter,
        geometry,
        palette,
        perked=effective_mode in (AssistantMode.COMMAND, AssistantMode.DICTATING) or (processing and not sleeping),
        twitch=perk if (processing and not sleeping) else 0.0,
    )
    if processing and not sleeping:
        _paint_ear_attention_waves(painter, geometry, halo_pulse)
    painter.restore()

    if effective_mode is AssistantMode.MUTED:
        _paint_zzz(painter, geometry)
    elif effective_mode is AssistantMode.ERROR:
        _paint_error_badge(painter, geometry, ring_color)

    active_badge = "" if sleeping else (badge_text or ("KUUNTELEN!" if effective_mode is AssistantMode.COMMAND else ""))
    if active_badge:
        _paint_status_pill(
            painter,
            geometry,
            active_badge,
            is_error=effective_mode is AssistantMode.ERROR,
        )

    if wake_word.strip():
        _paint_wake_word_label(painter, geometry, wake_word.strip(), ring_color, sleeping=sleeping)

    painter.restore()


def render_cat_icon(
    mode: AssistantMode,
    size: int = 64,
    theme: CatTheme = CatTheme.CHARCOAL,
) -> QIcon:
    """Renderöi kissan ikoniksi (esim. ilmaisinalueelle)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        paint_cat(painter, CatGeometry(float(size)), mode, theme=theme)
    finally:
        painter.end()
    return QIcon(pixmap)


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, max(1.0, width))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _paint_ring(
    painter: QPainter,
    geometry: CatGeometry,
    mode: AssistantMode,
    color: QColor,
    halo_pulse: float,
    *,
    processing: bool = False,
    spinner_angle_deg: float = 0.0,
) -> None:
    s = geometry.size
    ring_rect = QRectF(0.06 * s, 0.08 * s, 0.88 * s, 0.88 * s)

    if mode in (AssistantMode.DICTATING, AssistantMode.COMMAND, AssistantMode.ERROR) or processing:
        base_glow_color = PROCESSING_COLOR if processing else color
        glow_alpha = int(75 + 65 * max(0.0, min(1.0, halo_pulse)))
        for spread, alpha_scale in ((0.046, 0.50), (0.024, 0.85)):
            glow = QColor(base_glow_color)
            glow.setAlpha(int(glow_alpha * alpha_scale))
            painter.setPen(_pen(glow, spread * s))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring_rect)

    stroke = QColor(color)
    stroke.setAlpha(110 if mode in (AssistantMode.IDLE, AssistantMode.MUTED) else 255)
    ring_width = 0.036 * s if mode is AssistantMode.COMMAND else 0.024 * s
    painter.setPen(_pen(stroke, ring_width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(ring_rect)

    if mode is AssistantMode.COMMAND:
        inner_rect = QRectF(0.105 * s, 0.125 * s, 0.79 * s, 0.79 * s)
        inner_color = QColor("#A7F3D0")
        inner_color.setAlpha(210)
        painter.setPen(_pen(inner_color, 0.015 * s))
        painter.drawEllipse(inner_rect)

    if processing:
        painter.setPen(_pen(PROCESSING_COLOR, 0.038 * s))
        painter.drawArc(ring_rect, int(spinner_angle_deg * 16), 110 * 16)
        painter.setPen(_pen(PROCESSING_SECONDARY_COLOR, 0.032 * s))
        painter.drawArc(ring_rect, int(((spinner_angle_deg + 180.0) % 360.0) * 16), 80 * 16)


def _head_path(geometry: CatGeometry) -> QPainterPath:
    """Pehmeästi pyöristetty, poskista hieman leveämpi kissanpää."""
    path = QPainterPath()
    path.moveTo(geometry.p(0.50, 0.25))
    path.cubicTo(geometry.p(0.68, 0.25), geometry.p(0.84, 0.38), geometry.p(0.84, 0.56))
    path.cubicTo(geometry.p(0.84, 0.74), geometry.p(0.70, 0.84), geometry.p(0.50, 0.84))
    path.cubicTo(geometry.p(0.30, 0.84), geometry.p(0.16, 0.74), geometry.p(0.16, 0.56))
    path.cubicTo(geometry.p(0.16, 0.38), geometry.p(0.32, 0.25), geometry.p(0.50, 0.25))
    path.closeSubpath()
    return path


def _paint_drop_shadow(painter: QPainter, geometry: CatGeometry) -> None:
    s = geometry.size
    painter.save()
    painter.translate(0.0, 0.024 * s)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 52))
    painter.drawPath(_head_path(geometry))
    painter.restore()


def _ear_path(geometry: CatGeometry, *, left: bool, ear_perk: float = 0.0) -> QPainterPath:
    sign = 1.0 if left else -1.0
    cx = lambda x: 0.50 + sign * (x - 0.50)  # noqa: E731
    tip_lift = 0.048 * ear_perk
    tip_out = 0.015 * ear_perk
    path = QPainterPath(geometry.p(cx(0.20), 0.44))
    path.quadTo(geometry.p(cx(0.18 - tip_out), 0.24 - tip_lift), geometry.p(cx(0.23 - tip_out), 0.16 - tip_lift))
    path.quadTo(geometry.p(cx(0.25 - tip_out), 0.13 - tip_lift), geometry.p(cx(0.28), 0.15 - tip_lift))
    path.quadTo(geometry.p(cx(0.37), 0.22 - tip_lift * 0.4), geometry.p(cx(0.42), 0.29))
    path.closeSubpath()
    return path


def _inner_ear_path(geometry: CatGeometry, *, left: bool, ear_perk: float = 0.0) -> QPainterPath:
    sign = 1.0 if left else -1.0
    cx = lambda x: 0.50 + sign * (x - 0.50)  # noqa: E731
    tip_lift = 0.042 * ear_perk
    tip_out = 0.012 * ear_perk
    path = QPainterPath(geometry.p(cx(0.235), 0.39))
    path.quadTo(geometry.p(cx(0.225 - tip_out), 0.26 - tip_lift), geometry.p(cx(0.255 - tip_out), 0.205 - tip_lift))
    path.quadTo(geometry.p(cx(0.325), 0.25 - tip_lift * 0.5), geometry.p(cx(0.365), 0.305))
    path.closeSubpath()
    return path


def _paint_ears(
    painter: QPainter,
    geometry: CatGeometry,
    palette: CatPalette,
    *,
    ear_perk: float = 0.0,
) -> None:
    s = geometry.size
    for left in (True, False):
        painter.setPen(_pen(palette.outline, 0.018 * s))
        painter.setBrush(palette.fur_dark)
        painter.drawPath(_ear_path(geometry, left=left, ear_perk=ear_perk))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.inner_ear)
        painter.drawPath(_inner_ear_path(geometry, left=left, ear_perk=ear_perk))


def _paint_ear_attention_waves(
    painter: QPainter,
    geometry: CatGeometry,
    halo_pulse: float,
) -> None:
    """Piirtää korvien viereen pienet animoidut ääniaaltokaaret kissan havahtuessa."""
    s = geometry.size
    alpha = int(130 + 110 * max(0.0, min(1.0, halo_pulse)))
    wave_color = QColor(PROCESSING_COLOR)
    wave_color.setAlpha(alpha)
    painter.setPen(_pen(wave_color, 0.020 * s))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    spread = 0.015 * halo_pulse
    left_arc = QRectF((0.08 - spread) * s, (0.10 - spread) * s, 0.16 * s, 0.16 * s)
    right_arc = QRectF((0.76 + spread) * s, (0.10 - spread) * s, 0.16 * s, 0.16 * s)
    painter.drawArc(left_arc, 115 * 16, 75 * 16)
    painter.drawArc(right_arc, -10 * 16, 75 * 16)


def _paint_head(painter: QPainter, geometry: CatGeometry, palette: CatPalette) -> None:
    s = geometry.size
    gradient = QRadialGradient(geometry.p(0.50, 0.42), 0.42 * s)
    gradient.setColorAt(0.0, palette.fur_light)
    gradient.setColorAt(1.0, palette.fur_dark)

    painter.setPen(_pen(palette.outline, 0.018 * s))
    painter.setBrush(gradient)
    painter.drawPath(_head_path(geometry))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(palette.cheek)
    painter.drawEllipse(QRectF(0.22 * s, 0.59 * s, 0.11 * s, 0.065 * s))
    painter.drawEllipse(QRectF(0.67 * s, 0.59 * s, 0.11 * s, 0.065 * s))


def _paint_eyes(
    painter: QPainter,
    geometry: CatGeometry,
    palette: CatPalette,
    left_pupil: Offset,
    right_pupil: Offset,
    *,
    worried: bool,
    alert: bool = False,
) -> None:
    scale = 1.16 if alert else 1.0
    r = geometry.eye_radius * scale
    pr = geometry.pupil_radius * (1.10 if alert else 1.0)
    iris_color = ALERT_IRIS_COLOR if alert else palette.eye_iris
    for is_left, (center, (ox, oy)) in enumerate(
        ((geometry.left_eye, left_pupil), (geometry.right_eye, right_pupil))
    ):
        painter.setPen(_pen(palette.outline, 0.013 * geometry.size))
        painter.setBrush(iris_color)
        painter.drawEllipse(center, r, r)

        pupil = QPointF(center.x() + ox, center.y() + oy)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.pupil)
        painter.drawEllipse(pupil, pr, pr)

        # Kaksi pientä heijastusta luo kiiltävän ja elävän katseen.
        painter.setBrush(EYE_HIGHLIGHT)
        painter.drawEllipse(QPointF(pupil.x() - pr * 0.34, pupil.y() - pr * 0.36), pr * 0.36, pr * 0.36)
        painter.drawEllipse(QPointF(pupil.x() + pr * 0.28, pupil.y() + pr * 0.30), pr * 0.16, pr * 0.16)

        if worried:
            _paint_worried_brow(painter, geometry, palette, center, left=is_left == 0)


def _paint_worried_brow(
    painter: QPainter,
    geometry: CatGeometry,
    palette: CatPalette,
    eye_center: QPointF,
    *,
    left: bool,
) -> None:
    s = geometry.size
    r = geometry.eye_radius
    sign = 1.0 if left else -1.0
    p1 = QPointF(eye_center.x() - sign * r * 0.85, eye_center.y() - r * 1.15)
    p2 = QPointF(eye_center.x() + sign * r * 0.65, eye_center.y() - r * 1.48)
    painter.setPen(_pen(palette.outline, 0.020 * s))
    painter.drawLine(p1, p2)


def _paint_closed_eyes(painter: QPainter, geometry: CatGeometry, palette: CatPalette) -> None:
    r = geometry.eye_radius
    painter.setPen(_pen(palette.outline, 0.022 * geometry.size))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for center in (geometry.left_eye, geometry.right_eye):
        rect = QRectF(center.x() - r * 0.9, center.y() - r * 0.45, r * 1.8, r * 0.9)
        painter.drawArc(rect, 200 * 16, 140 * 16)


def _paint_nose_and_mouth(
    painter: QPainter, geometry: CatGeometry, palette: CatPalette, mode: AssistantMode
) -> None:
    s = geometry.size
    nose = QPainterPath(geometry.p(0.47, 0.605))
    nose.quadTo(geometry.p(0.50, 0.595), geometry.p(0.53, 0.605))
    nose.quadTo(geometry.p(0.515, 0.635), geometry.p(0.50, 0.640))
    nose.quadTo(geometry.p(0.485, 0.635), geometry.p(0.47, 0.605))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(palette.nose)
    painter.drawPath(nose)

    painter.setPen(_pen(palette.outline, 0.016 * s))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if mode is AssistantMode.ERROR:
        # Suupielet alaspäin virhetilassa.
        frown = QPainterPath(geometry.p(0.445, 0.705))
        frown.quadTo(geometry.p(0.50, 0.658), geometry.p(0.555, 0.705))
        painter.drawPath(frown)
        return

    if mode in (AssistantMode.DICTATING, AssistantMode.COMMAND):
        # Iloinen avoin hymy sanelutilassa ja kun Puhis kuulee nimensä.
        mouth_depth = 0.760 if mode is AssistantMode.COMMAND else 0.745
        smile = QPainterPath(geometry.p(0.438, 0.662))
        smile.quadTo(geometry.p(0.50, mouth_depth), geometry.p(0.562, 0.662))
        smile.closeSubpath()
        painter.setBrush(palette.outline)
        painter.drawPath(smile)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.tongue)
        painter.drawEllipse(QRectF(0.468 * s, 0.686 * s, 0.064 * s, 0.036 * s))
        return

    mouth = QPainterPath(geometry.p(0.50, 0.640))
    mouth.quadTo(geometry.p(0.475, 0.688), geometry.p(0.440, 0.668))
    mouth.moveTo(geometry.p(0.50, 0.640))
    mouth.quadTo(geometry.p(0.525, 0.688), geometry.p(0.560, 0.668))
    painter.drawPath(mouth)


def _paint_whiskers(
    painter: QPainter,
    geometry: CatGeometry,
    palette: CatPalette,
    *,
    perked: bool = False,
    twitch: float = 0.0,
) -> None:
    s = geometry.size
    painter.setPen(_pen(palette.whisker, 0.012 * s))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    lift = (-0.020 - 0.016 * twitch) if perked else 0.0
    for sign in (-1.0, 1.0):
        cx = lambda offset: 0.50 + sign * offset  # noqa: E731
        for y_start, y_ctrl, y_end in (
            (0.605 + lift, 0.590 + lift * 0.5, 0.585),
            (0.635 + lift, 0.635 + lift * 0.5, 0.645),
            (0.665 + lift, 0.680 + lift * 0.5, 0.700),
        ):
            path = QPainterPath(geometry.p(cx(0.20), y_start))
            path.quadTo(geometry.p(cx(0.31), y_ctrl), geometry.p(cx(0.40), y_end))
            painter.drawPath(path)


def _paint_status_pill(
    painter: QPainter,
    geometry: CatGeometry,
    text: str,
    *,
    is_error: bool = False,
    is_processing: bool = False,
) -> None:
    """Piirtää selkeän tilapillerin kissan alareunaan, kun Puhis kuulee nimensä."""
    s = geometry.size
    rect = QRectF(0.04 * s, 0.78 * s, 0.92 * s, 0.19 * s)
    radius = 0.09 * s

    painter.setPen(_pen(EYE_HIGHLIGHT, 0.016 * s))
    if is_error:
        bg = BADGE_BG_ERROR
    elif is_processing:
        bg = BADGE_BG_PROCESSING
    else:
        bg = BADGE_BG_COMMAND
    painter.setBrush(bg)
    painter.drawRoundedRect(rect, radius, radius)

    painter.setPen(EYE_HIGHLIGHT)
    font = QFont("Segoe UI", max(6, int(0.082 * s)), QFont.Weight.Bold)
    painter.setFont(font)
    display = text if len(text) <= 14 else text[:13] + "…"
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, display)


def _paint_wake_word_label(
    painter: QPainter,
    geometry: CatGeometry,
    wake_word: str,
    accent_color: QColor,
    *,
    sleeping: bool = False,
) -> None:
    """Piirtää aktiivisen herätesanan tyylikkäällä fontilla kissan alapuolelle."""
    s = geometry.size
    pill_h = max(18.0, 0.21 * s)
    pill_rect = QRectF(0.10 * s, 1.00 * s, 0.80 * s, pill_h)
    radius = pill_h * 0.48

    border = QColor(accent_color)
    border.setAlpha(120 if sleeping else 200)
    bg = QColor(17, 22, 31, 185 if sleeping else 225)

    painter.setPen(_pen(border, 0.014 * s))
    painter.setBrush(bg)
    painter.drawRoundedRect(pill_rect, radius, radius)

    font = QFont("Bahnschrift", max(7, int(0.095 * s)), QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0.8, 0.012 * s))
    painter.setFont(font)

    text_color = QColor("#94A3B8") if sleeping else QColor("#F8FAFC")
    painter.setPen(text_color)
    display = wake_word.upper()
    if len(display) > 12:
        display = display[:11] + "…"
    painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, display)


def _paint_zzz(painter: QPainter, geometry: CatGeometry) -> None:
    s = geometry.size
    painter.setPen(QColor("#CBD5E1"))
    font = QFont("Segoe UI", max(6, int(0.085 * s)), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(geometry.p(0.74, 0.25), "z")
    font.setPointSize(max(7, int(0.110 * s)))
    painter.setFont(font)
    painter.drawText(geometry.p(0.81, 0.19), "Z")


def _paint_error_badge(painter: QPainter, geometry: CatGeometry, color: QColor) -> None:
    s = geometry.size
    center = geometry.p(0.80, 0.18)
    radius = 0.095 * s
    painter.setPen(_pen(EYE_HIGHLIGHT, 0.016 * s))
    painter.setBrush(color)
    painter.drawEllipse(center, radius, radius)

    painter.setPen(EYE_HIGHLIGHT)
    font = QFont("Segoe UI", max(7, int(0.115 * s)), QFont.Weight.Bold)
    painter.setFont(font)
    rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "!")

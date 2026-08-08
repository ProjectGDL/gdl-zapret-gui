from PySide6.QtCore import QEasingCurve, QPoint, QRect, QSize, Qt, QVariantAnimation
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QAbstractButton, QApplication, QSizePolicy


def _white_icon_pixmap(icon: QIcon, size: int) -> QPixmap:
    return _tinted_icon_pixmap(icon, size, QColor(255, 255, 255, 255))


def _tinted_icon_pixmap(icon: QIcon, size: int, tint: QColor) -> QPixmap:
    src = icon.pixmap(QSize(size, size))
    img = src.toImage().convertToFormat(QImage.Format_ARGB32)
    tr, tg, tb, ta = tint.red(), tint.green(), tint.blue(), tint.alpha()
    for y in range(img.height()):
        for x in range(img.width()):
            px = img.pixel(x, y)
            alpha = (px >> 24) & 0xFF
            if alpha > 0:
                a = (alpha * ta) // 255
                img.setPixel(x, y, (a << 24) | (tr << 16) | (tg << 8) | tb)
    return QPixmap.fromImage(img)


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


_BTN_SIZE = 160
_PILL_H   = 32
_PILL_GAP = 14


class RoundButton(QAbstractButton):
    _STOP = {
        "bg":    QColor("#e05545"),
        "hover": QColor("#f0665a"),
        "press": QColor("#c04035"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._hovered = False
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        self._color = self._target_bg()

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

        self._scale = 1.0
        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.setDuration(120)
        self._scale_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._scale_anim.valueChanged.connect(self._on_scale_anim)

        self._ring_t = 0.0
        self._ring_anim = QVariantAnimation(self)
        self._ring_anim.setDuration(120)
        self._ring_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._ring_anim.valueChanged.connect(self._on_ring_anim)

    def _on_ring_anim(self, value):
        self._ring_t = value
        self.update()

    def _on_scale_anim(self, value):
        self._scale = value
        self.update()

    def _start_pal(self):
        c = QApplication.palette().highlight().color()
        return {"bg": c, "hover": c.lighter(115), "press": c.darker(115)}

    def _target_bg(self) -> QColor:
        pal = self._STOP if self._running else self._start_pal()
        if self.isDown():
            return pal["press"]
        if self._hovered:
            return pal["hover"]
        return pal["bg"]

    def _animate_to(self, target: QColor):
        self._anim.stop()
        self._anim.setStartValue(self._color)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_anim(self, value):
        self._color = value
        self.update()

    def setRunning(self, running: bool):
        if self._running != running:
            self._running = running
            self._animate_to(self._target_bg())

    def sizeHint(self) -> QSize:
        return QSize(_BTN_SIZE, _BTN_SIZE + _PILL_GAP + _PILL_H)

    def enterEvent(self, event):
        self._hovered = True
        self._animate_to(self._target_bg())
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._animate_to(self._target_bg())
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._animate_to(self._target_bg())
        self._animate_scale(0.95)
        self._animate_ring(1.0)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._animate_to(self._target_bg())
        self._animate_scale(1.0)
        self._animate_ring(0.0)

    def _animate_scale(self, target: float):
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(target)
        self._scale_anim.start()

    def _animate_ring(self, target: float):
        self._ring_anim.stop()
        self._ring_anim.setStartValue(self._ring_t)
        self._ring_anim.setEndValue(target)
        self._ring_anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w  = self.width()
        cx = w / 2
        cy = _BTN_SIZE / 2
        r  = _BTN_SIZE / 2 - 4
        inner_r = _BTN_SIZE / 2 - 14

        color = self._color

        path = QPainterPath()
        path.addEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setClipPath(path)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        p.setClipping(False)

        ring_inner_r = inner_r - self._ring_t * 4
        ring_alpha   = int(25 + self._ring_t * 30)
        ring_outer = QPainterPath()
        ring_outer.addEllipse(cx - r, cy - r, r * 2, r * 2)
        ring_inner = QPainterPath()
        ring_inner.addEllipse(cx - ring_inner_r, cy - ring_inner_r,
                              ring_inner_r * 2, ring_inner_r * 2)
        ring_path = ring_outer - ring_inner
        p.setClipPath(ring_path)
        p.setBrush(QColor(0, 0, 0, ring_alpha))
        p.setPen(Qt.NoPen)
        p.drawPath(ring_path)
        p.setClipping(False)

        p.setPen(QPen(QColor(0, 0, 0, 40), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(int(cx), int(cy)), int(r), int(r))

        p.save()
        p.translate(cx, cy)
        p.scale(self._scale, self._scale)
        p.translate(-cx, -cy)

        p.setPen(QPen(QColor(0, 0, 0, 25), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(int(cx), int(cy)), int(inner_r), int(inner_r))

        grad = QConicalGradient(cx, cy, 270)
        grad.setColorAt(0.0,  QColor(255, 255, 255, 0))
        grad.setColorAt(0.15, QColor(255, 255, 255, 0))
        grad.setColorAt(0.35, QColor(255, 255, 255, 110))
        grad.setColorAt(0.5,  QColor(255, 255, 255, 130))
        grad.setColorAt(0.65, QColor(255, 255, 255, 110))
        grad.setColorAt(0.85, QColor(255, 255, 255, 0))
        grad.setColorAt(1.0,  QColor(255, 255, 255, 0))
        p.setPen(QPen(grad, 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(int(cx), int(cy)), int(inner_r), int(inner_r))

        icon_name = "media-playback-stop" if self._running else None
        if icon_name:
            icon = QIcon.fromTheme(icon_name)
            icon_size = int(_BTN_SIZE * 0.28)
            if not icon.isNull():
                p.drawPixmap(int(cx - icon_size / 2), int(cy - icon_size / 2),
                             _white_icon_pixmap(icon, icon_size))

        p.restore()

        if not self._running:
            icon = QIcon.fromTheme("media-playback-start")
            icon_size = int(_BTN_SIZE * 0.28)
            if not icon.isNull():
                p.drawPixmap(int(cx - icon_size / 2) + 3, int(cy - icon_size / 2),
                             _white_icon_pixmap(icon, icon_size))

        label = "Остановить" if self._running else "Запустить"
        font = self.font()
        font.setPointSize(max(7, int(_BTN_SIZE * 0.07)))
        p.setFont(font)
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(label) + 32
        pill_rect = QRect(int(cx - text_w / 2), _BTN_SIZE + _PILL_GAP, text_w, _PILL_H)
        pill_bg = QColor(color)
        pill_bg.setAlpha(40)
        p.setBrush(pill_bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(pill_rect, _PILL_H / 2, _PILL_H / 2)
        p.setPen(QApplication.palette().text().color())
        p.drawText(pill_rect, Qt.AlignCenter, label)

        p.end()

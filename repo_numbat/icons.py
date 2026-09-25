"""Toolbar/status icons drawn with QPainter so no image files are needed."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from repo_numbat.theme import C

ASSETS = Path(__file__).parent / "assets"


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        png = ASSETS / f"numbat-{size}.png"
        if png.exists():
            icon.addFile(str(png))
    if icon.isNull():
        icon.addFile(str(ASSETS / "numbat.svg"))
    return icon


@lru_cache(maxsize=None)
def dot(kind: str, size: int = 12) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(C.get(kind, C["none"]))
    p.setPen(QPen(color.darker(140), 1))
    p.setBrush(color)
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()
    return QIcon(pm)


def _canvas(size: int):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(C["text"]), size * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    return pm, p


def _arrow_head(p: QPainter, tip: QPointF, angle_deg: float, length: float) -> None:
    a = math.radians(angle_deg)
    left = QPointF(tip.x() - length * math.cos(a - 0.5), tip.y() - length * math.sin(a - 0.5))
    right = QPointF(tip.x() - length * math.cos(a + 0.5), tip.y() - length * math.sin(a + 0.5))
    p.drawLine(tip, left)
    p.drawLine(tip, right)


@lru_cache(maxsize=None)
def toolbar_icon(name: str, size: int = 28) -> QIcon:
    pm, p = _canvas(size)
    s = size
    m = s * 0.18
    r = QRectF(m, m, s - 2 * m, s - 2 * m)
    if name == "refresh":
        p.drawArc(r, 30 * 16, 300 * 16)
        tip = QPointF(r.center().x() + r.width() / 2 * math.cos(math.radians(-30)),
                      r.center().y() - r.height() / 2 * math.sin(math.radians(-30)))
        _arrow_head(p, tip, 200, s * 0.22)
    elif name == "fetch":  # cloud with a down arrow
        path = QPainterPath()
        path.moveTo(s * 0.25, s * 0.55)
        path.arcTo(QRectF(s * 0.12, s * 0.40, s * 0.30, s * 0.30), 90, 180)
        path.arcTo(QRectF(s * 0.28, s * 0.22, s * 0.36, s * 0.36), 200, -200)
        path.arcTo(QRectF(s * 0.58, s * 0.38, s * 0.30, s * 0.30), 90, -180)
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.5, s * 0.50), QPointF(s * 0.5, s * 0.86))
        _arrow_head(p, QPointF(s * 0.5, s * 0.86), 90, s * 0.2)
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(s * 0.15, s * 0.28)
        path.lineTo(s * 0.38, s * 0.28)
        path.lineTo(s * 0.46, s * 0.38)
        path.lineTo(s * 0.85, s * 0.38)
        path.lineTo(s * 0.85, s * 0.78)
        path.lineTo(s * 0.15, s * 0.78)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "terminal":
        p.drawRoundedRect(r, 2, 2)
        p.drawLine(QPointF(s * 0.30, s * 0.42), QPointF(s * 0.42, s * 0.52))
        p.drawLine(QPointF(s * 0.42, s * 0.52), QPointF(s * 0.30, s * 0.62))
        p.drawLine(QPointF(s * 0.50, s * 0.64), QPointF(s * 0.68, s * 0.64))
    elif name == "copy":
        p.drawRect(QRectF(s * 0.34, s * 0.34, s * 0.46, s * 0.46))
        path = QPainterPath()
        path.moveTo(s * 0.26, s * 0.62)
        path.lineTo(s * 0.20, s * 0.62)
        path.lineTo(s * 0.20, s * 0.20)
        path.lineTo(s * 0.62, s * 0.20)
        path.lineTo(s * 0.62, s * 0.26)
        p.drawPath(path)
    elif name == "settings":
        p.drawEllipse(QRectF(s * 0.36, s * 0.36, s * 0.28, s * 0.28))
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(s / 2 + s * 0.24 * math.cos(a), s / 2 + s * 0.24 * math.sin(a)),
                       QPointF(s / 2 + s * 0.36 * math.cos(a), s / 2 + s * 0.36 * math.sin(a)))
    elif name == "stop":
        p.setBrush(QColor(C["text"]))
        p.drawRoundedRect(QRectF(s * 0.26, s * 0.26, s * 0.48, s * 0.48), 2, 2)
    elif name == "push":
        p.drawLine(QPointF(s * 0.5, s * 0.78), QPointF(s * 0.5, s * 0.22))
        _arrow_head(p, QPointF(s * 0.5, s * 0.22), -90, s * 0.22)
        p.drawLine(QPointF(s * 0.22, s * 0.84), QPointF(s * 0.78, s * 0.84))
    elif name == "pull":
        p.drawLine(QPointF(s * 0.5, s * 0.20), QPointF(s * 0.5, s * 0.72))
        _arrow_head(p, QPointF(s * 0.5, s * 0.72), 90, s * 0.22)
        p.drawLine(QPointF(s * 0.22, s * 0.84), QPointF(s * 0.78, s * 0.84))
    elif name == "github":  # a globe with a magnifier
        g = QRectF(s * 0.16, s * 0.16, s * 0.52, s * 0.52)
        p.drawEllipse(g)
        p.drawEllipse(QRectF(s * 0.30, s * 0.16, s * 0.24, s * 0.52))
        p.drawLine(QPointF(s * 0.16, s * 0.42), QPointF(s * 0.68, s * 0.42))
        p.drawLine(QPointF(s * 0.62, s * 0.62), QPointF(s * 0.84, s * 0.84))
    elif name == "remote":  # cloud with a plus sign
        path = QPainterPath()
        path.moveTo(s * 0.25, s * 0.55)
        path.arcTo(QRectF(s * 0.12, s * 0.40, s * 0.30, s * 0.30), 90, 180)
        path.arcTo(QRectF(s * 0.28, s * 0.22, s * 0.36, s * 0.36), 200, -200)
        path.arcTo(QRectF(s * 0.58, s * 0.38, s * 0.30, s * 0.30), 90, -180)
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.5, s * 0.60), QPointF(s * 0.5, s * 0.88))
        p.drawLine(QPointF(s * 0.36, s * 0.74), QPointF(s * 0.64, s * 0.74))
    elif name == "clear":
        p.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.72, s * 0.72))
        p.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.28, s * 0.72))
    p.end()
    return QIcon(pm)

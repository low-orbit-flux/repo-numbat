#!/usr/bin/env python3
"""Render repo_numbat/assets/numbat.svg into PNG (several sizes) and a Windows .ico.

Run from a venv that has PySide6 installed:
    python tools/make_icon.py
Pillow is optional; it is only used to write the .ico and .icns files.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "repo_numbat" / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def render(svg: Path, size: int) -> QImage:
    renderer = QSvgRenderer(str(svg))
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def main() -> int:
    QGuiApplication(sys.argv)
    svg = ASSETS / "numbat.svg"
    pngs: list[Path] = []
    for size in SIZES:
        out = ASSETS / f"numbat-{size}.png"
        render(svg, size).save(str(out))
        pngs.append(out)
        print("wrote", out)
    render(svg, 256).save(str(ASSETS / "numbat.png"))
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed; skipping numbat.ico")
        return 0
    frames = [Image.open(p) for p in pngs if p.stem.split("-")[1] in {"16", "24", "32", "48", "64", "128", "256"}]
    ico = ASSETS / "numbat.ico"
    frames[-1].save(ico, format="ICO", sizes=[(f.width, f.height) for f in frames], append_images=frames[:-1])
    print("wrote", ico)
    icns = ASSETS / "numbat.icns"
    big = Image.open(ASSETS / "numbat-512.png")
    big.save(icns, format="ICNS", sizes=[(s, s) for s in (16, 32, 64, 128, 256, 512)])
    print("wrote", icns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Windows app and tray icon assets."""

from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICONS = ASSETS / "icons"

SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
TRAY_SIZES = SIZES

BADGES = {
    "online": (44, 204, 113),
    "connecting": (245, 184, 0),
    "offline": (231, 76, 60),
    "paused": (149, 165, 166),
}


def _draw_icon(size: int, badge: Optional[Tuple[int, int, int]] = None) -> Image.Image:
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def xy(points):
        return [(int(x * scale), int(y * scale)) for x, y in points]

    def box(left, top, right, bottom):
        return [int(left * scale), int(top * scale), int(right * scale), int(bottom * scale)]

    # Shield body, tuned to stay legible at 16px tray size.
    shield = [
        (size * 0.50, size * 0.08),
        (size * 0.84, size * 0.22),
        (size * 0.84, size * 0.49),
        (size * 0.80, size * 0.68),
        (size * 0.68, size * 0.83),
        (size * 0.50, size * 0.93),
        (size * 0.32, size * 0.83),
        (size * 0.20, size * 0.68),
        (size * 0.16, size * 0.49),
        (size * 0.16, size * 0.22),
    ]
    draw.polygon(xy(shield), fill=(22, 126, 218, 255))
    draw.line(xy(shield + [shield[0]]), fill=(232, 246, 255, 255), width=max(1, int(size * 0.045 * scale)), joint="curve")

    # Subtle highlight that reads as polish at large sizes and disappears cleanly at small sizes.
    if size >= 32:
        highlight = [
            (size * 0.31, size * 0.26),
            (size * 0.50, size * 0.18),
            (size * 0.69, size * 0.26),
            (size * 0.63, size * 0.58),
            (size * 0.50, size * 0.73),
            (size * 0.37, size * 0.58),
        ]
        draw.polygon(xy(highlight), fill=(125, 211, 252, 54))

    stroke = max(2, int(size * 0.07)) * scale
    cx = size * 0.50
    draw.arc(box(size * 0.30, size * 0.37, size * 0.70, size * 0.78), 210, 330, fill=(255, 255, 255, 255), width=stroke)
    if size >= 24:
        draw.arc(box(size * 0.22, size * 0.28, size * 0.78, size * 0.86), 212, 328, fill=(255, 255, 255, 255), width=stroke)
    dot_r = max(1.4, size * 0.055)
    draw.ellipse(box(cx - dot_r, size * 0.62 - dot_r, cx + dot_r, size * 0.62 + dot_r), fill=(255, 255, 255, 255))

    if badge is not None:
        radius = size * 0.18
        bx = size * 0.76
        by = size * 0.76
        draw.ellipse(box(bx - radius * 1.18, by - radius * 1.18, bx + radius * 1.18, by + radius * 1.18), fill=(255, 255, 255, 255))
        draw.ellipse(box(bx - radius, by - radius, bx + radius, by + radius), fill=badge + (255,))

    return image.resize((size, size), Image.Resampling.LANCZOS)


def _save_ico(path: Path, badge: Optional[Tuple[int, int, int]] = None, sizes=()):
    frames = [_draw_icon(size, badge) for size in sizes]
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[-1].save(path, format="ICO", sizes=[frame.size for frame in frames], append_images=frames[:-1])


def main():
    _save_ico(ASSETS / "icon.ico", sizes=SIZES)
    for status, color in BADGES.items():
        _save_ico(ICONS / f"tray-{status}.ico", badge=color, sizes=TRAY_SIZES)
    print("Generated app and tray icons")


if __name__ == "__main__":
    main()

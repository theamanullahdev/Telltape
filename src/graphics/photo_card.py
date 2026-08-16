"""Real photo cards, for a specific, identifiable real-world subject (a
named person, a specific building) that generic stock footage can't
accurately represent. Same visual language as chart/map cards (rounded,
bordered, drop-shadowed), but holds a single real photo with NO synthetic
motion (no zoom/pan of any kind, see src/render/assemble.py's docstring
for why that's banned outright) and a visible on-screen credit line, so the
source is disclosed in the video itself, not just in metadata.json.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from src.graphics.palette import INK_PRIMARY, INK_SECONDARY, SURFACE

CARD_W, CARD_H = 1536, 860
DPI = 100


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr[-3000:]}")


def render_photo_card(image_path: Path, out_path: Path, caption: str, credit: str,
                       total_duration: float, border_color: str, fps: int = 30,
                       full_frame: bool = False) -> None:
    """full_frame=True: the photo IS the shot for this scene (card fills
    nearly the whole 1920x1080, opaque), used when a scene needs no
    footage layer behind it. full_frame=False (default): a smaller
    transparent overlay card meant to be composited over background
    footage via the same mechanism as chart/map graphics."""
    card_w, card_h = (1920, 1080) if full_frame else (CARD_W, CARD_H)
    fig = plt.figure(figsize=(card_w / DPI, card_h / DPI), dpi=DPI)
    fig.patch.set_alpha(0)

    if not full_frame:
        shadow = mpatches.FancyBboxPatch(
            (0.018, -0.005), 0.98, 0.98, transform=fig.transFigure,
            boxstyle="round,pad=0,rounding_size=0.035",
            linewidth=0, facecolor="#000000", alpha=0.35, zorder=-2,
        )
        fig.add_artist(shadow)
    card_margin = 0.02 if full_frame else 0.01
    card = mpatches.FancyBboxPatch(
        (card_margin, card_margin), 1 - 2 * card_margin, 1 - 2 * card_margin, transform=fig.transFigure,
        boxstyle="round,pad=0,rounding_size=0.02" if full_frame else "round,pad=0,rounding_size=0.035",
        linewidth=1.5, edgecolor=border_color, facecolor=SURFACE, zorder=-1,
    )
    fig.add_artist(card)

    img = mpimg.imread(image_path)
    img_h, img_w = img.shape[0], img.shape[1]
    img_aspect = img_w / img_h

    # photo area: contain-fit (never crop) within the card, leaving room
    # for the caption/credit strip at the bottom
    if full_frame:
        area_left, area_bottom, area_w, area_h = 0.15, 0.12, 0.70, 0.72
    else:
        area_left, area_bottom, area_w, area_h = 0.08, 0.16, 0.84, 0.68
    area_aspect = area_w * card_w / (area_h * card_h)
    if img_aspect > area_aspect:
        draw_w = area_w
        draw_h = area_w * card_w / img_aspect / card_h
    else:
        draw_h = area_h
        draw_w = area_h * card_h * img_aspect / card_w
    left = area_left + (area_w - draw_w) / 2
    bottom = area_bottom + (area_h - draw_h) / 2

    ax = fig.add_axes((left, bottom, draw_w, draw_h))
    ax.set_zorder(1)
    ax.imshow(img)
    ax.axis("off")

    title_fs, credit_fs = (30, 15) if full_frame else (24, 13)
    fig.text(0.5, 0.90, caption, color=INK_PRIMARY, fontsize=title_fs, fontweight="600", ha="center")
    fig.text(0.5, 0.06, credit, color=INK_SECONDARY, fontsize=credit_fs, ha="center")

    frame_path = out_path.with_suffix(".png")
    fig.savefig(frame_path, transparent=True)
    plt.close(fig)

    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(frame_path),
        "-t", f"{total_duration:.3f}", "-r", str(fps),
        "-c:v", "qtrle", str(out_path),
    ])
    frame_path.unlink()

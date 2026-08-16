"""Chart cards: bars grow in over ~2s (ease-out), then the highlighted bar
keeps a slow continuous pulse for the rest of the card's on-screen time
(see src/graphics/timing.py, a short beat, not held frozen for 40+
seconds). Styled per the dataviz skill's reference palette: emphasis form
(one accent, rest de-emphasis gray), thin capped bars, hairline gridlines,
ink-token typography.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from src.graphics.palette import (
    ACCENT, BASELINE, DEEMPHASIS, GRIDLINE, INK_MUTED, INK_PRIMARY,
    INK_SECONDARY, SURFACE,
)
from src.graphics.timing import FPS, GRAPHIC_ONSCREEN_SECONDS, REVEAL_SECONDS
from src.graphics.video_encode import frames_to_video

CARD_W, CARD_H = 1536, 860  # 80% of 1920x1080, leaves top/bottom margin
DPI = 100
BAR_WIDTH_FRAC = 0.38  # thin bars, generous air between them, not a "thick block"
PULSE_PERIOD = 1.8


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _card_figure(border_color: str):
    fig = plt.figure(figsize=(CARD_W / DPI, CARD_H / DPI), dpi=DPI)
    fig.patch.set_alpha(0)

    shadow = mpatches.FancyBboxPatch(
        (0.018, -0.005), 0.98, 0.98, transform=fig.transFigure,
        boxstyle="round,pad=0,rounding_size=0.035",
        linewidth=0, facecolor="#000000", alpha=0.35, zorder=-2,
    )
    fig.add_artist(shadow)
    card = mpatches.FancyBboxPatch(
        (0.01, 0.01), 0.98, 0.98, transform=fig.transFigure,
        boxstyle="round,pad=0,rounding_size=0.035",
        linewidth=1.5, edgecolor=border_color, facecolor=SURFACE, zorder=-1,
    )
    fig.add_artist(card)

    ax = fig.add_axes((0.09, 0.14, 0.82, 0.60))
    ax.set_zorder(1)
    ax.set_facecolor("none")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=INK_MUTED, labelsize=17)
    return fig, ax


def _rounded_bar(ax, x_center: float, width: float, height: float, color: str, glow: float = 0.0) -> None:
    if height <= 0:
        return
    r = min(width * 0.28, height * 0.12)
    if glow > 0:
        ax.add_patch(mpatches.FancyBboxPatch(
            (x_center - width / 2 - glow * 0.05, -r), width + glow * 0.1, height + r,
            boxstyle=f"round,pad=0,rounding_size={r}",
            mutation_aspect=1, linewidth=0, facecolor=color, alpha=0.25 * glow, zorder=2,
        ))
    ax.add_patch(mpatches.FancyBboxPatch(
        (x_center - width / 2, -r), width, height + r,
        boxstyle=f"round,pad=0,rounding_size={r}",
        mutation_aspect=1, linewidth=0, facecolor=color, zorder=3,
    ))


def _draw_frame(t: float, title: str, categories: list[str], values: list[float],
                 unit: str, highlight_index: int | None, subtitle: str,
                 border_color: str, value_labels: list[str] | None):
    reveal = _ease_out_cubic(min(t / REVEAL_SECONDS, 1.0))
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * (t - REVEAL_SECONDS) / PULSE_PERIOD) if t > REVEAL_SECONDS else 0.0

    fig, ax = _card_figure(border_color)
    colors = [ACCENT if i == highlight_index else DEEMPHASIS for i in range(len(categories))]
    eased_values = [v * reveal for v in values]

    xs = range(len(categories))
    for x, h, c, i in zip(xs, eased_values, colors, xs):
        glow = pulse if i == highlight_index else 0.0
        _rounded_bar(ax, x, BAR_WIDTH_FRAC, h, c, glow)

    if reveal > 0.85:
        labels = value_labels or [f"{v:,.1f}{unit}" for v in values]
        label_alpha = min((reveal - 0.85) / 0.15, 1.0)
        for x, v, label in zip(xs, values, labels):
            ax.text(x, v + max(values) * 0.035, label, ha="center", va="bottom",
                     color=INK_PRIMARY, fontsize=20, fontweight="600", alpha=label_alpha)

    ax.set_xlim(-0.7, len(categories) - 0.3)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(categories, color=INK_SECONDARY, fontsize=17)
    ax.set_ylim(0, max(values) * 1.22)
    ax.yaxis.set_visible(False)
    ax.grid(axis="y", color=GRIDLINE, linewidth=1.0, zorder=0)
    ax.axhline(0, color=BASELINE, linewidth=1.0, zorder=1)
    ax.set_axisbelow(True)

    fig.text(0.5, 0.90, title, color=INK_PRIMARY, fontsize=25, fontweight="600", ha="center")
    if subtitle:
        fig.text(0.5, 0.83, subtitle, color=INK_SECONDARY, fontsize=15, ha="center")
    return fig


def render_bar_chart_video(out_path: Path, title: str, categories: list[str], values: list[float],
                            total_duration: float, unit: str = "", highlight_index: int | None = None,
                            subtitle: str = "", border_color: str = ACCENT,
                            value_labels: list[str] | None = None) -> None:
    duration = min(total_duration, GRAPHIC_ONSCREEN_SECONDS)
    frame_dir = out_path.parent / f"_frames_{out_path.stem}"
    frame_dir.mkdir(exist_ok=True)
    n_frames = max(int(round(duration * FPS)), 1)

    for i in range(n_frames):
        t = i / FPS
        fig = _draw_frame(t, title, categories, values, unit, highlight_index, subtitle, border_color, value_labels)
        fig.savefig(frame_dir / f"f_{i:04d}.png", transparent=True)
        plt.close(fig)

    frames_to_video(frame_dir, out_path, FPS)
    shutil.rmtree(frame_dir, ignore_errors=True)

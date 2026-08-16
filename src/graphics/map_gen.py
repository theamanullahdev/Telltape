"""Route-map cards using REAL country coastlines (Natural Earth 110m via
src/graphics/geo.py) instead of abstract labeled boxes, plotted in plain
lon/lat (equirectangular, a real projection is overkill for a stylized
documentary map). Continuous motion for the whole on-screen duration, not
just an intro: the route draws itself in over ~2s, then a small marker
travels along the primary route on a loop for as long as the card is on
screen, plus a slow, subtle zoom, this is a short beat (see
src/graphics/timing.py), not something held frozen for 40+ seconds.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from src.graphics.geo import rings_in_view
from src.graphics.palette import DIVERGING_GOOD, INK_MUTED, INK_PRIMARY, SURFACE
from src.graphics.timing import FPS, GRAPHIC_ONSCREEN_SECONDS, REVEAL_SECONDS
from src.graphics.video_encode import frames_to_video

LAND = "#242422"       # one step off the card surface, not a saturated hue
LAND_EDGE = "#3a3a37"

CARD_W, CARD_H = 1536, 860
DPI = 100
LOOP_SECONDS = 3.2     # how long the traveling marker takes to cross the primary route once


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _card_figure(border_color: str, lon_range: tuple[float, float], lat_range: tuple[float, float], zoom: float):
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

    ax = fig.add_axes((0.04, 0.06, 0.92, 0.76))
    ax.set_zorder(1)
    ax.set_facecolor("none")

    lon_mid = sum(lon_range) / 2
    lat_mid = sum(lat_range) / 2
    lon_span = (lon_range[1] - lon_range[0]) / 2 / zoom
    lat_span = (lat_range[1] - lat_range[0]) / 2 / zoom
    ax.set_xlim(lon_mid - lon_span, lon_mid + lon_span)
    ax.set_ylim(lat_mid - lat_span, lat_mid + lat_span)
    ax.axis("off")
    return fig, ax


def _draw_coastlines(ax, lon_range, lat_range):
    for ring in rings_in_view(lon_range[0], lon_range[1], lat_range[0], lat_range[1]):
        ax.add_patch(mpatches.Polygon(
            ring, closed=True, facecolor=LAND, edgecolor=LAND_EDGE, linewidth=0.6, zorder=2,
        ))


def _path_length(path: list[tuple[float, float]]) -> list[float]:
    return [
        ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        for (x1, y1), (x2, y2) in zip(path[:-1], path[1:])
    ]


def _point_at_fraction(path: list[tuple[float, float]], frac: float) -> tuple[float, float]:
    seg_lengths = _path_length(path)
    total = sum(seg_lengths)
    if total == 0:
        return path[0]
    target = total * max(0.0, min(frac, 1.0))
    covered = 0.0
    for (x1, y1), (x2, y2), seg_len in zip(path[:-1], path[1:], seg_lengths):
        if covered + seg_len >= target:
            t = (target - covered) / seg_len if seg_len > 0 else 0
            return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        covered += seg_len
    return path[-1]


def _truncate_path(path: list[tuple[float, float]], frac: float) -> list[tuple[float, float]]:
    if frac >= 1.0 or len(path) < 2:
        return path
    seg_lengths = _path_length(path)
    total = sum(seg_lengths)
    target = total * frac
    out = [path[0]]
    covered = 0.0
    for (x1, y1), (x2, y2), seg_len in zip(path[:-1], path[1:], seg_lengths):
        if covered + seg_len >= target:
            remain = target - covered
            t = remain / seg_len if seg_len > 0 else 0
            out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
            return out
        out.append((x2, y2))
        covered += seg_len
    return out


def _draw_frame(t: float, title: str, lon_range, lat_range, points: list[dict],
                 routes: list[dict], border_color: str, primary_route_idx: int):
    reveal = _ease_out_cubic(min(t / REVEAL_SECONDS, 1.0))
    zoom = 1.0 + 0.05 * min(t / GRAPHIC_ONSCREEN_SECONDS, 1.0)  # slow, subtle zoom-in

    fig, ax = _card_figure(border_color, lon_range, lat_range, zoom)
    _draw_coastlines(ax, lon_range, lat_range)

    for i, route in enumerate(routes):
        color = route.get("color", DIVERGING_GOOD)
        style = route.get("style", "-")
        full_path = route["path"]
        drawn_path = _truncate_path(full_path, reveal)
        for (x1, y1), (x2, y2) in zip(drawn_path[:-1], drawn_path[1:]):
            ax.add_patch(FancyArrowPatch(
                (x1, y1), (x2, y2), connectionstyle="arc3,rad=0.12",
                arrowstyle="-|>", mutation_scale=16, linewidth=2.3,
                color=color, linestyle=style, zorder=5, alpha=0.9,
            ))
        if route.get("label") and reveal > 0.3:
            mx, my = drawn_path[-1]
            ax.text(mx, my + 2.2, route["label"], ha="center", color=color,
                    fontsize=14, fontweight="600", zorder=6, alpha=min(reveal * 2, 1.0))

        # continuous motion: a marker travels along the primary route on a loop,
        # once its reveal has finished, this is what keeps the card alive for
        # its whole on-screen time instead of freezing after the intro.
        if i == primary_route_idx and reveal >= 1.0:
            loop_t = (t - REVEAL_SECONDS) % LOOP_SECONDS
            frac = loop_t / LOOP_SECONDS
            mx, my = _point_at_fraction(full_path, frac)
            ax.scatter([mx], [my], s=90, color=INK_PRIMARY, edgecolor=color,
                       linewidth=2, zorder=8)

    point_alpha = min(reveal * 2.2, 1.0)
    for pt in points:
        x, y = pt["xy"]
        ax.scatter([x], [y], s=120, color=INK_PRIMARY, edgecolor=SURFACE, linewidth=2, zorder=10, alpha=point_alpha)
        ax.text(x, y - 2.2, pt["label"], ha="center", va="top", color=INK_PRIMARY,
                fontsize=15, fontweight="600", zorder=10, alpha=point_alpha)

    fig.text(0.5, 0.90, title, color=INK_PRIMARY, fontsize=22, fontweight="600", ha="center")
    return fig


def render_route_map_video(out_path: Path, title: str, lon_range: tuple[float, float],
                            lat_range: tuple[float, float], points: list[dict], routes: list[dict],
                            total_duration: float, border_color: str = DIVERGING_GOOD,
                            primary_route_idx: int = -1) -> None:
    duration = min(total_duration, GRAPHIC_ONSCREEN_SECONDS)
    frame_dir = out_path.parent / f"_frames_{out_path.stem}"
    frame_dir.mkdir(exist_ok=True)
    n_frames = max(int(round(duration * FPS)), 1)
    primary = primary_route_idx if primary_route_idx >= 0 else len(routes) - 1

    for i in range(n_frames):
        t = i / FPS
        fig = _draw_frame(t, title, lon_range, lat_range, points, routes, border_color, primary)
        fig.savefig(frame_dir / f"f_{i:04d}.png", transparent=True)
        plt.close(fig)

    frames_to_video(frame_dir, out_path, FPS)
    shutil.rmtree(frame_dir, ignore_errors=True)

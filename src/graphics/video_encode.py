"""Turns a sequence of transparent PNG frames into a short alpha-channel
video clip (QuickTime Animation codec, lossless, alpha-capable, fast to
encode), then extends it by holding the last frame for `hold_extra_seconds`.
This is what makes a chart/map an actual ~2s motion graphic (bars growing,
a route drawing itself in) instead of a static image, without paying to
render every frame of a 30-60s hold.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr[-3000:]}")


def frames_to_video(frame_dir: Path, out_path: Path, fps: int) -> None:
    """Every frame is individually rendered (continuous motion for the
    whole clip), no separate hold-extension pass needed."""
    _run([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", str(frame_dir / "f_%04d.png"),
        "-c:v", "qtrle", str(out_path),
    ])


def frames_to_held_video(frame_dir: Path, out_path: Path, fps: int, hold_extra_seconds: float) -> None:
    frames = sorted(frame_dir.glob("f_*.png"))
    n_frames = len(frames)

    intro = out_path.with_name(out_path.stem + "_intro.mov")
    _run([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", str(frame_dir / "f_%04d.png"),
        "-c:v", "qtrle", str(intro),
    ])

    if hold_extra_seconds > 0.05:
        last_frame = frames[-1]
        hold = out_path.with_name(out_path.stem + "_hold.mov")
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(last_frame),
            "-t", f"{hold_extra_seconds:.3f}", "-c:v", "qtrle", str(hold),
        ])
        concat_list = out_path.with_name(out_path.stem + "_concat.txt")
        concat_list.write_text(f"file '{intro.resolve()}'\nfile '{hold.resolve()}'\n")
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(out_path)])
        concat_list.unlink()
        hold.unlink()
        intro.unlink()
    else:
        intro.rename(out_path)

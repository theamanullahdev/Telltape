"""Measures actual pixel motion in a downloaded clip, the objective check
for "is this really a video, or a near-static shot that a zoom would make
look like a photo". Metadata/tags can't tell you this; only the pixels can.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

SAMPLE_W, SAMPLE_H = 160, 90
MOTION_THRESHOLD = 4.0  # mean abs pixel diff (0-255 gray) between two frames ~1.5s apart


def motion_score(clip_path: Path) -> float:
    """Grabs two downscaled grayscale frames ~1.5s apart and returns the
    mean absolute pixel difference. Near-zero means the shot is
    effectively static (locked-off camera, barely-moving subject)."""
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(clip_path),
            "-vf", f"select='eq(n\\,3)+eq(n\\,45)',scale={SAMPLE_W}:{SAMPLE_H}",
            "-vsync", "0", "-frames:v", "2",
            "-f", "image2pipe", "-pix_fmt", "gray", "-vcodec", "rawvideo", "-",
        ],
        capture_output=True,
    )
    frame_size = SAMPLE_W * SAMPLE_H
    data = proc.stdout
    if len(data) < frame_size * 2:
        return 0.0  # couldn't get two distinct frames, treat as suspect
    f1 = np.frombuffer(data[:frame_size], dtype=np.uint8).astype(np.int16)
    f2 = np.frombuffer(data[frame_size:frame_size * 2], dtype=np.uint8).astype(np.int16)
    return float(np.abs(f1 - f2).mean())


def has_motion(clip_path: Path) -> bool:
    return motion_score(clip_path) >= MOTION_THRESHOLD

"""Renders 'map'/'chart' scenes whose scenes.json entry already carries a
hand-authored `params` block into an animated alpha video card under
projects/<slug>/graphics/. Background footage for these scenes is resolved
separately in src/footage/resolve.py and composited underneath in assembly.
The graphic is an overlay, not a replacement for scene footage.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.common.logging_setup import get_logger
from src.graphics.chart_gen import render_bar_chart_video
from src.graphics.map_gen import render_route_map_video

log = get_logger(__name__)


def resolve_scene_graphics(project_root: Path) -> None:
    scenes = json.loads((project_root / "scenes.json").read_text())
    graphics_dir = project_root / "graphics"
    graphics_dir.mkdir(exist_ok=True)

    changed = False
    for i, scene in enumerate(scenes):
        visual = scene["visual"]
        if visual["type"] not in ("map", "chart") or "graphic_path" in visual or "params" not in visual:
            continue

        out_path = graphics_dir / f"scene_{i:02d}.mov"
        params = visual["params"]
        duration = scene["end"] - scene["start"]

        if visual["type"] == "chart":
            render_bar_chart_video(out_path, total_duration=duration, **params["args"])
        else:
            render_route_map_video(out_path, total_duration=duration, **params["args"])

        visual["graphic_path"] = str(out_path.relative_to(project_root))
        log.info("scene %d: rendered animated %s -> %s", i, visual["type"], out_path.name)
        changed = True

    if changed:
        (project_root / "scenes.json").write_text(json.dumps(scenes, indent=2))

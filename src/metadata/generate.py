"""Builds output/<slug>/metadata.json: title, chapters (from scene
boundaries), sources/attributions (from the footage index), narration stats.
Templated for now. It keeps the output folder's video and JSON metadata
together while leaving title and description writing to the project author.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.common.config import output_dir
from src.common import project

_VISUAL_PREFIX_RE = re.compile(r"^VISUAL:\s*", re.I)


def _chapter_label(note: str | None, fallback: str) -> str:
    if not note:
        return fallback
    clean = _VISUAL_PREFIX_RE.sub("", note).strip()
    return clean[:60] or fallback


def generate_metadata(project_root: Path) -> Path:
    state = project.load_state(project_root)
    scenes = json.loads((project_root / "scenes.json").read_text())

    chapters = []
    for i, scene in enumerate(scenes):
        chapters.append({
            "time": round(scene["start"], 1),
            "label": _chapter_label(scene["visual"].get("query"), f"scene {i + 1}"),
        })

    sources = []
    for scene in scenes:
        src = scene["visual"].get("source")
        if src:
            sources.append(src)

    duration = scenes[-1]["end"] if scenes else 0.0

    metadata = {
        "title": state["title"],
        "slug": state["slug"],
        "duration_seconds": round(duration, 1),
        "created_at": state["created_at"],
        "chapters": chapters,
        "sources": sources,
        "script_path": "script.md",  # relative to projects/<slug>/, not output/<slug>/
    }

    out_dir = output_dir() / project_root.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "metadata.json"
    out_path.write_text(json.dumps(metadata, indent=2))

    project.mark_stage_done(project_root, "metadata")
    return out_path

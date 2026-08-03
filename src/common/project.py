"""Project scaffold + state. A project is a directory under projects/<slug>/
holding working files; output/<slug>/ holds the final deliverables.

project.json is the single resumability record: which stages are done, so
`main.py render <slug>` can skip whatever's already on disk.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import projects_dir
from .slugify import unique_project_slug

STAGES = ["script", "scenes", "narration", "visuals", "assembly", "metadata"]


def create_project(title: str) -> Path:
    slug = unique_project_slug(title)
    root = projects_dir() / slug
    for sub in ("audio", "footage", "graphics", "cache"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    (root / "script.md").write_text(f"# {title}\n\n<!-- script goes here -->\n")

    state = {
        "title": title,
        "slug": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stages_done": [],
    }
    save_state(root, state)
    return root


def load_state(project_root: Path) -> dict:
    with open(project_root / "project.json") as f:
        return json.load(f)


def save_state(project_root: Path, state: dict) -> None:
    with open(project_root / "project.json", "w") as f:
        json.dump(state, f, indent=2)


def mark_stage_done(project_root: Path, stage: str) -> None:
    assert stage in STAGES, f"unknown stage {stage!r}"
    state = load_state(project_root)
    if stage not in state["stages_done"]:
        state["stages_done"].append(stage)
        save_state(project_root, state)


def project_path(slug: str) -> Path:
    root = projects_dir() / slug
    if not root.exists():
        raise FileNotFoundError(f"no project at {root}")
    return root

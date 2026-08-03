"""CLI entry point for the local documentary pipeline.

    python main.py new "Why Container Ships Are So Cheap"
    python main.py list
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.common import project
from src.common.config import projects_dir


def cmd_narrate(args):
    root = project.project_path(args.slug)
    from src.tts.narrate import generate_narration
    generate_narration(root, voice=args.voice, speed=args.speed)


def cmd_scenes(args):
    root = project.project_path(args.slug)
    from src.common.scenes import build_scenes
    path = build_scenes(root)
    print(f"wrote {path}")


def cmd_footage(args):
    root = project.project_path(args.slug)
    from src.footage.resolve import resolve_scene_footage
    from src.graphics.resolve import resolve_scene_graphics
    resolve_scene_graphics(root)  # map/chart scenes first (no API calls, instant)
    resolve_scene_footage(root)


def cmd_assemble(args):
    root = project.project_path(args.slug)
    from src.render.assemble import assemble
    path = assemble(root)
    print(f"wrote {path}")


def cmd_render(args):
    """Runs every stage end to end, skipping whatever's already done."""
    root = project.project_path(args.slug)
    state = project.load_state(root)
    done = set(state["stages_done"])

    if "narration" not in done:
        from src.tts.narrate import generate_narration
        generate_narration(root)
    if "scenes" not in done:
        from src.common.scenes import build_scenes
        build_scenes(root)
    if "visuals" not in done:
        from src.footage.resolve import resolve_scene_footage
        from src.graphics.resolve import resolve_scene_graphics
        resolve_scene_graphics(root)
        resolve_scene_footage(root)
    if "assembly" not in done:
        from src.render.assemble import assemble
        assemble(root)
    if "metadata" not in done:
        from src.metadata.generate import generate_metadata
        generate_metadata(root)
    print(f"done: output/{args.slug}/final.mp4")


def cmd_metadata(args):
    root = project.project_path(args.slug)
    from src.metadata.generate import generate_metadata
    path = generate_metadata(root)
    print(f"wrote {path}")


def cmd_new(args):
    root = project.create_project(args.title)
    print(f"created project '{root.name}' at {root}")


def cmd_list(args):
    for p in sorted(projects_dir().glob("*")):
        if p.is_dir():
            state = project.load_state(p)
            done = ", ".join(state["stages_done"]) or "none"
            print(f"{p.name}: stages done = [{done}]")


def main():
    parser = argparse.ArgumentParser(description="Documentary Factory CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a new project")
    p_new.add_argument("title")
    p_new.set_defaults(func=cmd_new)

    p_list = sub.add_parser("list", help="list projects and stage progress")
    p_list.set_defaults(func=cmd_list)

    p_narrate = sub.add_parser("narrate", help="generate narration.wav + words.json from script.md")
    p_narrate.add_argument("slug")
    p_narrate.add_argument("--voice", default=None)
    p_narrate.add_argument("--speed", type=float, default=None)
    p_narrate.set_defaults(func=cmd_narrate)

    p_scenes = sub.add_parser("scenes", help="build scenes.json from script.md + words.json")
    p_scenes.add_argument("slug")
    p_scenes.set_defaults(func=cmd_scenes)

    p_footage = sub.add_parser("footage", help="resolve+download stock footage for each scene")
    p_footage.add_argument("slug")
    p_footage.set_defaults(func=cmd_footage)

    p_assemble = sub.add_parser("assemble", help="render final.mp4 from resolved scenes.json")
    p_assemble.add_argument("slug")
    p_assemble.set_defaults(func=cmd_assemble)

    p_render = sub.add_parser("render", help="run all stages end to end (resumable)")
    p_render.add_argument("slug")
    p_render.set_defaults(func=cmd_render)

    p_metadata = sub.add_parser("metadata", help="write output/<slug>/metadata.json")
    p_metadata.add_argument("slug")
    p_metadata.set_defaults(func=cmd_metadata)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

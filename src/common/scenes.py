"""Builds scenes.json: aligns script.md paragraphs to word-level narration
timestamps, and classifies each paragraph's visual production note into a
visual directive (footage search query, or a map/chart placeholder for
stages not built yet).

This is the one place project structure turns a script and visual notes into
the deterministic manifest the rest of the pipeline consumes.
"""

import json
import re
from pathlib import Path

from src.common import project
from src.common.script import parse_paragraphs

_MAP_KEYWORDS = re.compile(r"\bmap\b", re.I)
_CHART_KEYWORDS = re.compile(r"\b(chart|graph)\b", re.I)
_VISUAL_PREFIX_RE = re.compile(r"^VISUAL:\s*", re.I)


def _is_real_word(token: str) -> bool:
    return any(c.isalnum() for c in token)


def _classify(note: str | None) -> tuple[str, str]:
    """Returns (visual_type, query_or_description)."""
    if not note:
        return "footage", ""
    clean = _VISUAL_PREFIX_RE.sub("", note).strip()
    if _MAP_KEYWORDS.search(clean):
        return "map", clean
    if _CHART_KEYWORDS.search(clean):
        return "chart", clean
    return "footage", clean


def build_scenes(project_root: Path) -> Path:
    script_md = (project_root / "script.md").read_text()
    words = json.loads((project_root / "audio" / "words.json").read_text())

    paragraphs = parse_paragraphs(script_md)

    scenes = []
    word_idx = 0
    for para in paragraphs:
        target_count = len(para["text"].split())
        start_idx = word_idx
        consumed = 0
        while word_idx < len(words) and consumed < target_count:
            if _is_real_word(words[word_idx]["word"]):
                consumed += 1
            word_idx += 1
        # absorb trailing punctuation-only tokens into this scene
        while word_idx < len(words) and not _is_real_word(words[word_idx]["word"]):
            word_idx += 1

        if start_idx >= len(words):
            break  # ran out of timed words (shouldn't happen if counts line up)

        end_word_idx = min(word_idx, len(words)) - 1
        visual_type, query = _classify(para["visual_note"])

        scenes.append({
            "start": words[start_idx]["start"],
            "end": words[end_word_idx]["end"],
            "narration": para["text"],
            "visual": {"type": visual_type, "query": query},
        })

    out_path = project_root / "scenes.json"
    out_path.write_text(json.dumps(scenes, indent=2))
    project.mark_stage_done(project_root, "scenes")
    return out_path

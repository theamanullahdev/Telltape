"""words.json -> burned-in captions .srt. Groups words into small on-screen
chunks (max words / max on-screen seconds, whichever hits first), Kokoro
tokenizes punctuation as separate word entries, so trailing punctuation is
hugged onto the preceding word instead of getting its own space.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_WORDS = 5
MAX_SECONDS = 2.5
_NO_SPACE_BEFORE = {",", ".", "!", "?", ";", ":", "'", "’", "”", ")", "]"}


def _join_words(words: list[dict]) -> str:
    out = ""
    for w in words:
        token = w["word"]
        if out and token not in _NO_SPACE_BEFORE:
            out += " "
        out += token
    return out


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: list[dict]) -> str:
    groups: list[list[dict]] = []
    current: list[dict] = []

    for w in words:
        if current and (
            len(current) >= MAX_WORDS
            or (w["end"] - current[0]["start"]) > MAX_SECONDS
        ):
            groups.append(current)
            current = []
        current.append(w)
    if current:
        groups.append(current)

    lines = []
    for i, group in enumerate(groups, start=1):
        start = _srt_timestamp(group[0]["start"])
        end = _srt_timestamp(group[-1]["end"])
        text = _join_words(group)
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def generate_srt(project_root: Path) -> Path:
    words = json.loads((project_root / "audio" / "words.json").read_text())
    srt_path = project_root / "cache" / "captions.srt"
    srt_path.parent.mkdir(exist_ok=True)
    srt_path.write_text(build_srt(words))
    return srt_path

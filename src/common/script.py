"""Turns a project's script.md into clean narration text: strips the
production-note HTML comments and the title heading, keeps only what should
actually be spoken.
"""

import re

_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_COMMENT_LINE_RE = re.compile(r"^<!--\s*(.*?)\s*-->$")
_HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.M)


def extract_narration_text(script_md: str) -> str:
    text = _COMMENT_RE.sub("", script_md)
    text = _HEADING_RE.sub("", text)
    lines = [line.strip() for line in text.splitlines()]
    paragraphs = " ".join(line for line in lines if line)
    return re.sub(r"\s+", " ", paragraphs).strip()


def parse_paragraphs(script_md: str) -> list[dict]:
    """Splits script.md into narration paragraphs, each tagged with the
    visual production-note comment that immediately preceded it (if any).
    A paragraph is a run of non-blank, non-comment, non-heading lines.
    """
    # Multi-line comments (e.g. the file-level intro note) never carry a
    # per-paragraph visual cue, so strip them wholesale before scanning
    # line-by-line for the single-line "<!-- VISUAL: ... -->" cues.
    single_line_only = _COMMENT_RE.sub(
        lambda m: m.group(0) if "\n" not in m.group(0) else "", script_md
    )

    pending_note = None
    current: list[str] = []
    paragraphs: list[dict] = []

    def flush():
        nonlocal current, pending_note
        if current:
            paragraphs.append({"visual_note": pending_note, "text": " ".join(current)})
            current = []
            pending_note = None

    for raw_line in single_line_only.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        m = _COMMENT_LINE_RE.match(line)
        if m:
            pending_note = m.group(1)
            continue
        if _HEADING_RE.match(line):
            continue
        current.append(line)
    flush()
    return paragraphs

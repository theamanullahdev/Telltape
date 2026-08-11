"""Resolves EVERY scene's background into a list of sub-cut segments (hard
cuts every few seconds, Wendover-style pacing, a scene is never one clip
stretched/looped for its whole 30-60s span). This runs for 'map'/'chart'
scenes too: the animated graphic (src/graphics/resolve.py) is composited
*on top* of this background in assembly, not instead of it, footage and
motion graphics are layers, not mutually exclusive.

Search queries come from the scene's *narration text*, not its production
visual-note shorthand, notes like "split screen, stock exchange ticker" or
"logos assembling" describe a graphic (Phase 4-6's job), and searching stock
footage for those literal words returns nonsense (crypto reels, YouTube
subscribe buttons). Narration text is natural English about the real
subject, which stock search actually matches well against.

Writes segments straight back into scenes.json (so assembly is a pure read
of that one file) and keeps a parallel footage/_index.json as the
human-readable license/attribution record.
"""

from __future__ import annotations

import itertools
import json
import random
import re
from pathlib import Path

from src.common import project
from src.common.config import get_config
from src.common.logging_setup import get_logger
from src.footage.motion import motion_score, MOTION_THRESHOLD
from src.footage.pexels import best_file, download_file, search_videos

log = get_logger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z']+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "as", "is", "was", "were", "are", "be", "been", "being", "it",
    "its", "this", "that", "these", "those", "his", "her", "their", "them",
    "he", "she", "they", "you", "your", "i", "we", "us", "our", "not", "no",
    "so", "than", "then", "there", "here", "into", "over", "under", "out",
    "up", "down", "off", "if", "when", "while", "by", "from", "about",
    "most", "more", "just", "also", "still", "even", "back", "one",
    "s", "d", "ll", "re", "ve", "t", "m",
    # proper nouns from this script that collide with unrelated stock
    # categories on Pexels, "koi" (the ship, from the Red Sea missile
    # incident) matched literal koi-fish-pond footage instead of anything
    # shipping-related.
    "koi",
}


def _keywords_from_narration(text: str, max_words: int = 8) -> list[str]:
    seen: list[str] = []
    for w in _WORD_RE.findall(text.lower()):
        w = w.strip("'")
        if len(w) < 3 or w in _STOPWORDS or w in seen:
            continue
        seen.append(w)
        if len(seen) >= max_words:
            break
    return seen


def _score(video: dict, keywords: list[str]) -> int:
    haystack = (video.get("url", "") + " " + " ".join(video.get("tags", []))).lower()
    return sum(1 for k in keywords if k in haystack)


# This is a corporate/infrastructure documentary (ships, ports, maps,
# money), talking-head/portrait/lifestyle people footage reads as random
# filler, not b-roll for the subject, so it's excluded outright rather than
# just deprioritized. Deliberately broad: a miss here (a person on screen
# who isn't the subject) is worse than an occasional false-positive
# exclusion of footage that would have been fine.
_PEOPLE_TERMS = {
    "portrait", "face", "faces", "selfie", "model", "smiling", "smile",
    "handshake", "meeting", "businessman", "businessperson", "businesswoman",
    "worker", "family", "child", "children", "kid", "kids", "baby", "woman",
    "women", "man", "men", "boy", "girl", "guy", "lady", "gentleman", "human",
    "people", "person", "couple", "friends", "close-up-of-a", "closeup-of-a",
    "closeup", "close-up", "eyes-closed", "eyes closed", "curly-hair",
    "hairstyle", "makeup", "beauty", "skincare", "spa", "wellness",
    "lifestyle", "using-a-laptop", "using-a-tablet", "typing", "video-call",
    "remote-work", "office-worker", "sitting", "relaxing", "studio-shot",
    "indoor-portrait", "headshot", "influencer", "vlogger", "talking",
    "agent", "realtor", "client", "clients", "customer", "salesperson",
    "consultant", "handing-over", "showing-the-property", "wedding",
    "celebration", "dancing", "dance", "party", "crowd", "gathering",
    "celebrating", "festival", "concert", "audience",
}


def _is_people_footage(video: dict) -> bool:
    haystack = (video.get("url", "") + " " + " ".join(video.get("tags", []))).lower()
    return any(term in haystack for term in _PEOPLE_TERMS)


def _split_into_subcuts(duration: float, lo: float, hi: float) -> list[float]:
    lengths = []
    remaining = duration
    while remaining > hi:
        length = random.uniform(lo, hi)
        lengths.append(length)
        remaining -= length
    if lengths and remaining < lo * 0.6:
        lengths[-1] += remaining  # too-short tail: fold into previous cut
    else:
        lengths.append(max(remaining, 0.5))
    return lengths


# Populated during resolve_scene_footage() when a scene had literally no
# candidate that cleared the motion threshold, surfaced to the user
# explicitly rather than silently shipping a near-static clip.
LOW_MOTION_FALLBACKS: list[dict] = []


def resolve_scene_footage(project_root: Path) -> Path:
    LOW_MOTION_FALLBACKS.clear()
    cfg = get_config()["footage"]
    lo, hi = cfg["subcut_seconds"]

    scenes = json.loads((project_root / "scenes.json").read_text())
    footage_dir = project_root / "footage"
    footage_dir.mkdir(exist_ok=True)

    index_path = footage_dir / "_index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}

    for i, scene in enumerate(scenes):
        visual = scene["visual"]
        if "segments" in visual:
            continue  # already resolved, resumable

        keywords = _keywords_from_narration(scene["narration"])
        query = " ".join(keywords) or "documentary b-roll"
        log.info("scene %d: searching pexels for %r", i, query)

        results = search_videos(query, per_page=25)
        candidates = [(v, best_file(v)) for v in results]
        candidates = [(v, f) for v, f in candidates if f and not _is_people_footage(v)]

        if not candidates:
            log.warning("scene %d: no results for %r, using fallback query", i, query)
            results = search_videos("cargo ship shipping port containers", per_page=15)
            candidates = [(v, best_file(v)) for v in results]
            candidates = [(v, f) for v, f in candidates if f and not _is_people_footage(v)]
        if not candidates:
            raise RuntimeError(f"scene {i}: could not resolve any footage (even fallback query)")

        candidates.sort(key=lambda vf: _score(vf[0], keywords), reverse=True)

        duration = scene["end"] - scene["start"]
        subcut_lengths = _split_into_subcuts(duration, lo, hi)

        # A narrow query (e.g. a specific phrase like "last mile delivery")
        # can leave too few candidates after the people-filter to cover
        # every sub-cut distinctly, top up with a broader query (fewer
        # keywords) rather than silently repeating the same one or two
        # clips across a whole scene.
        seen_ids = {v["id"] for v, _f in candidates}
        broaden_attempts = 0
        while len(candidates) < len(subcut_lengths) * 2 and broaden_attempts < len(keywords) - 2:
            broaden_attempts += 1
            broader_query = " ".join(keywords[: max(len(keywords) - broaden_attempts, 2)])
            extra_results = search_videos(broader_query, per_page=25)
            extra = [(v, best_file(v)) for v in extra_results]
            extra = [(v, f) for v, f in extra if f and not _is_people_footage(v) and v["id"] not in seen_ids]
            for v, f in extra:
                seen_ids.add(v["id"])
                candidates.append((v, f))
            candidates.sort(key=lambda vf: _score(vf[0], keywords), reverse=True)

        # Download+measure candidates in score order, keep only ones that
        # actually have visible motion (a locked-off/near-static stock
        # "video" combined with our Ken Burns zoom is indistinguishable
        # from a zoomed photo, this is the objective check, not a guess
        # from tags). One distinct validated clip per sub-cut; only repeat
        # a clip if we've exhausted every candidate.
        validated: list[tuple[dict, dict, float]] = []
        for video, file in candidates:
            if len(validated) >= len(subcut_lengths):
                break
            clip_path = footage_dir / f"{video['id']}.mp4"
            if not clip_path.exists():
                download_file(file["link"], clip_path)
            score = motion_score(clip_path)
            if score >= MOTION_THRESHOLD:
                validated.append((video, file, score))
            else:
                log.info("scene %d: rejected pexels video %d for low motion (score %.1f)", i, video["id"], score)

        used_low_motion_fallback = False
        if not validated:
            # Nothing passed, use the single highest-motion candidate
            # available rather than failing the scene, but this gets
            # reported to the user explicitly (see summary at the end).
            scored_all = []
            for video, file in candidates[:5]:
                clip_path = footage_dir / f"{video['id']}.mp4"
                if not clip_path.exists():
                    download_file(file["link"], clip_path)
                scored_all.append((video, file, motion_score(clip_path)))
            video, file, score = max(scored_all, key=lambda t: t[2])
            validated = [(video, file, score)]
            used_low_motion_fallback = True
            log.warning("scene %d: NO candidate cleared the motion threshold, using best available "
                        "(video %d, score %.1f)", i, video["id"], score)

        pool_cycle = itertools.cycle(validated)

        segments = []
        for length in subcut_lengths:
            video, file, score = next(pool_cycle)
            clip_path = footage_dir / f"{video['id']}.mp4"

            source = {
                "provider": "pexels",
                "id": video["id"],
                "url": video["url"],
                "photographer": video["user"]["name"],
                "photographer_url": video["user"]["url"],
                "license": "Pexels License (free to use, no attribution required)",
                "motion_score": round(score, 1),
            }
            segments.append({
                "clip_path": str(clip_path.relative_to(project_root)),
                "duration": length,
                "source": source,
            })
            index[str(video["id"])] = source
            if used_low_motion_fallback:
                LOW_MOTION_FALLBACKS.append({
                    "scene": i, "video_id": video["id"], "score": round(score, 1),
                    "duration": round(length, 1), "narration": scene["narration"][:80],
                })

        visual["segments"] = segments
        visual.pop("clip_path", None)
        visual.pop("source", None)

    (project_root / "scenes.json").write_text(json.dumps(scenes, indent=2))
    index_path.write_text(json.dumps(index, indent=2))
    project.mark_stage_done(project_root, "visuals")
    if LOW_MOTION_FALLBACKS:
        log.warning("LOW-MOTION FALLBACKS USED (no better candidate existed): %s", LOW_MOTION_FALLBACKS)
    return footage_dir

"""Pexels video search/download client. Free stock footage, no attribution
legally required (tracked anyway in the per-project footage index for
compliance/documentation).
"""

from __future__ import annotations

import requests

from src.common.config import get_config, require_env
from src.common.logging_setup import get_logger

log = get_logger(__name__)

SEARCH_URL = "https://api.pexels.com/videos/search"
TARGET_WIDTH = 1920


def _api_key() -> str:
    env_var = get_config()["footage"]["api_key_env"]
    return require_env(env_var)


def search_videos(query: str, per_page: int = 5) -> list[dict]:
    r = requests.get(
        SEARCH_URL,
        headers={"Authorization": _api_key()},
        params={"query": query, "per_page": per_page, "orientation": "landscape"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("videos", [])


def best_file(video: dict, target_width: int = TARGET_WIDTH) -> dict | None:
    """Picks the smallest video_file whose width is >= target_width (avoids
    downloading 4K when 1080p is what we'll scale to), falling back to the
    largest available if nothing meets the target."""
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"]
    if not files:
        return None
    candidates = sorted((f for f in files if f["width"] >= target_width), key=lambda f: f["width"])
    return candidates[0] if candidates else max(files, key=lambda f: f["width"])


def download_file(url: str, dest_path) -> None:
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)

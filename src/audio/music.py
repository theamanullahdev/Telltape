"""Freesound.org music bed search/download. Only CC0 and plain CC-BY
tracks are used, NC (non-commercial) is excluded since the video may be
monetized, SA/ND excluded to avoid derivative-work licensing complications
from mixing/ducking the track under narration.
"""

from __future__ import annotations

from pathlib import Path

import requests

from src.common.config import get_config, require_env
from src.common.logging_setup import get_logger

log = get_logger(__name__)

SEARCH_URL = "https://freesound.org/apiv2/search/text/"


def _api_key() -> str:
    env_var = get_config()["music"]["api_key_env"]
    return require_env(env_var)


def _license_allowed(license_url: str) -> bool:
    return "/by/" in license_url or "publicdomain/zero" in license_url


def search_tracks(query: str, min_duration: float, per_page: int = 15) -> list[dict]:
    r = requests.get(
        SEARCH_URL,
        params={
            "query": query,
            "token": _api_key(),
            "filter": f"duration:[{int(min_duration)} TO 600]",
            "fields": "id,name,duration,previews,license,username,url",
            "sort": "downloads_desc",
            "page_size": per_page,
        },
        timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return [t for t in results if _license_allowed(t["license"])]


def download_track(track: dict, dest_path: Path) -> None:
    url = track["previews"]["preview-hq-mp3"]
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)


def resolve_music(project_root: Path, query: str, min_duration: float) -> tuple[Path, dict] | None:
    """Returns (mp3_path, source_metadata) or None if no licensed track fits."""
    audio_dir = project_root / "audio"
    audio_dir.mkdir(exist_ok=True)
    music_path = audio_dir / "music.mp3"
    meta_path = audio_dir / "music_source.json"

    if music_path.exists() and meta_path.exists():
        import json
        return music_path, json.loads(meta_path.read_text())

    tracks = search_tracks(query, min_duration)
    if not tracks:
        log.warning("no CC0/CC-BY freesound tracks found for %r (min %.0fs)", query, min_duration)
        return None

    track = tracks[0]  # already sorted by downloads_desc, most-used tracks tend to be cleaner/more usable
    download_track(track, music_path)

    source = {
        "provider": "freesound",
        "id": track["id"],
        "name": track["name"],
        "username": track["username"],
        "url": track["url"],
        "license": track["license"],
    }
    import json
    meta_path.write_text(json.dumps(source, indent=2))
    log.info("music: downloaded %r by %s (%s)", track["name"], track["username"], track["license"])
    return music_path, source

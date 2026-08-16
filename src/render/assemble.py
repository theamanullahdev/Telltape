"""Assembly, layered not recomposed: every scene's background is its own
sub-cut stock-footage segments (fast pacing, hard cuts every few seconds),
each one a straight scale/crop trim of the source clip, real playback,
NO synthetic zoom/pan of any kind. (History: an earlier version applied a
Ken Burns zoom via ffmpeg's zoompan filter with d=<segment-frame-count>.
That parameter means "hold this one input frame and generate this many
OUTPUT frames from it before advancing", the correct usage for animating a
single still image, but on video input it effectively freezes each segment
on close to its first frame and crawls through the source at a tiny
fraction of real speed, i.e. exactly "screenshot it and zoom," which is the
opposite of what a broll-only edit wants. Removed outright rather than
"fixed", no camera move is layered on footage here anymore, ever.)
Segments join via short crossfade dissolves instead of hard concat. Source
clips are pre-validated for real pixel motion (src/footage/motion.py), so
what's actually driving the shot is the footage itself. Scenes with a
'map'/'chart' graphic get exactly ONE extra ffmpeg pass, overlaying the
animated card (rounded, bordered, ~80% width) on top of that scene's
background, centered, so footage keeps playing behind the graphic instead
of the graphic replacing it. There's exactly one final re-encode for the
whole video: burning captions + mixing narration/music.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.audio.music import resolve_music
from src.common import project
from src.common.config import get_config, output_dir
from src.common.logging_setup import get_logger
from src.graphics.timing import GRAPHIC_ONSCREEN_SECONDS
from src.subtitles.srt_gen import generate_srt

log = get_logger(__name__)

OVERLAY_WIDTH_FRAC = 0.80
XFADE_DURATION = 0.35  # short dissolve between clips, a transition, not a slow melt


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr[-4000:]}")


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def _render_video_segment(clip_path: Path, duration: float, width: int, height: int, fps: int,
                           out_path: Path) -> None:
    """Straight trim: scale/crop to frame, normalize fps (needed for the
    crossfade/concat steps downstream, not for any visual effect), no zoom,
    no pan. -stream_loop -1 only kicks in if a source sub-cut is shorter
    than the target duration; real footage otherwise plays at 1x speed
    start to finish."""
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},format=yuv420p"
    cmd = [
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(clip_path),
        "-vf", vf, "-t", f"{duration:.3f}",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(out_path),
    ]
    _run(cmd)


def _concat(paths: list[Path], list_file: Path, out_path: Path) -> None:
    """Hard-cut concat (stream copy, free), used only where a clean cut is
    correct (e.g. joining a graphic overlay onto its plain-footage tail)."""
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)])


def _crossfade_concat(paths: list[Path], out_path: Path) -> None:
    """Joins clips with a short dissolve instead of a hard cut, this is
    the 'transitions between clips' pass. Requires a real re-encode (xfade
    can't stream-copy), so it's used where the transition actually matters:
    between b-roll sub-cuts, not for every internal cache step."""
    if len(paths) == 1:
        import shutil
        shutil.copy(paths[0], out_path)
        return

    durations = [_probe_duration(p) for p in paths]
    cmd = ["ffmpeg", "-y"]
    for p in paths:
        cmd += ["-i", str(p)]

    # xfade requires every input to share a timebase, source clips carry
    # different container timebases (15360, 60000, ...) even though we
    # already normalized to 30fps content, so ffmpeg refuses to chain them
    # without an explicit fps+settb pass first.
    filter_parts = [f"[{i}:v]fps=30,settb=1/30[n{i}]" for i in range(len(paths))]
    running = durations[0]
    prev_label = "n0"
    for i in range(1, len(paths)):
        offset = max(running - XFADE_DURATION, 0.0)
        out_label = f"v{i}" if i < len(paths) - 1 else "vout"
        filter_parts.append(
            f"[{prev_label}][n{i}]xfade=transition=fade:duration={XFADE_DURATION}:offset={offset:.3f}[{out_label}]"
        )
        running = running + durations[i] - XFADE_DURATION
        prev_label = out_label

    cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[vout]"]
    cmd += ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out_path)]
    _run(cmd)


def _overlay_graphic(bg_path: Path, graphic_path: Path, width: int, height: int, out_path: Path) -> None:
    overlay_w = int(width * OVERLAY_WIDTH_FRAC)
    filter_complex = (
        f"[0:v]format=yuv420p[bg];"
        f"[1:v]scale={overlay_w}:-1[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto[out]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(bg_path), "-i", str(graphic_path),
        "-filter_complex", filter_complex, "-map", "[out]",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-shortest", str(out_path),
    ]
    _run(cmd)


def _build_scene_clip(scene: dict, scene_duration: float, project_root: Path, cache_dir: Path,
                       width: int, height: int, fps: int, index: int) -> Path:
    visual = scene["visual"]

    # A real, disclosed photo of a specific named subject (not stock
    # footage), the photo IS the shot for the whole scene, no footage
    # layer needed. See src/graphics/photo_card.py.
    if "photo_path" in visual:
        return project_root / visual["photo_path"]

    segments = visual["segments"]
    raw_total = sum(s["duration"] for s in segments)
    scale = scene_duration / raw_total if raw_total > 0 else 1.0

    # Crossfading N clips shortens the result by (N-1)*XFADE_DURATION versus
    # their raw sum (each dissolve overlaps two clips into one span), left
    # uncompensated, every scene renders a little short and the final
    # -shortest mux silently truncates the tail of the narration. Work out
    # how many crossfade joins this scene will actually have, then inflate
    # the scale so the POST-crossfade length matches scene_duration exactly.
    if "graphic_path" not in visual:
        n_groups = [len(segments)]
    else:
        target = min(GRAPHIC_ONSCREEN_SECONDS, scene_duration)
        cum, split_idx = 0.0, 0
        for j, seg in enumerate(segments):
            cum += seg["duration"] * scale
            split_idx = j + 1
            if cum >= target:
                break
        n_groups = [split_idx, len(segments) - split_idx]
    crossfade_loss = sum(max(0, n - 1) for n in n_groups) * XFADE_DURATION
    if crossfade_loss > 0 and raw_total > 0:
        scale = (scene_duration + crossfade_loss) / raw_total

    seg_paths = []
    for j, seg in enumerate(segments):
        seg_out = cache_dir / f"scene_{index:02d}_seg_{j:02d}.mp4"
        _render_video_segment(project_root / seg["clip_path"], seg["duration"] * scale, width, height, fps, seg_out)
        seg_paths.append(seg_out)

    if "graphic_path" not in visual:
        if len(seg_paths) == 1:
            return seg_paths[0]
        bg_path = cache_dir / f"scene_{index:02d}_bg.mp4"
        _crossfade_concat(seg_paths, bg_path)
        return bg_path

    # The graphic is a short beat (GRAPHIC_ONSCREEN_SECONDS), not the whole
    # scene: overlay it on the leading segments only, then cut back to plain
    # footage for whatever's left of the scene, footage never freezes under
    # a graphic for 40+ seconds.
    split_idx = n_groups[0]
    head_paths, tail_paths = seg_paths[:split_idx], seg_paths[split_idx:]

    if len(head_paths) == 1:
        head_bg = head_paths[0]
    else:
        head_bg = cache_dir / f"scene_{index:02d}_head_bg.mp4"
        _crossfade_concat(head_paths, head_bg)

    head_final = cache_dir / f"scene_{index:02d}_head_final.mp4"
    _overlay_graphic(head_bg, project_root / visual["graphic_path"], width, height, head_final)

    if not tail_paths:
        return head_final

    if len(tail_paths) == 1:
        tail_bg = tail_paths[0]
    else:
        tail_bg = cache_dir / f"scene_{index:02d}_tail_bg.mp4"
        _crossfade_concat(tail_paths, tail_bg)

    # head (graphic already baked in) -> tail: a hard cut is correct here,
    # the graphic's own disappearance is already the transition.
    scene_final = cache_dir / f"scene_{index:02d}_final.mp4"
    _concat([head_final, tail_bg], cache_dir / f"scene_{index:02d}_full_concat.txt", scene_final)
    return scene_final


def assemble(project_root: Path) -> Path:
    cfg = get_config()
    video_cfg = cfg["video"]
    width, height, fps = video_cfg["width"], video_cfg["height"], video_cfg["fps"]

    scenes = json.loads((project_root / "scenes.json").read_text())
    narration_wav = project_root / "audio" / "narration.wav"

    cache_dir = project_root / "cache"
    cache_dir.mkdir(exist_ok=True)

    scene_clips = []
    for i, scene in enumerate(scenes):
        start = 0.0 if i == 0 else scene["start"]
        scene_duration = scene["end"] - start
        log.info("assemble: scene %d/%d (%.1fs)%s", i + 1, len(scenes), scene_duration,
                  " + graphic overlay" if "graphic_path" in scene["visual"] else "")
        scene_clips.append(_build_scene_clip(scene, scene_duration, project_root, cache_dir, width, height, fps, i))

    silent_concat = cache_dir / "video_silent.mp4"
    _concat(scene_clips, cache_dir / "concat_list.txt", silent_concat)

    out_dir = output_dir() / project_root.name
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / "final.mp4"

    captions_cfg = cfg["captions"]
    music_cfg = cfg["music"]

    music_path = None
    if music_cfg["enabled"]:
        resolved = resolve_music(project_root, music_cfg["query"], min_duration=60)
        if resolved:
            music_path, _source = resolved

    filter_parts = []
    video_map = "0:v:0"
    if captions_cfg["enabled"]:
        # MarginL/MarginR deliberately omitted: libass interpreted them
        # against a much smaller internal default resolution than the real
        # 1920x1080 frame, over-constraining width and forcing 3-line wraps
        # even on a 3-word caption. Our 5-word/2.5s caption groups
        # (src/subtitles/srt_gen.py) are already narrow enough without it.
        srt_path = generate_srt(project_root)
        style = (
            f"FontName={captions_cfg['font']},FontSize={captions_cfg['font_size']},"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,"
            f"Alignment=2,MarginV={captions_cfg['margin_v']}"
        )
        filter_parts.append(f"[0:v:0]subtitles={srt_path}:original_size={width}x{height}:force_style='{style}'[vout]")
        video_map = "[vout]"

    extra_inputs: list[str] = []
    audio_map = "1:a:0"
    if music_path:
        extra_inputs = ["-stream_loop", "-1", "-i", str(music_path)]
        bed_db = music_cfg["bed_volume_db"]
        filter_parts.append(f"[2:a]volume={bed_db}dB[music_bed]")
        filter_parts.append(
            "[music_bed][1:a:0]sidechaincompress=threshold=0.05:ratio=8:attack=200:release=1000:makeup=1[music_duck]"
        )
        filter_parts.append("[1:a:0][music_duck]amix=inputs=2:duration=first:normalize=0[aout]")
        audio_map = "[aout]"

    final_cmd = ["ffmpeg", "-y", "-i", str(silent_concat), "-i", str(narration_wav)] + extra_inputs
    if filter_parts:
        final_cmd += ["-filter_complex", ";".join(filter_parts)]
    final_cmd += ["-map", video_map, "-map", audio_map]
    final_cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"] if captions_cfg["enabled"] else ["-c:v", "copy"]
    final_cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", str(final_path)]

    _run(final_cmd)

    log.info("assemble: wrote %s", final_path)
    project.mark_stage_done(project_root, "assembly")
    return final_path

"""Project-level narration stage: script.md -> audio/narration.wav + words.json.

Thin orchestration layer over kokoro_tts.synthesize(), reads voice/speed
from config (with per-project override support later), writes plain files,
marks the project's 'narration' stage done so re-runs can skip it.
"""

import json
from dataclasses import asdict
from pathlib import Path

import soundfile as sf

from src.common import project
from src.common.config import get_config
from src.common.logging_setup import get_logger
from src.common.script import extract_narration_text
from src.tts.kokoro_tts import SAMPLE_RATE, synthesize

log = get_logger(__name__)


def generate_narration(project_root: Path, voice: str | None = None, speed: float | None = None) -> Path:
    cfg = get_config()["tts"]
    voice = voice or cfg["voice"]
    speed = speed if speed is not None else cfg["speed"]

    audio_dir = project_root / "audio"
    audio_dir.mkdir(exist_ok=True)
    wav_path = audio_dir / "narration.wav"
    words_path = audio_dir / "words.json"

    script_text = (project_root / "script.md").read_text()
    narration_text = extract_narration_text(script_text)

    def on_chunk(i, total):
        log.info("narration: chunk %d/%d", i, total)

    result = synthesize(narration_text, voice=voice, speed=speed, on_chunk=on_chunk)

    sf.write(wav_path, result.audio, SAMPLE_RATE)
    words_path.write_text(json.dumps([asdict(w) for w in result.words], indent=2))

    duration = len(result.audio) / SAMPLE_RATE
    log.info("narration done: %.1fs audio, %d words, real_timestamps=%s",
              duration, len(result.words), result.has_real_timestamps)

    project.mark_stage_done(project_root, "narration")
    return wav_path

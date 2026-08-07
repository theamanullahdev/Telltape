"""Thin wrapper around the `kokoro` pip package.

Voice and speed are explicit arguments (never read from global config here) so
callers (API, CLI, future runtime overrides) fully control per-call behavior.
"""
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from src.common.logging_setup import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 24000

# Kokoro voice ids are prefixed a/b (American/British) + f/m (female/male).
# lang_code passed to KPipeline must match the voice prefix's language.
_LANG_CODE_BY_PREFIX = {"a": "a", "b": "b"}

_pipeline_cache: dict[str, object] = {}

# We split large inputs into our own sentence-bounded chunks before ever handing
# text to kokoro, rather than trusting a single call with an unbounded amount of
# text: it caps how much work one kokoro call has to do (kokoro/misaki also do
# their own internal splitting, but that's a black box we don't control), it
# lets one chunk fail and retry without redoing the whole part, and it gives us
# a natural point to report progress on long scripts instead of going silent
# for however long the whole part takes.
MAX_CHARS_PER_CHUNK = 500
CHUNK_RETRY_ATTEMPTS = 2

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

ChunkProgressCB = Callable[[int, int], None] | None


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


@dataclass
class TTSResult:
    audio: np.ndarray
    sample_rate: int
    words: list[WordTiming]
    has_real_timestamps: bool


def _get_pipeline(voice: str):
    lang_code = _LANG_CODE_BY_PREFIX.get(voice[0], "a")
    if lang_code not in _pipeline_cache:
        from kokoro import KPipeline

        _pipeline_cache[lang_code] = KPipeline(lang_code=lang_code)
    return _pipeline_cache[lang_code]


def _split_into_chunks(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return [text] if text.strip() else []

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _estimate_word_timings(text: str, duration: float) -> list[WordTiming]:
    words = text.split()
    if not words:
        return []
    weights = [len(w) + 1 for w in words]
    total = sum(weights)
    t = 0.0
    out = []
    for w, wt in zip(words, weights):
        span = duration * (wt / total)
        out.append(WordTiming(word=w, start=t, end=t + span))
        t += span
    return out


def _synthesize_chunk(pipeline, text: str, voice: str, speed: float) -> tuple[np.ndarray, list[WordTiming], bool]:
    audio_chunks: list[np.ndarray] = []
    words: list[WordTiming] = []
    has_real_timestamps = False
    t_offset = 0.0

    for chunk in pipeline(text, voice=voice, speed=speed):
        chunk_text, _phonemes, audio = chunk.graphemes, chunk.phonemes, chunk.audio
        audio_np = np.asarray(audio, dtype=np.float32)
        chunk_duration = len(audio_np) / SAMPLE_RATE

        tokens = getattr(chunk, "tokens", None)
        if tokens and all(getattr(tok, "start_ts", None) is not None for tok in tokens):
            has_real_timestamps = True
            for tok in tokens:
                words.append(WordTiming(
                    word=tok.text,
                    start=t_offset + tok.start_ts,
                    end=t_offset + tok.end_ts,
                ))
        else:
            words.extend(
                WordTiming(w.word, w.start + t_offset, w.end + t_offset)
                for w in _estimate_word_timings(chunk_text, chunk_duration)
            )

        audio_chunks.append(audio_np)
        t_offset += chunk_duration

    audio = np.concatenate(audio_chunks) if audio_chunks else np.zeros(0, dtype=np.float32)
    return audio, words, has_real_timestamps


def synthesize(text: str, voice: str, speed: float = 1.0, on_chunk: ChunkProgressCB = None) -> TTSResult:
    pipeline = _get_pipeline(voice)
    text_chunks = _split_into_chunks(text)
    total = len(text_chunks)

    all_audio: list[np.ndarray] = []
    all_words: list[WordTiming] = []
    has_real_timestamps = False
    t_offset = 0.0

    for i, chunk_text in enumerate(text_chunks, start=1):
        last_error: Exception | None = None
        for attempt in range(1, CHUNK_RETRY_ATTEMPTS + 1):
            try:
                audio, words, chunk_has_ts = _synthesize_chunk(pipeline, chunk_text, voice, speed)
                break
            except Exception as e:  # noqa: BLE001 - retry once, then surface it
                last_error = e
                log.warning("TTS chunk %d/%d attempt %d failed: %s", i, total, attempt, e)
                time.sleep(0.5)
        else:
            raise RuntimeError(f"TTS failed for chunk {i}/{total} after {CHUNK_RETRY_ATTEMPTS} attempts") from last_error

        has_real_timestamps = has_real_timestamps or chunk_has_ts
        all_audio.append(audio)
        all_words.extend(WordTiming(w.word, w.start + t_offset, w.end + t_offset) for w in words)
        t_offset += len(audio) / SAMPLE_RATE

        if on_chunk:
            on_chunk(i, total)

    full_audio = np.concatenate(all_audio) if all_audio else np.zeros(0, dtype=np.float32)
    return TTSResult(
        audio=full_audio,
        sample_rate=SAMPLE_RATE,
        words=all_words,
        has_real_timestamps=has_real_timestamps,
    )

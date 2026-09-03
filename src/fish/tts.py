from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from fishaudio.exceptions import (
    APIError,
    AuthenticationError,
    FishAudioError,
    NotFoundError,
    RateLimitError,
)
from fishaudio.types import Prosody, TTSConfig

from src.fish.client import create_client
from src.config import get_config

logger = logging.getLogger(__name__)

_SEGMENT_MAX_CHARS = 150


class TTSFailure(Exception):
    """Raised when Fish Audio synthesis fails."""


def _build_config(speed: float, volume_db: int) -> TTSConfig:
    return TTSConfig(
        format="mp3",
        latency="balanced",
        mp3_bitrate=64,
        chunk_length=100,
        prosody=Prosody(speed=speed, volume=float(volume_db)),
    )


def _translate_error(exc: FishAudioError) -> TTSFailure:
    if isinstance(exc, AuthenticationError):
        return TTSFailure("Fish Audio API key is invalid or missing.")
    if isinstance(exc, RateLimitError):
        return TTSFailure("Fish Audio rate limit exceeded. Try again later.")
    if isinstance(exc, NotFoundError):
        return TTSFailure("Voice not found on Fish Audio. It may have been removed.")
    if isinstance(exc, APIError):
        return TTSFailure(f"Fish Audio API error {exc.status}: {exc.message}")
    return TTSFailure(f"Fish Audio error: {exc}")


async def synthesize(
    text: str,
    reference_id: str,
    speed: float = 1.0,
    volume_db: int = 0,
    model: str | None = None,
) -> bytes:
    config = get_config()
    model = model or config.tts_model
    try:
        client = create_client()
        return await client.tts.convert(
            text=text,
            reference_id=reference_id,
            config=_build_config(speed, volume_db),
            model=model,
        )
    except FishAudioError as e:
        raise _translate_error(e) from e


def _split_segments(text: str, max_chars: int = _SEGMENT_MAX_CHARS) -> list[str]:
    segments: list[str] = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= max_chars:
            segments.append(remaining)
            break
        cut = _segment_cut(remaining, max_chars)
        segments.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    return [s for s in segments if s.strip()]


def _segment_cut(text: str, limit: int) -> int:
    for i in range(limit, 0, -1):
        if text[i - 1] in ".!?;:\n, ":
            return i
    return limit


async def synthesize_stream(
    text: str,
    reference_id: str,
    speed: float = 1.0,
    volume_db: int = 0,
    model: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream audio for ``text`` as a sequence of short synthesis requests.

    Long text is split into small segments so the first audio arrives after a
    few seconds instead of waiting for the whole text to be generated, and a
    failed segment is skipped instead of truncating the message.
    """
    config = get_config()
    model = model or config.tts_model
    segments = _split_segments(text)
    yielded = False
    last_error: TTSFailure | None = None
    for segment in segments:
        try:
            async for chunk in _stream_segment(
                segment, reference_id, speed, volume_db, model
            ):
                yielded = True
                yield chunk
        except TTSFailure as e:
            last_error = e
            logger.warning("Skipping failed speech segment: %s", e)
    if not yielded and last_error is not None:
        raise last_error


async def _stream_segment(
    text: str,
    reference_id: str,
    speed: float,
    volume_db: int,
    model: str,
) -> AsyncIterator[bytes]:
    try:
        client = create_client()
        stream = await client.tts.stream(
            text=text,
            reference_id=reference_id,
            config=_build_config(speed, volume_db),
            model=model,
        )
        async for chunk in stream:
            yield chunk
    except FishAudioError as e:
        raise _translate_error(e) from e

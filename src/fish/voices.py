from __future__ import annotations

import re
from dataclasses import dataclass

from fishaudio.exceptions import FishAudioError, NotFoundError

from src.fish.client import create_client

VOICE_URL_PATTERNS = [
    re.compile(r"fish\.audio/(?:[a-z]{2}/)?voice-library/([a-f0-9]{32})", re.IGNORECASE),
    re.compile(r"fish\.audio/(?:[a-z]{2}/)?app/(?:my-voices|personal-voices|voice-library)/([a-f0-9]{32})", re.IGNORECASE),
    re.compile(r"fish\.audio/(?:[a-z]{2}/)?voices?/([a-f0-9]{32})", re.IGNORECASE),
    re.compile(r"fish\.audio/m/([a-f0-9]{32})", re.IGNORECASE),
]
UUID_PATTERN = re.compile(r"^[a-f0-9]{32}$", re.IGNORECASE)


@dataclass(frozen=True)
class VoiceInfo:
    id: str
    title: str
    cover_image: str | None = None
    languages: list[str] | None = None
    visibility: str | None = None
    state: str | None = None
    task_count: int | None = None


def extract_voice_id(value: str) -> str | None:
    stripped = value.strip()
    if UUID_PATTERN.match(stripped):
        return stripped.lower()
    for pattern in VOICE_URL_PATTERNS:
        match = pattern.search(stripped)
        if match:
            return match.group(1)
    return None


async def resolve_voice(value: str) -> VoiceInfo | None:
    voice_id = extract_voice_id(value)
    if voice_id is None:
        return None
    try:
        client = create_client()
        voice = await client.voices.get(voice_id)
    except NotFoundError:
        return None
    except FishAudioError:
        return None
    return VoiceInfo(
        id=voice.id,
        title=voice.title,
        cover_image=voice.cover_image,
        languages=voice.languages,
        visibility=voice.visibility,
        state=voice.state,
    )


async def search_public_voices(
    query: str,
    limit: int = 15,
    title_language: list[str] | None = None,
) -> list[VoiceInfo]:
    """Search the public voice library by title, ordered by popularity."""
    return await _list_public_voices(limit=limit, title=query, title_language=title_language)


async def list_public_voices(
    limit: int = 15,
    *,
    tags: list[str] | None = None,
    language: str | None = None,
    title_language: list[str] | None = None,
) -> list[VoiceInfo]:
    """List the most popular public voices matching the given tags/language."""
    return await _list_public_voices(
        limit=limit, tags=tags, language=language, title_language=title_language
    )


async def _list_public_voices(
    limit: int = 15,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
    language: str | None = None,
    title_language: list[str] | None = None,
) -> list[VoiceInfo]:
    """Query the public voice library, ordered by popularity (top models first).

    The API sorts by ``task_count`` (number of synthesis uses); a local
    stable tiebreak on title keeps the ordering deterministic.
    """
    client = create_client()
    try:
        page = await client.voices.list(
            title=title,
            tags=tags,
            language=language,
            title_language=title_language,
            self_only=False,
            page_size=limit,
            sort_by="task_count",
        )
    except FishAudioError:
        return []
    voices = sorted(page.items, key=lambda v: (-v.task_count, v.title.lower()))
    return [
        VoiceInfo(
            id=item.id,
            title=item.title,
            cover_image=item.cover_image,
            languages=item.languages,
            visibility=item.visibility,
            state=item.state,
            task_count=item.task_count,
        )
        for item in voices
    ]

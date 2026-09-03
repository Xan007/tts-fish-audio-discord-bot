from __future__ import annotations

import discord

from src.i18n import t
from src.speech.pipeline import SpeakResult, pipeline

from collections.abc import Callable, Coroutine
from typing import Any

# Tracks the last speaker user_id per guild_id
_last_speaker: dict[int, int] = {}


def format_text_for_speaker(
    guild_id: int, user_id: int, author_name: str, text: str, language: str = "en"
) -> str:
    """Prepends 'User says:' only when speaker changes in the guild."""
    last_id = _last_speaker.get(guild_id)
    _last_speaker[guild_id] = user_id
    if last_id != user_id:
        return t(language, "author_says", name=author_name, text=text)
    return text


def reset_speaker_for_guild(guild_id: int) -> None:
    _last_speaker.pop(guild_id, None)


async def speak_for_member(
    member: discord.Member,
    text: str,
    language: str = "en",
    include_prefix: bool = False,
    on_play_start: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_play_end: Callable[[], Coroutine[Any, Any, None]] | None = None,
) -> SpeakResult:
    voice_state = member.voice
    if voice_state is None or voice_state.channel is None:
        return SpeakResult(False, t(language, "p_need_vc"))
    if include_prefix:
        text = format_text_for_speaker(
            member.guild.id, member.id, member.display_name, text, language=language
        )
    return await pipeline.submit(
        member.guild.id,
        voice_state.channel,
        member.id,
        text,
        language=language,
        on_play_start=on_play_start,
        on_play_end=on_play_end,
    )


async def speak_in_channel(
    guild: discord.Guild,
    channel: discord.VoiceChannel,
    user_id: int,
    author_name: str,
    text: str,
    language: str = "en",
    on_play_start: Callable[[], Coroutine[Any, Any, None]] | None = None,
    on_play_end: Callable[[], Coroutine[Any, Any, None]] | None = None,
) -> SpeakResult:
    text = format_text_for_speaker(
        guild.id, user_id, author_name, text, language=language
    )
    return await pipeline.submit(
        guild.id,
        channel,
        user_id,
        text,
        language=language,
        on_play_start=on_play_start,
        on_play_end=on_play_end,
    )

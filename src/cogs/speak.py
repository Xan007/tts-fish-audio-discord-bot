from __future__ import annotations

import discord

from src.i18n import t
from src.speech.pipeline import SpeakResult, pipeline


async def speak_for_member(
    member: discord.Member,
    text: str,
    language: str = "en",
) -> SpeakResult:
    voice_state = member.voice
    if voice_state is None or voice_state.channel is None:
        return SpeakResult(False, t(language, "p_need_vc"))
    return await pipeline.submit(
        member.guild.id, voice_state.channel, member.id, text, language=language
    )


async def speak_in_channel(
    guild: discord.Guild,
    channel: discord.VoiceChannel,
    user_id: int,
    text: str,
    language: str = "en",
) -> SpeakResult:
    return await pipeline.submit(guild.id, channel, user_id, text, language=language)

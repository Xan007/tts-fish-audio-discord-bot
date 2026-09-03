from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from src.audio.playback import playback
from src.cogs.speak import speak_in_channel
from src.db import get_session
from src.i18n import get_language_for_user, t
from src.speech.filters import clean_for_tts
from src.store import channels

logger = logging.getLogger(__name__)


class AutojoinCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    autojoin = app_commands.Group(
        name="autojoin",
        description=locale_str(
            "Manage autojoin for voice channels.",
            **{"es-ES": "Gestiona el autojoin de los canales de voz."},
        ),
    )

    @autojoin.command(
        name="enable",
        description=locale_str(
            "Enable autojoin for your current voice channel.",
            **{"es-ES": "Activa el autojoin para tu canal de voz actual."},
        ),
    )
    async def autojoin_enable(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        if not isinstance(member, discord.Member) or member.voice is None:
            await interaction.response.send_message(
                t(language, "aj_need_vc_enable"), ephemeral=True
            )
            return
        if interaction.guild_id is None:
            return
        voice_channel = member.voice.channel
        text_channel = interaction.channel
        if isinstance(text_channel, discord.VoiceChannel):
            if text_channel.id != voice_channel.id:
                await interaction.response.send_message(
                    t(language, "aj_need_same_vc"),
                    ephemeral=True,
                )
                return
            async with get_session() as session:
                await channels.set_autojoin(
                    session, interaction.guild_id, voice_channel.id, 0, enabled=True
                )
            await self._refresh_stay(interaction.guild_id)
            await interaction.response.send_message(
                t(language, "aj_enabled"), ephemeral=True
            )
            return
        if text_channel is not None:
            async with get_session() as session:
                await channels.set_autojoin(
                    session, interaction.guild_id, voice_channel.id, text_channel.id, enabled=True
                )
            await self._refresh_stay(interaction.guild_id)
            await interaction.response.send_message(
                t(language, "aj_enabled"), ephemeral=True
            )

    @autojoin.command(
        name="disable",
        description=locale_str(
            "Disable autojoin for your voice channel.",
            **{"es-ES": "Desactiva el autojoin para tu canal de voz."},
        ),
    )
    async def autojoin_disable(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        if not isinstance(member, discord.Member) or member.voice is None or interaction.guild_id is None:
            await interaction.response.send_message(
                t(language, "aj_need_vc_disable"), ephemeral=True
            )
            return
        async with get_session() as session:
            await channels.disable_autojoin(session, interaction.guild_id, member.voice.channel.id)
        await self._refresh_stay(interaction.guild_id)
        await interaction.response.send_message(
            t(language, "aj_disabled"), ephemeral=True
        )

    async def _refresh_stay(self, guild_id: int) -> None:
        async with get_session() as session:
            rows = await channels.get_enabled_autojoin_for_guild(session, guild_id)
        playback.set_stay(guild_id, len(rows) > 0)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        if self.bot.user in message.mentions:
            return
        async with get_session() as session:
            if isinstance(message.channel, discord.VoiceChannel):
                rows = await channels.get_autojoin_for_voice_channel(
                    session, message.guild.id, message.channel.id
                )
            elif isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                rows = await channels.get_autojoin_for_text_channel(
                    session, message.guild.id, message.channel.id
                )
            else:
                return
            if not rows:
                return
            language = await get_language_for_user(session, message.author.id, member=message.author)

        text = await clean_for_tts(message, language)
        if not text:
            return
        for row in rows:
            if row.text_channel_id == 0 or row.text_channel_id == message.channel.id:
                voice_channel = message.guild.get_channel(row.voice_channel_id)
                if isinstance(voice_channel, discord.VoiceChannel):
                    result = await speak_in_channel(
                        message.guild,
                        voice_channel,
                        message.author.id,
                        message.author.display_name,
                        text,
                        language=language,
                    )
                    if result.ok and len(text) >= 150:
                        from src.cogs.tts import CancelTTSView
                        view = CancelTTSView(message.author.id, message.guild.id, language)
                        try:
                            view.message = await message.reply(
                                view=view,
                                mention_author=False,
                            )
                        except discord.HTTPException:
                            pass
                break

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.id != self.bot.user.id:
            return
        if before.channel is not None and after.channel is None:
            playback.cleanup(member.guild.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutojoinCommands(bot))

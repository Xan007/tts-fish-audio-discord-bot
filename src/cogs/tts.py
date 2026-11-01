from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from src.audio.playback import playback
from src.cogs.speak import speak_for_member
from src.i18n import get_language_for_user, t
from src.speech.filters import clean_text_for_tts
from src.speech.pipeline import pipeline

logger = logging.getLogger(__name__)

class TTSCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="join",
        description=locale_str(
            "Join the voice channel you are currently in.",
            **{"es-ES": "Entra al canal de voz en el que estás."},
        ),
    )
    async def join(self, interaction: discord.Interaction) -> None:
        language = await get_language_for_user(
            None, interaction.user.id, interaction=interaction
        )
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                t(language, "tts_server_only"), ephemeral=True
            )
            return

        voice_state = member.voice
        if voice_state is None or voice_state.channel is None:
            await interaction.response.send_message(
                t(language, "join_need_vc"), ephemeral=True
            )
            return

        channel = voice_state.channel
        bot_member = interaction.guild.me
        if bot_member is None or not channel.permissions_for(bot_member).connect:
            await interaction.response.send_message(
                t(language, "join_no_permission", channel=channel.mention),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await playback.ensure_connected(interaction.guild, channel)
        except Exception:
            logger.exception(
                "Failed to join voice channel %s in guild %s",
                channel.id,
                interaction.guild.id,
            )
            await interaction.followup.send(
                t(language, "join_failed", channel=channel.mention), ephemeral=True
            )
            return

        await interaction.followup.send(
            t(language, "join_success", channel=channel.mention), ephemeral=True
        )

    @app_commands.command(
        name="tts",
        description=locale_str(
            "Speak the given text with your configured voice in your voice channel.",
            **{"es-ES": "Dice el texto indicado con tu voz configurada en tu canal de voz."},
        ),
    )
    @app_commands.describe(text="Text to speak aloud")
    async def tts(self, interaction: discord.Interaction, text: str) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member):
            language = await get_language_for_user(None, interaction.user.id)
            await interaction.response.send_message(
                t(language, "tts_server_only"), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        language = await get_language_for_user(None, member.id, interaction=interaction)
        cleaned = await clean_text_for_tts(text, interaction, language=language)
        if not cleaned.strip():
            await interaction.followup.send(
                t(language, "tts_empty"), ephemeral=True
            )
            return

        result = await speak_for_member(member, cleaned, language=language)
        await interaction.followup.send(result.message, ephemeral=True)

    @app_commands.command(
        name="stop",
        description=locale_str(
            "Stop the current speech playback and clear the guild queue.",
            **{"es-ES": "Detiene la reproducción actual y vacía la cola de voz."},
        ),
    )
    async def stop(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        pipeline.stop(interaction.guild_id)
        await interaction.response.send_message(t(language, "stop_success"), ephemeral=True)

    @app_commands.command(
        name="skip",
        description=locale_str(
            "Skip the current speech audio.",
            **{"es-ES": "Salta el audio de voz actual."},
        ),
    )
    async def skip(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        pipeline.skip(interaction.guild_id)
        await interaction.response.send_message(t(language, "skip_success"), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TTSCommands(bot))

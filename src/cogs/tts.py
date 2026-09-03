from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from src.cogs.speak import speak_for_member
from src.i18n import get_language_for_user, t
from src.speech.filters import clean_text_for_tts

logger = logging.getLogger(__name__)


class TTSCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

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

        await interaction.response.defer(ephemeral=False)
        language = await get_language_for_user(None, member.id, interaction=interaction)
        cleaned = await clean_text_for_tts(text, interaction, language=language)
        if not cleaned.strip():
            await interaction.followup.send(
                t(language, "tts_empty"), ephemeral=True
            )
            return
        result = await speak_for_member(member, cleaned, language=language)
        if result.ok:
            await interaction.followup.send(result.message)
        else:
            await interaction.followup.send(result.message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TTSCommands(bot))

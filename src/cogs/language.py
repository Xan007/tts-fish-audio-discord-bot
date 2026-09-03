from __future__ import annotations

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from src.config import get_config
from src.db import get_session
from src.i18n import SUPPORTED_LANGUAGES, language_from_locale, language_label, t
from src.store import users


class LanguageCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="language",
        description=locale_str(
            "Set the language the bot replies to you in.",
            **{"es-ES": "Configura el idioma en el que el bot te responde."},
        ),
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="Auto", value="auto"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Español", value="es"),
        ]
    )
    @app_commands.describe(
        language="auto = use your Discord language, English, or Español"
    )
    async def language_set(
        self, interaction: discord.Interaction, language: app_commands.Choice[str]
    ) -> None:
        async with get_session() as session:
            await users.set_user_language(
                session, interaction.user.id, language.value, get_config().default_voice_id
            )
        if language.value in SUPPORTED_LANGUAGES:
            lang = language.value
        else:
            lang = language_from_locale(str(interaction.locale))
        await interaction.response.send_message(
            t(lang, "lang_done", language=language_label(lang, language.value)),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LanguageCommands(bot))

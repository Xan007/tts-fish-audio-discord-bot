from __future__ import annotations

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from src.i18n import get_language_for_user, t
from src.ui.catalog import ACCENT_COLOR
from src.ui.quick_help import QuickHelpView


def help_embed(language: str) -> discord.Embed:
    embed = discord.Embed(
        title=t(language, "help_title"),
        description=t(language, "help_desc"),
        color=ACCENT_COLOR,
    )
    embed.add_field(name=t(language, "help_catalog"), value=t(language, "help_catalog_value"), inline=False)
    embed.add_field(name=t(language, "help_search"), value=t(language, "help_search_value"), inline=False)
    embed.add_field(name=t(language, "help_join"), value=t(language, "help_join_value"), inline=False)
    embed.add_field(name=t(language, "help_speak"), value=t(language, "help_speak_value"), inline=False)
    embed.add_field(name=t(language, "help_autojoin"), value=t(language, "help_autojoin_value"), inline=False)
    embed.add_field(name=t(language, "help_language"), value=t(language, "help_language_value"), inline=False)
    embed.set_footer(text=t(language, "help_footer"))
    return embed


class HelpCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.type is not discord.MessageType.default:
            return
        if self.bot.user not in message.mentions:
            return
        language = await get_language_for_user(None, message.author.id, member=message.author)
        view = QuickHelpView(message.author.id, language)
        view.message = await message.reply(embed=help_embed(language), view=view)

    @app_commands.command(
        name="help",
        description=locale_str(
            "Show the essential commands.",
            **{"es-ES": "Muestra los comandos esenciales."},
        ),
    )
    async def help_command(self, interaction: discord.Interaction) -> None:
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        view = QuickHelpView(interaction.user.id, language)
        view.message = await interaction.response.send_message(
            embed=help_embed(language), view=view
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCommands(bot))

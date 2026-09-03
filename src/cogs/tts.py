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
from src.ui.catalog import ACCENT_COLOR

logger = logging.getLogger(__name__)

LONG_MESSAGE_THRESHOLD = 150


# Tracks the currently active CancelTTSView per guild_id
_active_cancel_views: dict[int, CancelTTSView] = {}


class CancelTTSView(discord.ui.View):
    """Subtle view with a Cancel button that auto-deletes when finished or replaced."""

    def __init__(self, author_id: int, guild_id: int, language: str) -> None:
        super().__init__(timeout=90)
        self.author_id = author_id
        self.guild_id = guild_id
        self.language = language
        self.message: discord.Message | None = None
        self.cancel_button = discord.ui.Button(
            label=t(language, "cancel_btn"),
            style=discord.ButtonStyle.secondary,
        )
        self.cancel_button.callback = self.on_cancel
        self.add_item(self.cancel_button)

    async def register(self, message: discord.Message) -> None:
        """Register this view as the active cancel view for the guild, removing any previous one."""
        self.message = message
        old_view = _active_cancel_views.get(self.guild_id)
        if old_view is not None and old_view is not self:
            await old_view.dismiss()
        _active_cancel_views[self.guild_id] = self

    async def dismiss(self) -> None:
        """Silently dismiss and delete this cancel button."""
        self.stop()
        if _active_cancel_views.get(self.guild_id) is self:
            _active_cancel_views.pop(self.guild_id, None)
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass

    async def on_timeout(self) -> None:
        """Silently remove the cancel button when timeout occurs."""
        await self.dismiss()

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        is_author = interaction.user.id == self.author_id
        is_admin = (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        )
        if not (is_author or is_admin):
            await interaction.response.send_message(
                t(self.language, "cancel_perm_error"), ephemeral=True
            )
            return

        pipeline.skip(self.guild_id)
        await self.dismiss()
        await interaction.response.send_message(
            t(self.language, "cancelled_by", user=interaction.user.display_name),
            ephemeral=True,
        )


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

        if len(cleaned) >= LONG_MESSAGE_THRESHOLD and interaction.guild_id:
            view = CancelTTSView(interaction.user.id, interaction.guild_id, language)

            async def on_start() -> None:
                try:
                    msg = await interaction.channel.send(
                        f"> *{cleaned[:150]}...*",
                        view=view,
                    )
                    await view.register(msg)
                except Exception:
                    pass

            async def on_end() -> None:
                await view.dismiss()

            result = await speak_for_member(
                member,
                cleaned,
                language=language,
                on_play_start=on_start,
                on_play_end=on_end,
            )
            if not result.ok:
                await interaction.followup.send(result.message, ephemeral=True)
            else:
                await interaction.followup.send(result.message)
        else:
            result = await speak_for_member(member, cleaned, language=language)
            if result.ok:
                await interaction.followup.send(result.message)
            else:
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
        await interaction.response.send_message(t(language, "stop_success"), ephemeral=False)

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
        await interaction.response.send_message(t(language, "skip_success"), ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TTSCommands(bot))

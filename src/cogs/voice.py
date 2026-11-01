from __future__ import annotations

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from src.audio.playback import playback
from src.config import get_config
from src.db import get_session
from src.fish.tts import TTSFailure, synthesize
from src.fish.voices import extract_voice_id, resolve_voice, search_public_voices
from src.i18n import get_language_for_user, t, voice_language_filter
from src.store import users
from src.ui.catalog import CatalogView
from src.ui.voice_picker import VoicePickerView

PREVIEW_TEXT = "Hello, this is a voice preview."


async def voice_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    query = current.strip()
    if len(query) < 2:
        return []
    found_id = extract_voice_id(query)
    if found_id is not None:
        return [app_commands.Choice(name=query[:100], value=found_id)]
    language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
    results = await search_public_voices(
        query, limit=25, title_language=voice_language_filter(language)
    )
    choices: list[app_commands.Choice[str]] = []
    for voice in results:
        label = voice.title[:70]
        if voice.languages:
            label += f" ({', '.join(voice.languages[:2])})"
        if voice.task_count:
            label += f" · {voice.task_count:,} uses"
        choices.append(app_commands.Choice(name=label[:100], value=voice.id))
    return choices


class VoiceCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    voice = app_commands.Group(
        name="voice",
        description=locale_str(
            "Manage your personal TTS voice.",
            **{"es-ES": "Gestiona tu voz personal de TTS."},
        ),
    )

    @app_commands.command(
        name="voices",
        description=locale_str(
            "Browse the voice library by category and pick one.",
            **{"es-ES": "Explora la biblioteca de voces por categoría y elige una."},
        ),
    )
    async def voices_catalog(self, interaction: discord.Interaction) -> None:
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        view = CatalogView(interaction.user.id, language)
        view.message = await interaction.response.send_message(
            embed=view.categories_embed(), view=view, ephemeral=True
        )

    @voice.command(
        name="search",
        description=locale_str(
            "Search the Fish Audio voice library and pick one with a button.",
            **{"es-ES": "Busca en la biblioteca de voces de Fish Audio y elige una con un botón."},
        ),
    )
    @app_commands.describe(query="Search terms for a voice name")
    async def voice_search(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True)
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        results = await search_public_voices(
            query, limit=50, title_language=voice_language_filter(language)
        )
        if not results:
            await interaction.followup.send(
                t(language, "no_results"), ephemeral=True
            )
            return
        view = VoicePickerView(interaction.user.id, results, query, language)
        view.message = await interaction.followup.send(
            embed=view.embed(), view=view, ephemeral=True
        )

    @voice.command(
        name="set",
        description=locale_str(
            "Set your personal TTS voice from a voice id or fish.audio URL.",
            **{"es-ES": "Configura tu voz personal de TTS con un ID o un enlace de fish.audio."},
        ),
    )
    @app_commands.describe(ref="Voice id (32 hex chars) or a fish.audio voice URL")
    @app_commands.autocomplete(ref=voice_autocomplete)
    async def voice_set(self, interaction: discord.Interaction, ref: str) -> None:
        await interaction.response.defer(ephemeral=True)
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        voice = await resolve_voice(ref)
        if voice is None:
            await interaction.followup.send(
                t(language, "v_not_found"), ephemeral=True
            )
            return
        async with get_session() as session:
            await users.set_user_voice(
                session, interaction.user.id, voice.id, voice_title=voice.title
            )
        await interaction.followup.send(
            t(language, "v_set", title=voice.title), ephemeral=True
        )

    @voice.command(
        name="set_for",
        description=locale_str(
            "Set another user's TTS voice (requires Administrator).",
            **{"es-ES": "Configura la voz TTS de otro usuario (requiere Administrador)."},
        ),
    )
    @app_commands.describe(
        user="The user whose voice to set",
        ref="Voice id (32 hex chars) or a fish.audio voice URL",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(ref=voice_autocomplete)
    async def voice_set_for(
        self, interaction: discord.Interaction, user: discord.Member, ref: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        voice = await resolve_voice(ref)
        if voice is None:
            await interaction.followup.send(
                t(language, "v_not_found"), ephemeral=True
            )
            return
        async with get_session() as session:
            await users.set_user_voice(
                session, user.id, voice.id, voice_title=voice.title
            )
        await interaction.followup.send(
            t(language, "v_set_for", title=voice.title, user=user.display_name),
            ephemeral=True,
        )

    @voice.command(
        name="info",
        description=locale_str(
            "Show your current voice and settings.",
            **{"es-ES": "Muestra tu voz actual y su configuración."},
        ),
    )
    async def voice_info(self, interaction: discord.Interaction) -> None:
        config = get_config()
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        async with get_session() as session:
            user_voice = await users.get_user_voice(session, interaction.user.id)
        if user_voice is None:
            await interaction.response.send_message(
                t(
                    language, "v_info_default",
                    id=config.default_voice_id, speed=users.DEFAULT_SPEED, volume=users.DEFAULT_VOLUME_DB,
                ),
                ephemeral=True,
            )
            return
        title = user_voice.voice_title or "Unknown"
        await interaction.response.send_message(
            t(
                language, "v_info",
                title=title, id=user_voice.voice_id,
                speed=user_voice.speed, volume=user_voice.volume_db,
            ),
            ephemeral=True,
        )

    @voice.command(
        name="reset",
        description=locale_str(
            "Reset your voice to the bot default.",
            **{"es-ES": "Restablece tu voz a la predeterminada del bot."},
        ),
    )
    async def voice_reset(self, interaction: discord.Interaction) -> None:
        config = get_config()
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        async with get_session() as session:
            await users.reset_user_voice(session, interaction.user.id, config.default_voice_id)
        await interaction.response.send_message(
            t(language, "v_reset"), ephemeral=True
        )

    @voice.command(
        name="preview",
        description=locale_str(
            "Play a short sample with a voice (or your current one).",
            **{"es-ES": "Reproduce una muestra breve con una voz (o con la tuya)."},
        ),
    )
    @app_commands.describe(ref="Voice id or fish.audio URL (optional)")
    @app_commands.autocomplete(ref=voice_autocomplete)
    async def voice_preview(self, interaction: discord.Interaction, ref: str | None = None) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member):
            language = await get_language_for_user(None, interaction.user.id)
            await interaction.response.send_message(
                t(language, "v_need_vc"), ephemeral=True
            )
            return
        language = await get_language_for_user(None, member.id, interaction=interaction)
        if member.voice is None or member.voice.channel is None:
            await interaction.response.send_message(
                t(language, "v_need_vc"), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        if ref:
            voice = await resolve_voice(ref)
            if voice is None:
                await interaction.followup.send(
                    t(language, "v_not_found"), ephemeral=True
                )
                return
            audio = await self._synthesize_for_preview(PREVIEW_TEXT, voice.id)
        else:
            async with get_session() as session:
                user_voice = await users.get_user_voice(session, member.id)
            voice_id, speed, volume_db = (
                user_voice.voice_id,
                user_voice.speed,
                user_voice.volume_db,
            ) if user_voice else (
                get_config().default_voice_id,
                users.DEFAULT_SPEED,
                users.DEFAULT_VOLUME_DB,
            )
            audio = await self._synthesize_for_preview(
                PREVIEW_TEXT, voice_id, speed=speed, volume_db=volume_db
            )
        if audio is None:
            await interaction.followup.send(
                t(language, "v_preview_fail"), ephemeral=True
            )
            return
        try:
            voice_client = await playback.ensure_connected(member.guild, member.voice.channel)
        except Exception:
            await interaction.followup.send(
                t(language, "v_join_fail"), ephemeral=True
            )
            return
        await playback.enqueue(voice_client, audio)
        await interaction.followup.send(t(language, "v_playing_preview"), ephemeral=True)

    @staticmethod
    async def _synthesize_for_preview(
        text: str, voice_id: str, speed: float = 1.0, volume_db: int = 0
    ) -> bytes | None:
        try:
            return await synthesize(text, voice_id, speed=speed, volume_db=volume_db)
        except TTSFailure:
            return None

    @voice.command(
        name="speed",
        description=locale_str(
            "Set your speech speed (0.5 to 2.0).",
            **{"es-ES": "Configura tu velocidad de voz (0.5 a 2.0)."},
        ),
    )
    @app_commands.describe(speed="Speed multiplier between 0.5 and 2.0")
    async def voice_speed(
        self, interaction: discord.Interaction, speed: app_commands.Range[float, 0.5, 2.0]
    ) -> None:
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        async with get_session() as session:
            await users.update_speed(session, interaction.user.id, speed, get_config().default_voice_id)
        await interaction.response.send_message(
            t(language, "v_speed_set", speed=speed), ephemeral=True
        )

    @voice.command(
        name="volume",
        description=locale_str(
            "Set your volume in dB (-20 to 20).",
            **{"es-ES": "Configura tu volumen en dB (-20 a 20)."},
        ),
    )
    @app_commands.describe(volume="Volume adjustment in decibels")
    async def voice_volume(
        self, interaction: discord.Interaction, volume: app_commands.Range[int, -20, 20]
    ) -> None:
        language = await get_language_for_user(None, interaction.user.id, interaction=interaction)
        async with get_session() as session:
            await users.update_volume(session, interaction.user.id, volume, get_config().default_voice_id)
        await interaction.response.send_message(
            t(language, "v_volume_set", volume=volume), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceCommands(bot))

from __future__ import annotations

from dataclasses import dataclass

import discord

from src.audio.playback import playback
from src.db import get_session
from src.fish.tts import TTSFailure, synthesize
from src.fish.voices import VoiceInfo, list_public_voices
from src.i18n import t, voice_language_filter
from src.store import users
from src.ui.formatting import format_voice_lines, page_footer

PAGE_SIZE = 10
NAV_ROW = 3

ACCENT_COLOR = 0x5865F2
SUCCESS_COLOR = 0x57F287

CATALOG_PREVIEW_TEXT = "Hello, this is a voice preview."


@dataclass(frozen=True)
class CatalogCategory:
    key: str
    label: str
    emoji: str
    tags: tuple[str, ...] = ()
    language: str | None = None


CATALOG_CATEGORIES: tuple[CatalogCategory, ...] = (
    CatalogCategory("anime", "Anime", "\U0001f38c", tags=("anime",)),
    CatalogCategory("game", "Video games", "\U0001f3ae", tags=("game",)),
    CatalogCategory("movie", "Movies & series", "\U0001f3ac", tags=("movie",)),
    CatalogCategory("celebrity", "Celebrities", "\u2b50", tags=("celebrity",)),
    CatalogCategory("character", "Character voices", "\U0001f5e3\ufe0f", tags=("character-voice",)),
    CatalogCategory("male", "Male voices", "\U0001f468", tags=("male",)),
    CatalogCategory("female", "Female voices", "\U0001f469", tags=("female",)),
    CatalogCategory("es", "Spanish", "\U0001f1ea\U0001f1f8", language="es"),
    CatalogCategory("news", "News anchors", "\U0001f4f0", tags=("news",)),
)


class _VoiceButton(discord.ui.Button):
    def __init__(self, voice: VoiceInfo, number: int, row: int) -> None:
        super().__init__(
            label=str(number),
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self.voice = voice

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.on_pick(interaction, self.voice)


class _NavButton(discord.ui.Button):
    def __init__(
        self, label: str, style: discord.ButtonStyle, custom_id: str, disabled: bool, row: int = NAV_ROW
    ) -> None:
        super().__init__(
            label=label,
            style=style,
            custom_id=custom_id,
            row=row,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.on_nav(interaction, self.custom_id)


class CatalogView(discord.ui.View):
    """Voice catalog: pick a category, then a numbered voice (sets + previews)."""

    def __init__(self, owner_id: int, language: str) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.language = language
        self.category: CatalogCategory | None = None
        self.voices: list[VoiceInfo] = []
        self.page = 0
        self.message: discord.Message | None = None
        self._render_categories()

    @property
    def _page_count(self) -> int:
        return max(1, (len(self.voices) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _page_voices(self) -> list[VoiceInfo]:
        start = self.page * PAGE_SIZE
        return self.voices[start : start + PAGE_SIZE]

    def _category_select(self) -> discord.ui.Select:
        options = [
            discord.SelectOption(label=cat.label, value=cat.key, emoji=cat.emoji)
            for cat in CATALOG_CATEGORIES
        ]
        select = discord.ui.Select(
            placeholder=t(self.language, "catalog_placeholder"),
            options=options,
            row=0,
        )
        select.callback = self.on_category
        return select

    def categories_embed(self) -> discord.Embed:
        lines = [f"### {cat.emoji} {cat.label}" for cat in CATALOG_CATEGORIES]
        embed = discord.Embed(
            title=t(self.language, "catalog_title"),
            description="\n\n".join(lines),
            color=ACCENT_COLOR,
        )
        embed.set_footer(text=t(self.language, "catalog_footer"))
        return embed

    def results_embed(self) -> discord.Embed:
        assert self.category is not None
        embed = discord.Embed(
            title=t(self.language, "catalog_results_title", category=self.category.label),
            description=format_voice_lines(self._page_voices()),
            color=ACCENT_COLOR,
        )
        embed.set_footer(text=page_footer(self.language, self.page + 1, self._page_count))
        return embed

    def _render_categories(self) -> None:
        self.clear_items()
        self.add_item(self._category_select())
        self.add_item(
            _NavButton(
                "\u25c0 " + t(self.language, "back_to_help"),
                discord.ButtonStyle.secondary,
                "help",
                False,
                row=NAV_ROW,
            )
        )

    def _render_results(self) -> None:
        self.clear_items()
        self.add_item(
            _NavButton(
                "\u25c0 " + t(self.language, "catalog_back"),
                discord.ButtonStyle.secondary,
                "back",
                False,
                row=0,
            )
        )
        for offset, voice in enumerate(self._page_voices()):
            self.add_item(_VoiceButton(voice, offset + 1, row=1 + offset // 5))
        self.add_item(_NavButton("\u25c0", discord.ButtonStyle.secondary, "prev", self.page == 0))
        self.add_item(_NavButton("\u25b6", discord.ButtonStyle.secondary, "next", self.page >= self._page_count - 1))

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            t(self.language, "owner_error"), ephemeral=True
        )
        return False

    async def on_category(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_owner(interaction):
            return
        category = next(
            (c for c in CATALOG_CATEGORIES if c.key == interaction.data["values"][0]),
            None,
        )
        if category is None:
            return
        await interaction.response.defer()
        self.category = category
        title_language = (
            voice_language_filter(self.language) if not category.language else None
        )
        self.voices = await list_public_voices(
            50,
            tags=list(category.tags),
            language=category.language,
            title_language=title_language,
        )
        self.page = 0
        if not self.voices:
            await interaction.followup.send(
                t(self.language, "catalog_no_results", category=category.label),
                ephemeral=True,
            )
            return
        self._render_results()
        await interaction.edit_original_response(embed=self.results_embed(), view=self)

    async def on_pick(self, interaction: discord.Interaction, voice: VoiceInfo) -> None:
        if not await self._ensure_owner(interaction):
            return
        async with get_session() as session:
            await users.set_user_voice(session, self.owner_id, voice.id, voice_title=voice.title)
        self.stop()
        embed = discord.Embed(
            title=t(self.language, "voice_set_title"),
            description=t(self.language, "voice_set_desc", title=voice.title),
            color=SUCCESS_COLOR,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        member = interaction.user
        if isinstance(member, discord.Member) and member.voice is not None:
            try:
                audio = await synthesize(CATALOG_PREVIEW_TEXT, voice.id)
            except TTSFailure:
                return
            try:
                vc = await playback.ensure_connected(member.guild, member.voice.channel)
                await playback.enqueue(vc, audio)
            except Exception:
                pass

    async def on_nav(self, interaction: discord.Interaction, action: str) -> None:
        if not await self._ensure_owner(interaction):
            return
        if action == "help":
            await self._back_to_help(interaction)
            return
        if action == "back":
            self.category = None
            self.voices = []
            self.page = 0
            self._render_categories()
            await interaction.response.edit_message(embed=self.categories_embed(), view=self)
            return
        if action == "prev":
            self.page = max(0, self.page - 1)
        elif action == "next":
            self.page = min(self._page_count - 1, self.page + 1)
        self._render_results()
        await interaction.response.edit_message(embed=self.results_embed(), view=self)

    async def _back_to_help(self, interaction: discord.Interaction) -> None:
        from src.cogs.help import help_embed
        from src.ui.quick_help import QuickHelpView

        view = QuickHelpView(self.owner_id, self.language)
        view.message = self.message
        self.stop()
        await interaction.response.edit_message(
            embed=help_embed(self.language), view=view
        )

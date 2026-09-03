from __future__ import annotations

import discord

from src.db import get_session
from src.fish.voices import VoiceInfo
from src.i18n import t
from src.store import users
from src.ui.formatting import format_voice_lines, page_footer

PAGE_SIZE = 10
NAV_ROW = 4

ACCENT_COLOR = 0x5865F2
SUCCESS_COLOR = 0x57F287


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


class VoicePickerView(discord.ui.View):
    def __init__(self, owner_id: int, voices: list[VoiceInfo], query: str, language: str) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.voices = voices
        self.query = query
        self.language = language
        self.page = 0
        self.message: discord.Message | None = None
        self._render()

    @property
    def _page_count(self) -> int:
        return max(1, (len(self.voices) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _page_voices(self) -> list[VoiceInfo]:
        start = self.page * PAGE_SIZE
        return self.voices[start : start + PAGE_SIZE]

    def embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=t(self.language, "picker_title", query=self.query),
            description=format_voice_lines(self._page_voices()),
            color=ACCENT_COLOR,
        )
        embed.set_footer(text=page_footer(self.language, self.page + 1, self._page_count))
        return embed

    def _render(self) -> None:
        self.clear_items()
        for offset, voice in enumerate(self._page_voices()):
            self.add_item(_VoiceButton(voice, offset + 1, row=offset // 5))
        self.add_item(
            _NavButton(
                "\u25c0 " + t(self.language, "back_to_help"),
                discord.ButtonStyle.secondary,
                "help",
                False,
                row=2,
            )
        )
        self.add_item(_NavButton("\u25c0", discord.ButtonStyle.secondary, "prev", self.page == 0))
        self.add_item(_NavButton("\u25b6", discord.ButtonStyle.secondary, "next", self.page >= self._page_count - 1))

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            t(self.language, "owner_error"), ephemeral=True
        )
        return False

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

    async def on_nav(self, interaction: discord.Interaction, action: str) -> None:
        if not await self._ensure_owner(interaction):
            return
        if action == "help":
            await self._back_to_help(interaction)
            return
        if action == "prev":
            self.page = max(0, self.page - 1)
        elif action == "next":
            self.page = min(self._page_count - 1, self.page + 1)
        self._render()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def _back_to_help(self, interaction: discord.Interaction) -> None:
        from src.cogs.help import help_embed
        from src.ui.quick_help import QuickHelpView

        view = QuickHelpView(self.owner_id, self.language)
        view.message = self.message
        self.stop()
        await interaction.response.edit_message(
            embed=help_embed(self.language), view=view
        )

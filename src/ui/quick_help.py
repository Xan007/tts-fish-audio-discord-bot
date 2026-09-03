from __future__ import annotations

import discord

from src.fish.voices import search_public_voices
from src.i18n import t, voice_language_filter
from src.ui.catalog import CatalogView
from src.ui.voice_picker import VoicePickerView


class SearchModal(discord.ui.Modal):
    def __init__(self, parent: "QuickHelpView") -> None:
        self.parent = parent
        super().__init__(title=t(parent.language, "modal_title"))
        self.query = discord.ui.TextInput(
            label=t(parent.language, "modal_query_label"),
            placeholder=t(parent.language, "modal_placeholder"),
            max_length=100,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        query = self.query.value.strip()
        results = await search_public_voices(
            query, limit=50, title_language=voice_language_filter(self.parent.language)
        )
        if not results:
            await interaction.followup.send(
                t(self.parent.language, "no_results"), ephemeral=True
            )
            return
        picker = VoicePickerView(
            self.parent.owner_id, results, query, self.parent.language
        )
        picker.message = self.parent.message
        await interaction.edit_original_response(embed=picker.embed(), view=picker)
        self.parent.stop()


class _ActionButton(discord.ui.Button):
    def __init__(self, label: str, style: discord.ButtonStyle, action: str) -> None:
        super().__init__(label=label, style=style, custom_id=action)
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.on_action(interaction, self.action)


class QuickHelpView(discord.ui.View):
    """Quick help with buttons that jump straight into the voice pickers."""

    def __init__(self, owner_id: int, language: str) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.language = language
        self.message: discord.Message | None = None
        self.add_item(
            _ActionButton(
                t(language, "button_catalog"), discord.ButtonStyle.primary, "catalog"
            )
        )
        self.add_item(
            _ActionButton(
                t(language, "button_search"), discord.ButtonStyle.secondary, "search"
            )
        )

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            t(self.language, "owner_error"), ephemeral=True
        )
        return False

    async def on_action(self, interaction: discord.Interaction, action: str) -> None:
        if not await self._ensure_owner(interaction):
            return
        if action == "catalog":
            catalog = CatalogView(self.owner_id, self.language)
            catalog.message = self.message
            self.stop()
            await interaction.response.edit_message(
                embed=catalog.categories_embed(), view=catalog
            )
        elif action == "search":
            await interaction.response.send_modal(SearchModal(self))

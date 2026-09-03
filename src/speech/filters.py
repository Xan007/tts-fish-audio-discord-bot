from __future__ import annotations

import re

import discord

from src.i18n import t

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")
CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
CUSTOM_EMOJI_RE = re.compile(r"<a?:(\w+):(\d+)>")


async def clean_for_tts(message: discord.Message, language: str = "en") -> str | None:
    """Turn a chat message into something natural to read aloud.

    - URLs are replaced with a short note ("Link sent").
    - Image/file attachments are announced ("Image sent" / "File sent").
    - User/role/channel mentions become their names.
    - Custom emojis become their short name.
    Returns None when there is nothing to say.
    """
    text = message.content or ""
    text = _replace_user_mentions(message, text)
    text = _replace_role_mentions(message, text)
    text = _replace_channel_mentions(message, text)
    text = CUSTOM_EMOJI_RE.sub(lambda m: m.group(1), text)

    extras: list[str] = []
    if URL_RE.search(text):
        text_without_urls = URL_RE.sub("", text).strip()
        if not text_without_urls:
            extras.append(t(language, "note_url"))
            text = ""
        else:
            extras.append(t(language, "note_url"))
            text = text_without_urls

    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image"):
            extras.append(t(language, "note_image"))
        else:
            extras.append(t(language, "note_file"))

    if message.embeds and not text:
        extras.append(t(language, "note_url"))

    parts = [p for p in (text.strip(), *extras) if p]
    if not parts:
        return None
    return ". ".join(parts) + "."


async def clean_text_for_tts(
    text: str, context: discord.Message | discord.Interaction
) -> str:
    """Light cleaning for explicit /tts text: keep URLs as-is, but turn
    mentions and custom emojis into readable names."""
    text = _replace_user_mentions(context, text)
    text = _replace_role_mentions(context, text)
    text = _replace_channel_mentions(context, text)
    return CUSTOM_EMOJI_RE.sub(lambda m: m.group(1), text)


def _replace_user_mentions(context: discord.Message | discord.Interaction, text: str) -> str:
    guild = context.guild
    def repl(match: re.Match[str]) -> str:
        uid = int(match.group(1))
        if guild is not None:
            member = guild.get_member(uid)
            if member is not None:
                return member.display_name
        return ""

    return USER_MENTION_RE.sub(repl, text)


def _replace_role_mentions(context: discord.Message | discord.Interaction, text: str) -> str:
    guild = context.guild
    def repl(match: re.Match[str]) -> str:
        rid = int(match.group(1))
        if guild is not None:
            role = guild.get_role(rid)
            if role is not None:
                return role.name
        return ""

    return ROLE_MENTION_RE.sub(repl, text)


def _replace_channel_mentions(context: discord.Message | discord.Interaction, text: str) -> str:
    guild = context.guild
    def repl(match: re.Match[str]) -> str:
        cid = int(match.group(1))
        if guild is not None:
            ch = guild.get_channel(cid)
            if ch is not None:
                return ch.name
        return ""

    return CHANNEL_MENTION_RE.sub(repl, text)

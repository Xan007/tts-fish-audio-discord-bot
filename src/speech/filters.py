from __future__ import annotations

import re

import discord

from src.i18n import t

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")
CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
CUSTOM_EMOJI_RE = re.compile(r"<a?:(\w+):(\d+)>")


CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\s*([\s\S]*?)```")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
GIF_URL_RE = re.compile(r"https?://(?:tenor\.com|giphy\.com)/\S+", re.IGNORECASE)
SPOILER_RE = re.compile(r"\|\|(.*?)\|\|")


async def clean_for_tts(message: discord.Message, language: str = "en") -> str | None:
    """Turn a chat message into a natural, spoken audio script.

    - URLs are replaced with friendly audio notes (e.g. "link", "GIF").
    - Code blocks and inline code are summarized or normalized.
    - Image, video, audio, and general attachments are announced cleanly.
    - Stickers are announced.
    - User/role/channel mentions become their friendly display names.
    - Custom emojis become their name without colons/IDs.
    - Spoilers are stripped of markdown.
    - Excess whitespace/punctuation is collapsed.
    Returns None when there is nothing meaningful to say.
    """
    text = message.content or ""

    # Replace spoilers markdown delimiters
    text = SPOILER_RE.sub(r"\1", text)

    # Process mentions & emojis
    text = _replace_user_mentions(message, text)
    text = _replace_role_mentions(message, text)
    text = _replace_channel_mentions(message, text)
    text = CUSTOM_EMOJI_RE.sub(lambda m: m.group(1).replace("_", " "), text)

    extras: list[str] = []

    # Handle code blocks
    if CODE_BLOCK_RE.search(text):
        text = CODE_BLOCK_RE.sub(f" [{t(language, 'note_code')}] ", text)
    if INLINE_CODE_RE.search(text):
        text = INLINE_CODE_RE.sub(r"\1", text)

    # Handle GIFs and URLs
    if GIF_URL_RE.search(text):
        text = GIF_URL_RE.sub("", text)
        extras.append(t(language, "note_gif"))

    if URL_RE.search(text):
        text = URL_RE.sub("", text)
        extras.append(t(language, "note_url"))

    # Handle attachments
    for attachment in message.attachments:
        ctype = (attachment.content_type or "").lower()
        fname = attachment.filename.lower()
        if ctype.startswith("image") or fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
            extras.append(t(language, "note_image"))
        elif ctype.startswith("video") or fname.endswith((".mp4", ".webm", ".mov", ".mkv")):
            extras.append(t(language, "note_video"))
        elif ctype.startswith("audio") or fname.endswith((".mp3", ".wav", ".ogg", ".m4a", ".flac")):
            extras.append(t(language, "note_audio"))
        else:
            extras.append(t(language, "note_file"))

    # Handle stickers
    if getattr(message, "stickers", None):
        for sticker in message.stickers:
            extras.append(f"{t(language, 'note_sticker')} {sticker.name}")

    # Handle embeds when there is no text or attachments
    if message.embeds and not text.strip() and not extras:
        extras.append(t(language, "note_url"))

    text = _normalize_text(text)
    parts = [p for p in (text, *extras) if p]
    if not parts:
        return None
    return ". ".join(parts) + "."


async def clean_text_for_tts(
    text: str, context: discord.Message | discord.Interaction, language: str = "en"
) -> str:
    """Filter and sanitize explicit /tts text: keep links as 'link' notes,
    expand mentions and custom emojis, and clean formatting."""
    text = SPOILER_RE.sub(r"\1", text)
    text = _replace_user_mentions(context, text)
    text = _replace_role_mentions(context, text)
    text = _replace_channel_mentions(context, text)
    text = CUSTOM_EMOJI_RE.sub(lambda m: m.group(1).replace("_", " "), text)

    extras: list[str] = []
    if GIF_URL_RE.search(text):
        text = GIF_URL_RE.sub("", text)
        extras.append(t(language, "note_gif"))
    if URL_RE.search(text):
        text = URL_RE.sub("", text)
        extras.append(t(language, "note_url"))

    if CODE_BLOCK_RE.search(text):
        text = CODE_BLOCK_RE.sub(f" [{t(language, 'note_code')}] ", text)
    if INLINE_CODE_RE.search(text):
        text = INLINE_CODE_RE.sub(r"\1", text)

    text = _normalize_text(text)
    parts = [p for p in (text, *extras) if p]
    if not parts:
        return ""
    return ". ".join(parts)


def _normalize_text(text: str) -> str:
    """Collapse duplicate punctuation, excessive whitespace, and repeated spam words."""
    # Collapse multiple spaces and newlines
    text = re.sub(r"\s+", " ", text).strip()
    # Collapse excessive punctuation (e.g. !!!!!!! -> !)
    text = re.sub(r"([!?.,])\1{2,}", r"\1\1", text)

    # Collapse repetitive spam words (e.g. 'palabra' repeated 10 times -> maximum 3 times)
    words = text.split(" ")
    if len(words) > 3:
        cleaned_words: list[str] = []
        repeat_count = 1
        for i, word in enumerate(words):
            if i > 0 and word.lower() == words[i - 1].lower():
                repeat_count += 1
                if repeat_count <= 3:
                    cleaned_words.append(word)
            else:
                repeat_count = 1
                cleaned_words.append(word)
        text = " ".join(cleaned_words)

    return text


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

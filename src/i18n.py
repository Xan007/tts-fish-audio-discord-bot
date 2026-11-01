from __future__ import annotations

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.store import users

SUPPORTED_LANGUAGES = ("en", "es")
DEFAULT_LANGUAGE = "en"

LANGUAGE_LABELS = {
    "auto": {"en": "Auto", "es": "Auto"},
    "en": {"en": "English", "es": "English"},
    "es": {"en": "Español", "es": "Español"},
}

STRINGS: dict[str, dict[str, str]] = {
    # voice picker
    "picker_title": {"en": "Voice search: {query}", "es": "Búsqueda de voces: {query}"},
    "picker_footer": {
        "en": "Page {page} of {total} - pick a voice",
        "es": "Página {page} de {total} - elige una voz",
    },
    "voice_set_title": {"en": "Voice set", "es": "Voz configurada"},
    "voice_set_desc": {"en": "**{title}** is now your voice.", "es": "**{title}** es ahora tu voz."},
    "no_results": {"en": "No voices found for that query.", "es": "No se encontraron voces para esa búsqueda."},
    "owner_error": {"en": "This menu belongs to someone else.", "es": "Este menú pertenece a otra persona."},
    # catalog
    "catalog_title": {"en": "Voice catalog", "es": "Catálogo de voces"},
    "catalog_placeholder": {"en": "Pick a category", "es": "Elige una categoría"},
    "catalog_footer": {
        "en": "Pick a voice with the buttons below",
        "es": "Elige una voz con los botones de abajo",
    },
    "catalog_results_title": {
        "en": "Top voices · {category}",
        "es": "Mejores voces · {category}",
    },
    "catalog_back": {"en": "Back", "es": "Atrás"},
    "back_to_help": {"en": "Help", "es": "Ayuda"},
    "catalog_no_results": {
        "en": "No voices found for **{category}**.",
        "es": "No se encontraron voces para **{category}**.",
    },
    # quick help
    "modal_title": {"en": "Search voices", "es": "Buscar voces"},
    "modal_query_label": {"en": "Search terms", "es": "Términos de búsqueda"},
    "modal_placeholder": {
        "en": "e.g. anime girl or a fish.audio URL",
        "es": "p. ej. chica anime o un enlace de fish.audio",
    },
    "button_catalog": {"en": "Catalog", "es": "Catálogo"},
    "button_search": {"en": "Search", "es": "Buscar"},
    # help embed
    "help_title": {"en": "Quick guide", "es": "Guía rápida"},
    "help_desc": {"en": "Pick a voice, then talk.", "es": "Elige una voz y habla."},
    "help_catalog": {"en": "Voice catalog", "es": "Catálogo de voces"},
    "help_catalog_value": {
        "en": "/voices - popular voices by category",
        "es": "/voices - voces populares por categoría",
    },
    "help_search": {"en": "Search voices", "es": "Buscar voces"},
    "help_search_value": {
        "en": "/voice search - find any voice",
        "es": "/voice search - encuentra cualquier voz",
    },
    "help_speak": {"en": "Speak", "es": "Hablar"},
    "help_speak_value": {
        "en": "/tts <text> - say something out loud",
        "es": "/tts <texto> - di algo en voz alta",
    },
    "help_join": {"en": "Join voice", "es": "Entrar a voz"},
    "help_join_value": {
        "en": "/join - join the voice channel you are in",
        "es": "/join - entra al canal de voz donde estás",
    },
    "help_autojoin": {"en": "Autojoin", "es": "Autojoin"},
    "help_autojoin_value": {
        "en": "/autojoin enable - reply to chat automatically",
        "es": "/autojoin enable - responde al chat automáticamente",
    },
    "help_language": {"en": "Language", "es": "Idioma"},
    "help_language_value": {
        "en": "/language - auto, English or Español",
        "es": "/language - auto, English o Español",
    },
    "help_footer": {"en": "Tip: mention me anytime.", "es": "Tip: mencióname cuando quieras."},
    # voice commands
    "v_not_found": {
        "en": "That voice was not found. Provide a valid voice id or a fish.audio URL.",
        "es": "No se encontró esa voz. Proporciona un ID válido o un enlace de fish.audio.",
    },
    "v_set": {"en": "Voice set to **{title}**.", "es": "Voz configurada: **{title}**."},
    "v_set_for": {
        "en": "Voice set to **{title}** for **{user}**.",
        "es": "Voz configurada para **{user}**: **{title}**.",
    },
    "v_info_default": {
        "en": "You are using the default voice `{id}` with speed {speed} and volume {volume} dB.",
        "es": "Usas la voz por defecto `{id}` con velocidad {speed} y volumen {volume} dB.",
    },
    "v_info": {
        "en": "Voice: **{title}** (`{id}`)\nSpeed: {speed}\nVolume: {volume} dB",
        "es": "Voz: **{title}** (`{id}`)\nVelocidad: {speed}\nVolumen: {volume} dB",
    },
    "v_reset": {
        "en": "Your voice has been reset to the default.",
        "es": "Tu voz se ha restablecido a la predeterminada.",
    },
    "v_need_vc": {
        "en": "You must be in a voice channel to preview a voice.",
        "es": "Debes estar en un canal de voz para probar una voz.",
    },
    "v_preview_fail": {
        "en": "Could not generate a preview with that voice.",
        "es": "No se pudo generar una prueba con esa voz.",
    },
    "v_join_fail": {
        "en": "Could not join the voice channel.",
        "es": "No se pudo unir al canal de voz.",
    },
    "v_playing_preview": {"en": "Playing preview.", "es": "Reproduciendo prueba."},
    "v_speed_set": {"en": "Your speech speed is now {speed}.", "es": "Tu velocidad de voz es ahora {speed}."},
    "v_volume_set": {"en": "Your volume is now {volume} dB.", "es": "Tu volumen es ahora {volume} dB."},
    # tts command
    "tts_server_only": {
        "en": "This command must be used in a server.",
        "es": "Este comando debe usarse en un servidor.",
    },
    "tts_empty": {
        "en": "Nothing to say after cleaning mentions.",
        "es": "No hay nada que decir tras limpiar las menciones.",
    },
    "join_need_vc": {
        "en": "Join a voice channel first, then use `/join`.",
        "es": "Primero entra a un canal de voz y luego usa `/join`.",
    },
    "join_no_permission": {
        "en": "I need the Connect permission in {channel} to join it.",
        "es": "Necesito el permiso Conectar en {channel} para entrar.",
    },
    "join_failed": {
        "en": "I couldn't join {channel}. Check my channel permissions and try again.",
        "es": "No pude entrar a {channel}. Revisa mis permisos en el canal e inténtalo de nuevo.",
    },
    "join_success": {
        "en": "Joined {channel}.",
        "es": "Entré a {channel}.",
    },
    # autojoin
    "aj_need_vc_enable": {
        "en": "You must be in a voice channel to enable autojoin.",
        "es": "Debes estar en un canal de voz para activar autojoin.",
    },
    "aj_need_same_vc": {
        "en": "Run this command in the voice channel you are connected to.",
        "es": "Ejecuta este comando en el canal de voz al que estás conectado.",
    },
    "aj_enabled": {
        "en": "Autojoin enabled for this voice channel.",
        "es": "Autojoin activado para este canal de voz.",
    },
    "aj_need_vc_disable": {
        "en": "You must be in a voice channel to disable autojoin.",
        "es": "Debes estar en un canal de voz para desactivar autojoin.",
    },
    "aj_disabled": {
        "en": "Autojoin disabled for this voice channel.",
        "es": "Autojoin desactivado para este canal de voz.",
    },
    # speech pipeline
    "p_need_vc": {
        "en": "You must be in a voice channel to use this command.",
        "es": "Debes estar en un canal de voz para usar este comando.",
    },
    "p_playing": {"en": "Playing.", "es": "Reproduciendo."},
    "p_failed": {"en": "Synthesis failed: {error}", "es": "Error de síntesis: {error}"},
    "p_join_fail": {
        "en": "Could not join the voice channel: {error}",
        "es": "No se pudo unir al canal de voz: {error}",
    },
    "p_stopped": {"en": "Speech pipeline stopped.", "es": "El sistema de voz se detuvo."},
    "p_crashed": {"en": "Speech pipeline crashed.", "es": "El sistema de voz falló."},
    "p_queue_full": {
        "en": "The speech queue is full. Please try again in a moment.",
        "es": "La cola de voz está llena. Inténtalo de nuevo en un momento.",
    },
    # language command
    "lang_title": {"en": "Bot language", "es": "Idioma del bot"},
    "lang_desc": {
        "en": "Set the language the bot replies to you in.",
        "es": "Configura el idioma en el que el bot te responde.",
    },
    "lang_done": {
        "en": "The bot will reply to you in **{language}**.",
        "es": "El bot te responderá en **{language}**.",
    },
    # controls & cancels
    "stop_success": {"en": "Stopped playback and cleared the queue.", "es": "Reproducción detenida y cola vaciada."},
    "skip_success": {"en": "Skipped current audio.", "es": "Audio actual saltado."},
    "cancel_btn": {"en": "Cancel", "es": "Cancelar"},
    "cancelled_by": {"en": "Cancelled by {user}.", "es": "Cancelado por {user}."},
    "cancel_perm_error": {
        "en": "Only the author of this message or an administrator can cancel it.",
        "es": "Solo el autor de este mensaje o un administrador pueden cancelarlo.",
    },
    "author_says": {"en": "{name} says: {text}", "es": "{name} dice: {text}"},
    # message notes spoken aloud
    "note_url": {"en": "link", "es": "enlace"},
    "note_image": {"en": "image", "es": "imagen"},
    "note_video": {"en": "video", "es": "video"},
    "note_audio": {"en": "audio note", "es": "audio"},
    "note_file": {"en": "attached file", "es": "archivo adjunto"},
    "note_code": {"en": "code block", "es": "bloque de código"},
    "note_sticker": {"en": "sticker", "es": "sticker"},
    "note_gif": {"en": "GIF", "es": "GIF"},
}


def t(lang: str, key: str, **kwargs) -> str:
    translations = STRINGS[key]
    text = translations.get(lang, translations[DEFAULT_LANGUAGE])
    if kwargs:
        return text.format(**kwargs)
    return text


def language_label(language: str, name: str) -> str:
    return LANGUAGE_LABELS[name].get(language, LANGUAGE_LABELS[name]["en"])


def voice_language_filter(lang: str) -> list[str] | None:
    """Title-language filter for voice searches; None shows all languages."""
    if lang in SUPPORTED_LANGUAGES:
        return [lang]
    return None


def language_from_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LANGUAGE
    code = str(locale).split("-")[0].lower()
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def effective_language(user_language: str | None, locale: str | None) -> str:
    if user_language in SUPPORTED_LANGUAGES:
        return user_language
    return language_from_locale(locale)


def interaction_language(interaction: discord.Interaction, user_language: str | None) -> str:
    return effective_language(user_language, str(interaction.locale))


def member_language(member: discord.Member, user_language: str | None) -> str:
    guild = getattr(member, "guild", None)
    locale = str(guild.locale) if guild is not None else None
    return effective_language(user_language, locale)


async def get_language_for_user(
    session: AsyncSession | None,
    user_id: int,
    *,
    interaction: discord.Interaction | None = None,
    member: discord.Member | None = None,
) -> str:
    if session is not None:
        user_language = await users.get_user_language(session, user_id)
    else:
        async with get_session() as s:
            user_language = await users.get_user_language(s, user_id)

    if user_language in SUPPORTED_LANGUAGES:
        return user_language
    if interaction is not None:
        source = getattr(interaction, "locale", None)
    elif member is not None:
        guild = getattr(member, "guild", None)
        source = getattr(guild, "locale", None) if guild is not None else None
    else:
        source = None
    return language_from_locale(str(source) if source is not None else None)

from __future__ import annotations

from src.fish.voices import VoiceInfo
from src.i18n import t


def format_voice_lines(voices: list[VoiceInfo]) -> str:
    """Compact one-line-per-voice listing shared by catalog and search."""
    lines = []
    for index, voice in enumerate(voices, 1):
        lang = ", ".join(voice.languages[:3]) if voice.languages else "unknown"
        usage = f" · {voice.task_count:,} uses" if voice.task_count else ""
        lines.append(f"{index}. **{voice.title}** ({lang}){usage}")
    return "\n".join(lines)


def page_footer(language: str, page: int, total: int) -> str:
    return "\u25c0  " + t(language, "picker_footer", page=page, total=total) + "  \u25b6"

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Config:
    discord_token: str
    fish_api_key: str
    default_voice_id: str
    tts_model: str
    db_path: Path
    log_level: str
    guild_id: int | None
    speech_concurrency: int
    voice_idle_timeout: float
    bot_description: str


def load_config() -> Config:
    db_path_raw = os.environ.get("DB_PATH", "data/bot.db")
    db_path = Path(db_path_raw)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    guild_raw = os.environ.get("GUILD_ID")
    guild_id = int(guild_raw) if guild_raw and guild_raw.strip() else None

    return Config(
        discord_token=_env("DISCORD_TOKEN"),
        fish_api_key=_env("FISH_API_KEY"),
        default_voice_id=_env("DEFAULT_VOICE_ID", "933563129e564b19a115bedd57b7406a"),
        tts_model=os.environ.get("TTS_MODEL", "s2.1-pro-free"),
        db_path=db_path,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        guild_id=guild_id,
        speech_concurrency=int(os.environ.get("SPEECH_CONCURRENCY", "1")),
        voice_idle_timeout=float(os.environ.get("VOICE_IDLE_TIMEOUT", "600")),
        bot_description=os.environ.get("BOT_DESCRIPTION", ""),
    )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config

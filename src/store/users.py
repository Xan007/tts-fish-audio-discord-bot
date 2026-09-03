from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import UserVoiceModel

DEFAULT_SPEED = 1.0
DEFAULT_VOLUME_DB = 0
DEFAULT_LANGUAGE = "auto"


@dataclass(frozen=True)
class UserVoice:
    user_id: int
    voice_id: str
    voice_title: str | None
    set_at: int
    speed: float
    volume_db: int


async def get_user_voice(session: AsyncSession, user_id: int) -> UserVoice | None:
    stmt = select(UserVoiceModel).where(UserVoiceModel.user_id == user_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return UserVoice(
        user_id=row.user_id,
        voice_id=row.voice_id,
        voice_title=row.voice_title,
        set_at=row.set_at,
        speed=row.speed,
        volume_db=row.volume_db,
    )


async def set_user_voice(
    session: AsyncSession,
    user_id: int,
    voice_id: str,
    voice_title: str | None = None,
    speed: float = DEFAULT_SPEED,
    volume_db: int = DEFAULT_VOLUME_DB,
) -> UserVoice:
    now = int(time.time())
    stmt = (
        insert(UserVoiceModel)
        .values(
            user_id=user_id,
            voice_id=voice_id,
            voice_title=voice_title,
            set_at=now,
            speed=speed,
            volume_db=volume_db,
        )
        .on_conflict_do_update(
            index_elements=[UserVoiceModel.user_id],
            set_={
                "voice_id": voice_id,
                "voice_title": voice_title,
                "set_at": now,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    return UserVoice(user_id, voice_id, voice_title, now, speed, volume_db)


async def reset_user_voice(
    session: AsyncSession,
    user_id: int,
    default_voice_id: str,
    default_voice_title: str | None = None,
) -> UserVoice:
    now = int(time.time())
    stmt = (
        insert(UserVoiceModel)
        .values(
            user_id=user_id,
            voice_id=default_voice_id,
            voice_title=default_voice_title,
            set_at=now,
            speed=DEFAULT_SPEED,
            volume_db=DEFAULT_VOLUME_DB,
        )
        .on_conflict_do_update(
            index_elements=[UserVoiceModel.user_id],
            set_={
                "voice_id": default_voice_id,
                "voice_title": default_voice_title,
                "set_at": now,
                "speed": DEFAULT_SPEED,
                "volume_db": DEFAULT_VOLUME_DB,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    return UserVoice(
        user_id, default_voice_id, default_voice_title, now, DEFAULT_SPEED, DEFAULT_VOLUME_DB
    )


async def update_speed(
    session: AsyncSession, user_id: int, speed: float, default_voice_id: str
) -> None:
    now = int(time.time())
    stmt = (
        insert(UserVoiceModel)
        .values(
            user_id=user_id,
            voice_id=default_voice_id,
            voice_title=None,
            set_at=now,
            speed=speed,
            volume_db=DEFAULT_VOLUME_DB,
        )
        .on_conflict_do_update(
            index_elements=[UserVoiceModel.user_id],
            set_={"speed": speed},
        )
    )
    await session.execute(stmt)
    await session.commit()


async def update_volume(
    session: AsyncSession, user_id: int, volume_db: int, default_voice_id: str
) -> None:
    now = int(time.time())
    stmt = (
        insert(UserVoiceModel)
        .values(
            user_id=user_id,
            voice_id=default_voice_id,
            voice_title=None,
            set_at=now,
            speed=DEFAULT_SPEED,
            volume_db=volume_db,
        )
        .on_conflict_do_update(
            index_elements=[UserVoiceModel.user_id],
            set_={"volume_db": volume_db},
        )
    )
    await session.execute(stmt)
    await session.commit()


async def get_user_language(session: AsyncSession, user_id: int) -> str:
    stmt = select(UserVoiceModel.language).where(UserVoiceModel.user_id == user_id)
    result = await session.execute(stmt)
    lang = result.scalar_one_or_none()
    if lang is None:
        return DEFAULT_LANGUAGE
    return lang


async def set_user_language(
    session: AsyncSession,
    user_id: int,
    language: str,
    default_voice_id: str,
) -> None:
    now = int(time.time())
    stmt = (
        insert(UserVoiceModel)
        .values(
            user_id=user_id,
            voice_id=default_voice_id,
            voice_title=None,
            set_at=now,
            speed=DEFAULT_SPEED,
            volume_db=DEFAULT_VOLUME_DB,
            language=language,
        )
        .on_conflict_do_update(
            index_elements=[UserVoiceModel.user_id],
            set_={"language": language},
        )
    )
    await session.execute(stmt)
    await session.commit()


from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import GuildAutojoinModel


@dataclass(frozen=True)
class AutojoinChannel:
    guild_id: int
    voice_channel_id: int
    text_channel_id: int
    enabled: int


async def set_autojoin(
    session: AsyncSession,
    guild_id: int,
    voice_channel_id: int,
    text_channel_id: int,
    enabled: bool = True,
) -> None:
    stmt = (
        insert(GuildAutojoinModel)
        .values(
            guild_id=guild_id,
            voice_channel_id=voice_channel_id,
            text_channel_id=text_channel_id,
            enabled=1 if enabled else 0,
        )
        .on_conflict_do_update(
            index_elements=[GuildAutojoinModel.guild_id, GuildAutojoinModel.voice_channel_id],
            set_={
                "text_channel_id": text_channel_id,
                "enabled": 1 if enabled else 0,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()


async def disable_autojoin(
    session: AsyncSession, guild_id: int, voice_channel_id: int
) -> None:
    stmt = (
        update(GuildAutojoinModel)
        .where(
            GuildAutojoinModel.guild_id == guild_id,
            GuildAutojoinModel.voice_channel_id == voice_channel_id,
        )
        .values(enabled=0)
    )
    await session.execute(stmt)
    await session.commit()


async def get_autojoin_for_text_channel(
    session: AsyncSession, guild_id: int, text_channel_id: int
) -> list[AutojoinChannel]:
    stmt = select(GuildAutojoinModel).where(
        GuildAutojoinModel.guild_id == guild_id,
        GuildAutojoinModel.text_channel_id.in_([text_channel_id, 0]),
        GuildAutojoinModel.enabled == 1,
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        AutojoinChannel(
            guild_id=r.guild_id,
            voice_channel_id=r.voice_channel_id,
            text_channel_id=r.text_channel_id,
            enabled=r.enabled,
        )
        for r in rows
    ]


async def get_autojoin_for_voice_channel(
    session: AsyncSession, guild_id: int, voice_channel_id: int
) -> list[AutojoinChannel]:
    stmt = select(GuildAutojoinModel).where(
        GuildAutojoinModel.guild_id == guild_id,
        GuildAutojoinModel.voice_channel_id == voice_channel_id,
        GuildAutojoinModel.enabled == 1,
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        AutojoinChannel(
            guild_id=r.guild_id,
            voice_channel_id=r.voice_channel_id,
            text_channel_id=r.text_channel_id,
            enabled=r.enabled,
        )
        for r in rows
    ]


async def get_enabled_autojoin_for_guild(
    session: AsyncSession, guild_id: int
) -> list[AutojoinChannel]:
    stmt = select(GuildAutojoinModel).where(
        GuildAutojoinModel.guild_id == guild_id,
        GuildAutojoinModel.enabled == 1,
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        AutojoinChannel(
            guild_id=r.guild_id,
            voice_channel_id=r.voice_channel_id,
            text_channel_id=r.text_channel_id,
            enabled=r.enabled,
        )
        for r in rows
    ]


async def guild_has_autojoin(session: AsyncSession, guild_id: int) -> bool:
    stmt = (
        select(GuildAutojoinModel.guild_id)
        .where(
            GuildAutojoinModel.guild_id == guild_id,
            GuildAutojoinModel.enabled == 1,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None

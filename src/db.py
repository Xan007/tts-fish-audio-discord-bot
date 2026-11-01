from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Float, Integer, String, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config import get_config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class UserVoiceModel(Base):
    __tablename__ = "user_voices"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voice_id: Mapped[str] = mapped_column(String, nullable=False)
    voice_title: Mapped[str | None] = mapped_column(String, nullable=True)
    set_at: Mapped[int] = mapped_column(Integer, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    volume_db: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    language: Mapped[str] = mapped_column(String, nullable=False, default="auto")


class GuildAutojoinModel(Base):
    __tablename__ = "guild_autojoin"

    guild_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voice_channel_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        db_path = get_config().db_path.resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        _engine = create_async_engine(
            url,
            echo=False,
            pool_size=1,
            max_overflow=0,
            connect_args={"timeout": 30},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate)


def _migrate(connection) -> None:
    inspector = inspect(connection)
    if "user_voices" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("user_voices")}
        if "language" not in columns:
            connection.execute(
                text("ALTER TABLE user_voices ADD COLUMN language VARCHAR NOT NULL DEFAULT 'auto'")
            )


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None

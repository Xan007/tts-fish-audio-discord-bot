from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import discord

from src.audio.playback import PlaybackManager, StreamSource, StreamSourceError, playback
from src.config import get_config
from src.db import get_session
from src.fish.tts import synthesize_stream
from src.i18n import t
from src.store import users

logger = logging.getLogger(__name__)

_BACKLOG_WARNING_AT = 10


@dataclass(frozen=True)
class SpeakResult:
    ok: bool
    message: str


@dataclass
class SpeechJob:
    guild_id: int
    channel: discord.VoiceChannel
    user_id: int
    text: str
    language: str = "en"
    future: asyncio.Future | None = None


def _voice_settings(user_voice: users.UserVoice | None) -> tuple[str, float, int]:
    config = get_config()
    if user_voice is None:
        return config.default_voice_id, users.DEFAULT_SPEED, users.DEFAULT_VOLUME_DB
    return user_voice.voice_id, user_voice.speed, user_voice.volume_db


class SpeechPipeline:
    """FIFO speech queue per guild with bounded Fish Audio concurrency.

    Messages are processed in submission order per guild. Up to
    ``max_concurrency`` messages are synthesized in parallel at any time
    (across all guilds), but audio is enqueued for playback strictly in
    order, so a fast request can never overtake a slow one.
    """

    def __init__(
        self,
        max_concurrency: int = 3,
        manager: PlaybackManager = playback,
    ) -> None:
        self._max_concurrency = max(1, max_concurrency)
        self._manager = manager
        self._sem = asyncio.Semaphore(self._max_concurrency)
        self._queues: dict[int, asyncio.Queue[SpeechJob]] = {}
        self._workers: dict[int, asyncio.Task] = {}
        self._spawn_locks: dict[int, asyncio.Lock] = {}

    async def submit(
        self,
        guild_id: int,
        channel: discord.VoiceChannel,
        user_id: int,
        text: str,
        language: str = "en",
    ) -> SpeakResult:
        job = SpeechJob(
            guild_id=guild_id,
            channel=channel,
            user_id=user_id,
            text=text,
            language=language,
        )
        job.future = asyncio.get_running_loop().create_future()
        queue = self._queues.setdefault(guild_id, asyncio.Queue())
        await queue.put(job)
        if queue.qsize() >= _BACKLOG_WARNING_AT and queue.qsize() % _BACKLOG_WARNING_AT == 0:
            logger.warning(
                "Speech backlog in guild %s: %d messages queued", guild_id, queue.qsize()
            )
        await self._spawn_worker(guild_id)
        return await job.future

    async def _spawn_worker(self, guild_id: int) -> None:
        lock = self._spawn_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            worker = self._workers.get(guild_id)
            if worker is None or worker.done():
                self._workers[guild_id] = asyncio.create_task(
                    self._run(guild_id), name=f"speech-{guild_id}"
                )

    async def _run(self, guild_id: int) -> None:
        queue = self._queues[guild_id]
        try:
            while True:
                batch = [await queue.get()]
                for _ in range(self._max_concurrency - 1):
                    try:
                        batch.append(queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                try:
                    results = await asyncio.gather(
                        *(self._synthesize(job) for job in batch)
                    )
                    for job, (audio, result) in zip(batch, results):
                        if audio is not None:
                            result = await self._play_audio(job, audio)
                        self._resolve(job, result)
                except asyncio.CancelledError:
                    self._fail_batch(batch, t(job.language, "p_stopped"))
                    raise
                except Exception:
                    logger.exception("Speech pipeline crashed in guild %s", guild_id)
                    self._fail_batch(batch, t(job.language, "p_crashed"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Speech pipeline crashed in guild %s", guild_id)

    async def _synthesize(
        self, job: SpeechJob
    ) -> tuple[StreamSource | None, SpeakResult]:
        async with get_session() as session:
            user_voice = await users.get_user_voice(session, job.user_id)
        voice_id, speed, volume_db = _voice_settings(user_voice)
        try:
            source = StreamSource(self._bounded(synthesize_stream(job.text, voice_id, speed=speed, volume_db=volume_db)))
            source.start()
        except Exception as e:
            logger.exception("Unexpected synthesis failure for user %s", job.user_id)
            return None, SpeakResult(False, t(job.language, "p_failed", error=e))
        try:
            await source.wait_first()
        except asyncio.CancelledError:
            source.cancel()
            raise
        except StreamSourceError as e:
            source.cancel()
            return None, SpeakResult(False, t(job.language, "p_failed", error=e))
        return source, SpeakResult(True, t(job.language, "p_playing"))

    def _bounded(self, stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        async def generator() -> AsyncIterator[bytes]:
            async with self._sem:
                async for chunk in stream:
                    yield chunk
        return generator()

    async def _play_audio(self, job: SpeechJob, audio: StreamSource) -> SpeakResult:
        try:
            vc = await self._manager.ensure_connected(job.channel.guild, job.channel)
        except Exception as e:
            audio.cancel()
            logger.exception("Failed to connect to voice channel for user %s", job.user_id)
            return SpeakResult(False, t(job.language, "p_join_fail", error=e))
        await self._manager.enqueue(vc, audio)
        return SpeakResult(True, t(job.language, "p_playing"))

    def cleanup(self, guild_id: int) -> None:
        queue = self._queues.pop(guild_id, None)
        if queue is not None:
            while not queue.empty():
                job = queue.get_nowait()
                self._resolve(job, SpeakResult(False, t(job.language, "p_stopped")))
        worker = self._workers.pop(guild_id, None)
        if worker is not None and not worker.done():
            worker.cancel()

    @staticmethod
    def _resolve(job: SpeechJob, result: SpeakResult) -> None:
        if job.future is not None and not job.future.done():
            job.future.set_result(result)

    @classmethod
    def _fail_batch(cls, batch: list[SpeechJob], message: str) -> None:
        for job in batch:
            cls._resolve(job, SpeakResult(False, message))


pipeline = SpeechPipeline(
    max_concurrency=get_config().speech_concurrency,
)

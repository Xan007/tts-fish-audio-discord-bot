from __future__ import annotations

import asyncio
import logging
import subprocess
from collections.abc import AsyncIterator, Callable
from io import BytesIO

import discord

from src.config import get_config

logger = logging.getLogger(__name__)

FFMPEG_OPTIONS = {
    "before_options": "-loglevel error -nostdin",
    "options": "-vn",
}

_FFMPEG_ARGS = [
    "ffmpeg",
    "-loglevel",
    "error",
    "-nostdin",
    "-i",
    "-",
    "-vn",
    "-f",
    "s16le",
    "-ar",
    "48000",
    "-ac",
    "2",
    "pipe:1",
]


class PlaybackError(Exception):
    """Raised when audio playback cannot start or fails."""


class StreamSourceError(Exception):
    """Raised when an audio stream fails before or during playback."""


class StreamSource:
    """Async iterable of audio chunks produced eagerly by a pump task.

    The pump starts iterating ``stream`` as soon as :meth:`start` is called
    and pushes chunks through a bounded queue so playback can begin without
    waiting for the full download.
    """

    def __init__(self, stream: AsyncIterator[bytes], queue_maxsize: int = 32) -> None:
        self._stream = stream
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=queue_maxsize)
        self._first: asyncio.Future | None = None
        self._error: Exception | None = None
        self._pump: asyncio.Task | None = None

    def start(self) -> None:
        if self._pump is None:
            self._first = asyncio.get_running_loop().create_future()
            self._pump = asyncio.create_task(self._pump_loop())

    async def wait_first(self, timeout: float = 30.0) -> None:
        """Wait until the first chunk is available.

        Raises :class:`StreamSourceError` on synthesis failure or timeout.
        """
        assert self._first is not None
        try:
            await asyncio.wait_for(asyncio.shield(self._first), timeout)
        except asyncio.TimeoutError:
            raise StreamSourceError("Synthesis timed out.") from None
        except Exception as e:
            raise StreamSourceError(str(e)) from e

    async def _pump_loop(self) -> None:
        assert self._first is not None
        try:
            async for chunk in self._stream:
                await self._queue.put(chunk)
                if not self._first.done():
                    self._first.set_result(None)
            if not self._first.done():
                self._first.set_result(None)
            await self._queue.put(None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._error = e
            if not self._first.done():
                self._first.set_exception(e)
            await self._queue.put(None)

    def __aiter__(self) -> StreamSource:
        return self

    async def __anext__(self) -> bytes:
        item = await self._queue.get()
        if item is None:
            if self._error is not None:
                raise StreamSourceError(str(self._error)) from self._error
            raise StopAsyncIteration
        return item

    def cancel(self) -> None:
        if self._pump is not None and not self._pump.done():
            self._pump.cancel()


class PlaybackManager:
    """Per-guild FIFO audio queue with voice connection management."""

    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue[bytes | StreamSource]] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._clients: dict[int, discord.VoiceClient] = {}
        self._channels: dict[int, discord.VoiceChannel] = {}
        self._connect_locks: dict[int, asyncio.Lock] = {}
        self._stay: set[int] = set()

    def set_stay(self, guild_id: int, stay: bool) -> None:
        if stay:
            self._stay.add(guild_id)
        else:
            self._stay.discard(guild_id)

    async def ensure_connected(
        self, guild: discord.Guild, channel: discord.VoiceChannel
    ) -> discord.VoiceClient:
        guild_id = guild.id
        lock = self._connect_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            vc = guild.voice_client
            if vc is None:
                return await channel.connect(self_deaf=True)
            if vc.channel.id != channel.id:
                await vc.move_to(channel)
            return vc

    async def enqueue(
        self, voice_client: discord.VoiceClient, data: bytes | StreamSource
    ) -> None:
        guild_id = voice_client.guild.id
        self._clients[guild_id] = voice_client
        if voice_client.channel is not None:
            self._channels[guild_id] = voice_client.channel
        queue = self._queues.setdefault(guild_id, asyncio.Queue())
        await queue.put(data)
        task = self._tasks.get(guild_id)
        if task is None or task.done():
            self._tasks[guild_id] = asyncio.create_task(self._run(guild_id))

    async def _run(self, guild_id: int) -> None:
        queue = self._queues[guild_id]
        idle_timeout = get_config().voice_idle_timeout
        try:
            while True:
                vc = self._clients.get(guild_id)
                if vc is None or not vc.is_connected():
                    channel = self._channels.get(guild_id)
                    if channel is None or channel.guild is None:
                        break
                    await asyncio.sleep(1)
                    try:
                        vc = await self.ensure_connected(channel.guild, channel)
                        self._clients[guild_id] = vc
                    except Exception:
                        logger.warning(
                            "Could not reconnect voice connection in guild %s", guild_id
                        )
                        break
                if queue.empty():
                    if await self._maybe_disconnect(vc):
                        break
                    try:
                        data = await asyncio.wait_for(
                            queue.get(), timeout=idle_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.info(
                            "Leaving voice channel in guild %s after %.0fs idle",
                            guild_id, idle_timeout,
                        )
                        try:
                            await vc.disconnect()
                        except Exception:
                            pass
                        break
                else:
                    data = await queue.get()
                try:
                    await self._play(vc, data)
                except Exception:
                    logger.exception("Playback failed in guild %s", guild_id)
        finally:
            while not queue.empty():
                item = queue.get_nowait()
                if isinstance(item, StreamSource):
                    item.cancel()

    @classmethod
    async def _play(
        cls, vc: discord.VoiceClient, data: bytes | StreamSource
    ) -> None:
        if isinstance(data, StreamSource):
            await cls._play_stream(vc, data)
        else:
            await cls._play_bytes(vc, data)

    @staticmethod
    async def _play_source(
        vc: discord.VoiceClient,
        source: discord.AudioSource,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        finished = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _after(err: Exception | None) -> None:
            if err:
                logger.warning("FFmpeg playback error: %s", err)
            loop.call_soon_threadsafe(finished.set)

        try:
            vc.play(source, after=_after)
        except Exception as e:
            if on_done is not None:
                on_done()
            raise PlaybackError("Voice client is not playing. Try again.") from e
        try:
            await finished.wait()
        except asyncio.CancelledError:
            try:
                vc.stop()
            except Exception:
                pass
            raise
        finally:
            if on_done is not None:
                on_done()

    @staticmethod
    async def _play_bytes(vc: discord.VoiceClient, data: bytes) -> None:
        try:
            source = discord.FFmpegPCMAudio(BytesIO(data), pipe=True, **FFMPEG_OPTIONS)
        except Exception as e:
            raise PlaybackError(
                "Could not start FFmpeg. Make sure FFmpeg is installed and on PATH."
            ) from e
        await PlaybackManager._play_source(vc, source, on_done=source.cleanup)

    @classmethod
    async def _play_stream(cls, vc: discord.VoiceClient, source: StreamSource) -> None:
        source.start()
        proc = cls._spawn_ffmpeg()
        audio = discord.PCMAudio(proc.stdout)
        feed = asyncio.create_task(cls._feed_proc(proc, source))
        try:
            await cls._play_source(vc, audio)
        finally:
            feed.cancel()
            source.cancel()
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.stdout.close()
            except Exception:
                pass

    @staticmethod
    def _spawn_ffmpeg() -> subprocess.Popen:
        try:
            return subprocess.Popen(
                _FFMPEG_ARGS,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError:
            raise PlaybackError(
                "Could not start FFmpeg. Make sure FFmpeg is installed and on PATH."
            ) from None

    @staticmethod
    async def _feed_proc(proc: subprocess.Popen, source: StreamSource) -> None:
        try:
            async for chunk in source:
                await asyncio.to_thread(proc.stdin.write, chunk)
        except Exception as e:
            logger.warning("Audio stream feed stopped: %s", e)
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    @staticmethod
    async def _maybe_disconnect(vc: discord.VoiceClient) -> bool:
        channel = vc.channel
        if channel is None:
            return False
        if not any(member_id != vc.user.id for member_id in channel.voice_states):
            try:
                await vc.disconnect()
            except Exception:
                pass
            return True
        return False

    def stop(self, guild_id: int) -> None:
        """Stop current audio and clear the queue for the given guild."""
        queue = self._queues.get(guild_id)
        if queue is not None:
            while not queue.empty():
                item = queue.get_nowait()
                if isinstance(item, StreamSource):
                    item.cancel()
        vc = self._clients.get(guild_id)
        if vc is not None and vc.is_playing():
            vc.stop()

    def skip(self, guild_id: int) -> None:
        """Skip currently playing audio for the guild."""
        vc = self._clients.get(guild_id)
        if vc is not None and vc.is_playing():
            vc.stop()

    def cleanup(self, guild_id: int) -> None:
        task = self._tasks.pop(guild_id, None)
        if task is not None and not task.done():
            task.cancel()
        queue = self._queues.pop(guild_id, None)
        if queue is not None:
            while not queue.empty():
                item = queue.get_nowait()
                if isinstance(item, StreamSource):
                    item.cancel()
        self._clients.pop(guild_id, None)
        self._channels.pop(guild_id, None)
        self._connect_locks.pop(guild_id, None)
        self._stay.discard(guild_id)


playback = PlaybackManager()

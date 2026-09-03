from __future__ import annotations

import asyncio

from fishaudio import AsyncFishAudio

from src.config import get_config

_client: AsyncFishAudio | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def create_client() -> AsyncFishAudio:
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        _client = AsyncFishAudio(api_key=get_config().fish_api_key)
        _client_loop = loop
    return _client

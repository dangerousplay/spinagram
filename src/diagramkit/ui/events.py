"""Fan-out of UI events to every connected browser over server-sent events."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

KEEPALIVE = 15.0


class EventBus:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: dict) -> None:
        """Safe from any thread (fetch jobs run in a pool)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for q in list(self._queues):
            loop.call_soon_threadsafe(q.put_nowait, event)

    async def stream(self, keepalive: float = KEEPALIVE) -> AsyncIterator[str]:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        try:
            yield _sse({"type": "hello"})
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), keepalive)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(event)
        finally:
            self._queues.discard(q)

    @property
    def clients(self) -> int:
        return len(self._queues)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

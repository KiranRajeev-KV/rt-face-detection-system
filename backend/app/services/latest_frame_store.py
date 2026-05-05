import asyncio
from uuid import UUID


class LatestFrameStore:
    def __init__(self) -> None:
        self._frames: dict[UUID, bytes] = {}
        self._lock = asyncio.Lock()

    async def set(self, session_id: UUID, frame: bytes) -> None:
        async with self._lock:
            self._frames[session_id] = frame

    async def get(self, session_id: UUID) -> bytes | None:
        async with self._lock:
            return self._frames.get(session_id)

    async def clear(self) -> None:
        async with self._lock:
            self._frames.clear()

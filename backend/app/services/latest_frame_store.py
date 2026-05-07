import asyncio
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class LatestFrame:
    bytes_data: bytes
    version: int


class LatestFrameStore:
    def __init__(self) -> None:
        self._frames: dict[UUID, LatestFrame] = {}
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)

    async def set(self, session_id: UUID, frame: bytes) -> None:
        async with self._condition:
            current = self._frames.get(session_id)
            next_version = 1 if current is None else current.version + 1
            self._frames[session_id] = LatestFrame(bytes_data=frame, version=next_version)
            self._condition.notify_all()

    async def get(self, session_id: UUID) -> LatestFrame | None:
        async with self._lock:
            return self._frames.get(session_id)

    async def wait_for_new_frame(
        self,
        session_id: UUID,
        last_seen_version: int,
        timeout: float,
    ) -> LatestFrame | None:
        async with self._condition:
            current = self._frames.get(session_id)
            if current is not None and current.version > last_seen_version:
                return current

            try:
                await asyncio.wait_for(
                    self._condition.wait_for(
                        lambda: (
                            (latest := self._frames.get(session_id)) is not None
                            and latest.version > last_seen_version
                        )
                    ),
                    timeout=timeout,
                )
            except TimeoutError:
                return None
            return self._frames.get(session_id)

    async def clear_session(self, session_id: UUID) -> None:
        async with self._condition:
            self._frames.pop(session_id, None)
            self._condition.notify_all()

    async def clear(self) -> None:
        async with self._condition:
            self._frames.clear()
            self._condition.notify_all()

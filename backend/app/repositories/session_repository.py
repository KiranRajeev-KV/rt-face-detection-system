from uuid import UUID

from app.db.models import VideoSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, session_id: UUID) -> VideoSession | None:
        statement = select(VideoSession).where(VideoSession.id == session_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_or_create(self, session_id: UUID, source: str = "browser-webcam") -> VideoSession:
        existing = await self.get(session_id)
        if existing is not None:
            existing.status = "active"
            return existing
        session = VideoSession(id=session_id, source=source, status="active")
        self.session.add(session)
        await self.session.flush()
        return session

from uuid import UUID

from app.db.models import RoiDetection
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


class RoiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: UUID,
        frame_id: int,
        timestamp_ms: int,
        x: int,
        y: int,
        width: int,
        height: int,
        confidence: float | None,
        frame_width: int,
        frame_height: int,
        detector_name: str,
    ) -> RoiDetection:
        item = RoiDetection(
            session_id=session_id,
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            x=x,
            y=y,
            width=width,
            height=height,
            confidence=confidence,
            frame_width=frame_width,
            frame_height=frame_height,
            detector_name=detector_name,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_by_session(self, *, session_id: UUID, limit: int) -> list[RoiDetection]:
        result = await self.session.execute(
            select(RoiDetection)
            .where(RoiDetection.session_id == session_id)
            .order_by(desc(RoiDetection.frame_id), desc(RoiDetection.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


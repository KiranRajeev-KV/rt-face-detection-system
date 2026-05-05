from typing import Annotated
from uuid import UUID

from app.core.errors import FrameNotReadyError, SessionNotFoundError
from app.repositories.session_repository import SessionRepository
from app.services.dependencies import get_db_session, get_latest_frame_store
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1", tags=["video"])


@router.get("/video/stream")
async def get_latest_frame(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    session_repo = SessionRepository(db)
    session = await session_repo.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    latest_frame = await get_latest_frame_store().get(session_id)
    if latest_frame is None:
        raise FrameNotReadyError(session_id)
    return Response(content=latest_frame, media_type="image/jpeg")

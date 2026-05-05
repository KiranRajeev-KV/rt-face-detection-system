from typing import Annotated
from uuid import UUID

from app.repositories.roi_repository import RoiRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.roi import RoiListResponse
from app.services.dependencies import get_db_session
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1", tags=["roi"])


@router.get("/roi", response_model=RoiListResponse)
async def get_roi_history(
    session_id: Annotated[UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> RoiListResponse:
    session_repo = SessionRepository(db)
    roi_repo = RoiRepository(db)
    session = await session_repo.get(session_id)
    if session is None:
        from app.core.errors import SessionNotFoundError

        raise SessionNotFoundError(session_id)
    items = await roi_repo.list_by_session(session_id=session_id, limit=limit)
    return RoiListResponse(
        session_id=session_id,
        count=len(items),
        items=[item.to_read_model() for item in items],
    )

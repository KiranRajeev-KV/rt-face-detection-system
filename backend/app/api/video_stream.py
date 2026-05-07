import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from app.core.errors import SessionNotFoundError
from app.repositories.session_repository import SessionRepository
from app.services.dependencies import get_db_session, get_latest_frame_store
from app.services.latest_frame_store import LatestFrameStore
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1", tags=["video"])


@router.get("/video/stream")
async def stream_video(
    request: Request,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    session_repo = SessionRepository(db)
    session = await session_repo.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    latest_frame_store = get_latest_frame_store()
    return StreamingResponse(
        _generate_mjpeg_stream(
            request=request,
            session_id=session_id,
            latest_frame_store=latest_frame_store,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_mjpeg_stream(
    *,
    request: Request,
    session_id: UUID,
    latest_frame_store: LatestFrameStore,
    wait_timeout_seconds: float = 1.0,
) -> AsyncIterator[bytes]:
    last_seen_version = 0
    try:
        while True:
            if await request.is_disconnected():
                break

            next_frame = await latest_frame_store.wait_for_new_frame(
                session_id=session_id,
                last_seen_version=last_seen_version,
                timeout=wait_timeout_seconds,
            )
            if next_frame is None:
                continue

            last_seen_version = next_frame.version
            yield _format_mjpeg_chunk(next_frame.bytes_data)
    except asyncio.CancelledError:
        return


def _format_mjpeg_chunk(frame_bytes: bytes) -> bytes:
    headers = (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: "
        + str(len(frame_bytes)).encode("ascii")
        + b"\r\n\r\n"
    )
    return headers + frame_bytes + b"\r\n"

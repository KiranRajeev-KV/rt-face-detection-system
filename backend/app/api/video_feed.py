import logging
from typing import Annotated
from uuid import UUID

from app.core.errors import FramePayloadError, SessionIdentifierError
from app.db.session import session_manager
from app.services.dependencies import app_state
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from starlette.types import Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["video"])


@router.websocket("/video/feed")
async def video_feed(
    websocket: WebSocket,
    session_id: Annotated[str, Query()],
) -> None:
    try:
        parsed_session_id = UUID(session_id)
    except ValueError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="invalid session_id")
        raise SessionIdentifierError(session_id) from exc

    await websocket.accept()
    processor = app_state.get_frame_processor()
    async with session_manager.session() as db_session:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("websocket disconnected", extra={"session_id": str(parsed_session_id)})
                break
            if message.get("type") == "websocket.disconnect":
                logger.info("websocket disconnected", extra={"session_id": str(parsed_session_id)})
                break

            try:
                payload, is_binary = _extract_message_payload(message)
                result = await processor.process_message(
                    db_session=db_session,
                    session_id=parsed_session_id,
                    payload=payload,
                    is_binary=is_binary,
                )
                await websocket.send_json(result.model_dump(mode="json"))
            except FramePayloadError as exc:
                logger.warning(
                    "frame rejected",
                    extra={"session_id": str(parsed_session_id), "error": exc.message},
                )
                await websocket.send_json(
                    {
                        "type": "frame_error",
                        "session_id": str(parsed_session_id),
                        "frame_id": exc.frame_id,
                        "detail": exc.message,
                    }
                )
            except Exception:  # pragma: no cover
                logger.exception(
                    "unexpected frame processing failure",
                    extra={"session_id": str(parsed_session_id)},
                )
                await websocket.send_json(
                    {
                        "type": "frame_error",
                        "session_id": str(parsed_session_id),
                        "frame_id": None,
                        "detail": "internal processing error",
                    }
                )


def _extract_message_payload(message: Message) -> tuple[bytes | str, bool]:
    if "bytes" in message and message["bytes"] is not None:
        return message["bytes"], True
    if "text" in message and message["text"] is not None:
        return message["text"], False
    raise FramePayloadError("frame payload missing")

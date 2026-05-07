import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.video_stream import _format_mjpeg_chunk, _generate_mjpeg_stream, stream_video
from app.services.latest_frame_store import LatestFrameStore
from app.tests.test_frame_validation import build_jpeg_bytes
from fastapi.testclient import TestClient


class StaticRequest:
    async def is_disconnected(self) -> bool:
        return False


def test_stream_missing_session_returns_404(test_app):
    app, _detector = test_app
    session_id = uuid4()

    with patch(
        "app.api.video_stream.SessionRepository.get",
        new=AsyncMock(return_value=None),
    ):
        with TestClient(app) as client:
            response = client.get(f"/api/v1/video/stream?session_id={session_id}")

    assert response.status_code == 404
    assert response.json()["error"] == "session_not_found"


def test_stream_existing_session_returns_multipart_content_type(test_app):
    session_id = uuid4()

    async def run_test() -> None:
        request = StaticRequest()
        with patch(
            "app.api.video_stream.SessionRepository.get",
            new=AsyncMock(return_value=object()),
        ):
            response = await stream_video(request=request, session_id=session_id, db=object())

        assert response.media_type == "multipart/x-mixed-replace; boundary=frame"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"

    asyncio.run(run_test())


def test_mjpeg_chunk_contains_valid_multipart_jpeg_frame():
    frame_bytes = build_jpeg_bytes()

    chunk = _format_mjpeg_chunk(frame_bytes)

    assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ")
    assert f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode("ascii") in chunk
    assert chunk.endswith(frame_bytes + b"\r\n")


def test_mjpeg_generator_emits_first_available_frame():
    async def run_test() -> None:
        store = LatestFrameStore()
        session_id = uuid4()
        frame_bytes = build_jpeg_bytes()
        await store.set(session_id, frame_bytes)

        generator = _generate_mjpeg_stream(
            request=StaticRequest(),
            session_id=session_id,
            latest_frame_store=store,
            wait_timeout_seconds=0.01,
        )
        chunk = await asyncio.wait_for(anext(generator), timeout=0.1)
        await generator.aclose()

        assert chunk == _format_mjpeg_chunk(frame_bytes)

    asyncio.run(run_test())

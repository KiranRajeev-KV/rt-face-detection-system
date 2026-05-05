from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.db.models import RoiDetection, VideoSession
from app.db.session import session_manager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.asyncio
async def test_roi_api_returns_latest_first(test_app):
    app, _detector = test_app
    session_id = uuid4()
    session_factory = async_sessionmaker(session_manager.engine, expire_on_commit=False)
    async with session_factory() as db_session:
        db_session.add(VideoSession(id=session_id, source="test", status="active"))
        db_session.add_all(
            [
                RoiDetection(
                    session_id=session_id,
                    frame_id=1,
                    timestamp_ms=100,
                    x=10,
                    y=10,
                    width=30,
                    height=30,
                    confidence=0.8,
                    frame_width=100,
                    frame_height=100,
                    detector_name="fake.detector",
                    created_at=datetime.now(UTC),
                ),
                RoiDetection(
                    session_id=session_id,
                    frame_id=2,
                    timestamp_ms=200,
                    x=12,
                    y=12,
                    width=32,
                    height=32,
                    confidence=0.9,
                    frame_width=100,
                    frame_height=100,
                    detector_name="fake.detector",
                    created_at=datetime.now(UTC),
                ),
            ]
        )
        await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/roi?session_id={session_id}&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [item["frame_id"] for item in body["items"]] == [2, 1]


import asyncio
from collections.abc import Iterator

import numpy as np
import pytest
from app.core.config import Settings
from app.db.models import Base
from app.db.session import session_manager
from app.main import create_app
from app.services.dependencies import app_state
from app.services.face_detector import DetectorOutcome, FaceDetector
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


class FakeDetector(FaceDetector):
    detector_name = "fake.detector"

    def __init__(self) -> None:
        self.next_result = DetectorOutcome(detections=[], detector_name=self.detector_name)

    def detect(self, rgb_image: np.ndarray, timestamp_ms: int) -> DetectorOutcome:
        return self.next_result


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        detector_model_path="/tmp/fake.task",
        cors_origins=["http://localhost:5173"],
    )


@pytest.fixture()
def test_app(test_settings: Settings) -> Iterator[tuple[object, FakeDetector]]:
    async def setup_app() -> tuple[object, FakeDetector]:
        engine = create_async_engine(
            test_settings.database_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        session_manager.engine = engine
        session_manager.session_factory = session_factory
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        detector = FakeDetector()
        app_state.override_for_tests(settings=test_settings, detector=detector)
        await app_state.get_latest_frame_store().clear()
        app = create_app(test_settings)
        return app, detector

    async def teardown_app() -> None:
        engine = session_manager.engine
        if engine is not None:
            await engine.dispose()
        session_manager.engine = None
        session_manager.session_factory = None

    app, detector = asyncio.run(setup_app())
    yield app, detector
    asyncio.run(teardown_app())

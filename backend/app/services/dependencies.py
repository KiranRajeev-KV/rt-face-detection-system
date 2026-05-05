from collections.abc import AsyncGenerator

from app.core.config import Settings, get_settings
from app.db.session import session_manager
from app.services.face_detector import FaceDetector, MediaPipeFaceDetector
from app.services.frame_processor import FrameProcessor
from app.services.latest_frame_store import LatestFrameStore
from sqlalchemy.ext.asyncio import AsyncSession


class AppState:
    def __init__(self) -> None:
        self._settings: Settings | None = None
        self._latest_frame_store = LatestFrameStore()
        self._detector: FaceDetector | None = None
        self._frame_processor: FrameProcessor | None = None

    def configure(self, settings: Settings) -> None:
        self._settings = settings
        if self._detector is None:
            self._detector = MediaPipeFaceDetector(
                model_path=settings.detector_model_path,
                min_confidence=settings.detector_min_confidence,
            )
        if self._frame_processor is None:
            self._frame_processor = FrameProcessor(
                settings=settings,
                detector=self._detector,
                latest_frame_store=self._latest_frame_store,
            )

    def override_for_tests(
        self,
        *,
        settings: Settings,
        detector: FaceDetector | None = None,
    ) -> None:
        self._settings = settings
        if detector is not None:
            self._detector = detector
        elif self._detector is None:
            self._detector = MediaPipeFaceDetector(
                model_path=settings.detector_model_path,
                min_confidence=settings.detector_min_confidence,
            )
        self._frame_processor = FrameProcessor(
            settings=settings,
            detector=self._detector,
            latest_frame_store=self._latest_frame_store,
        )

    def get_frame_processor(self) -> FrameProcessor:
        if self._frame_processor is None:
            self.configure(get_settings())
        assert self._frame_processor is not None
        return self._frame_processor

    def get_latest_frame_store(self) -> LatestFrameStore:
        return self._latest_frame_store


app_state = AppState()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_manager.session() as session:
        yield session


def get_latest_frame_store() -> LatestFrameStore:
    return app_state.get_latest_frame_store()

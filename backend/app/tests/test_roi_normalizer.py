from app.core.config import Settings
from app.services.face_detector import DetectorOutcome, FaceDetector
from app.services.frame_processor import FrameProcessor
from app.services.latest_frame_store import LatestFrameStore
from app.services.roi_normalizer import RawDetection, normalize_roi


class StubDetector(FaceDetector):
    detector_name = "stub.detector"

    def detect(self, rgb_image, timestamp_ms: int) -> DetectorOutcome:
        return DetectorOutcome(detections=[], detector_name=self.detector_name)


def test_roi_normalizer_clips_to_frame() -> None:
    normalized = normalize_roi(
        RawDetection(x=-5, y=10, width=140, height=100, confidence=0.75),
        frame_width=120,
        frame_height=80,
    )
    assert normalized is not None
    assert normalized.x == 0
    assert normalized.y == 10
    assert normalized.width == 120
    assert normalized.height == 70


def test_roi_normalizer_rejects_zero_area() -> None:
    normalized = normalize_roi(
        RawDetection(x=20, y=20, width=0.1, height=0.1, confidence=0.5),
        frame_width=100,
        frame_height=100,
    )
    assert normalized is None


def test_pick_roi_returns_none_when_no_face() -> None:
    processor = FrameProcessor(
        settings=Settings(detector_model_path="/tmp/fake.task"),
        detector=StubDetector(),
        latest_frame_store=LatestFrameStore(),
    )
    roi, warning = processor._pick_roi(
        DetectorOutcome(detections=[], detector_name="stub.detector"),
        frame_width=100,
        frame_height=100,
    )
    assert roi is None
    assert warning is None


def test_pick_roi_selects_highest_confidence() -> None:
    processor = FrameProcessor(
        settings=Settings(detector_model_path="/tmp/fake.task"),
        detector=StubDetector(),
        latest_frame_store=LatestFrameStore(),
    )
    roi, warning = processor._pick_roi(
        DetectorOutcome(
            detections=[
                RawDetection(x=10, y=10, width=20, height=20, confidence=0.6),
                RawDetection(x=40, y=20, width=10, height=10, confidence=0.9),
            ],
            detector_name="stub.detector",
        ),
        frame_width=100,
        frame_height=100,
    )
    assert roi is not None
    assert roi.x == 40
    assert roi.y == 20
    assert roi.width == 10
    assert roi.height == 10
    assert warning == "multiple faces detected; highest-confidence face selected"

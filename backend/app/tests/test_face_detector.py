from types import SimpleNamespace

import numpy as np
from app.services.face_detector import MediaPipeFaceDetector


class FakeDetector:
    def __init__(self) -> None:
        self.timestamps: list[int] = []

    def detect_for_video(self, _image, timestamp_ms: int):
        self.timestamps.append(timestamp_ms)
        return SimpleNamespace(detections=[])


def test_detector_enforces_monotonic_timestamps(monkeypatch) -> None:
    fake_detector = FakeDetector()
    detector = MediaPipeFaceDetector(model_path="/tmp/model.tflite", min_confidence=0.5)
    detector._detector = fake_detector

    monkeypatch.setattr(
        "app.services.face_detector.mp.Image",
        lambda image_format, data: SimpleNamespace(image_format=image_format, data=data),
    )

    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    detector.detect(frame, 1000)
    detector.detect(frame, 1000)
    detector.detect(frame, 999)

    assert fake_detector.timestamps == [1000, 1001, 1002]

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import mediapipe as mp
import numpy as np
from app.core.errors import DetectorInitializationError
from app.services.roi_normalizer import RawDetection


@dataclass(slots=True)
class DetectorOutcome:
    detections: list[RawDetection]
    detector_name: str


class FaceDetector:
    detector_name = "face-detector"

    def detect(self, rgb_image: np.ndarray, timestamp_ms: int) -> DetectorOutcome:
        raise NotImplementedError


class MediaPipeFaceDetector(FaceDetector):
    detector_name = "mediapipe.tasks.face_detector"

    def __init__(self, *, model_path: str, min_confidence: float) -> None:
        self._model_path = model_path
        self._min_confidence = min_confidence
        self._detector = None
        self._lock = Lock()
        self._last_timestamp_ms: int | None = None

    def _ensure_detector(self):
        if self._detector is not None:
            return self._detector
        with self._lock:
            if self._detector is not None:
                return self._detector
            try:
                base_options = mp.tasks.BaseOptions(model_asset_path=self._model_path)
                options = mp.tasks.vision.FaceDetectorOptions(
                    base_options=base_options,
                    running_mode=mp.tasks.vision.RunningMode.VIDEO,
                    min_detection_confidence=self._min_confidence,
                )
                self._detector = mp.tasks.vision.FaceDetector.create_from_options(options)
                return self._detector
            except Exception as exc:  # pragma: no cover
                raise DetectorInitializationError(str(exc)) from exc

    def detect(self, rgb_image: np.ndarray, timestamp_ms: int) -> DetectorOutcome:
        detector = self._ensure_detector()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        with self._lock:
            monotonic_timestamp_ms = timestamp_ms
            if (
                self._last_timestamp_ms is not None
                and monotonic_timestamp_ms <= self._last_timestamp_ms
            ):
                monotonic_timestamp_ms = self._last_timestamp_ms + 1
            result = detector.detect_for_video(mp_image, monotonic_timestamp_ms)
            self._last_timestamp_ms = monotonic_timestamp_ms
        detections: list[RawDetection] = []
        for detection in result.detections:
            bbox = detection.bounding_box
            confidence = detection.categories[0].score if detection.categories else None
            detections.append(
                RawDetection(
                    x=bbox.origin_x,
                    y=bbox.origin_y,
                    width=bbox.width,
                    height=bbox.height,
                    confidence=confidence,
                )
            )
        return DetectorOutcome(detections=detections, detector_name=self.detector_name)

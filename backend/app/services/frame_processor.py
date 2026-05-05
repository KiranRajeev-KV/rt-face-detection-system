from __future__ import annotations

import base64
import json
import time
from io import BytesIO
from uuid import UUID

import numpy as np
from app.core.config import Settings
from app.core.errors import FramePayloadError
from app.repositories.roi_repository import RoiRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.roi import RoiBounds
from app.schemas.video import FrameMetadata, FrameResult
from app.services.face_detector import DetectorOutcome, FaceDetector
from app.services.latest_frame_store import LatestFrameStore
from app.services.roi_drawer import draw_roi
from app.services.roi_normalizer import RawDetection, normalize_roi
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession


class FrameProcessor:
    def __init__(
        self,
        *,
        settings: Settings,
        detector: FaceDetector,
        latest_frame_store: LatestFrameStore,
    ) -> None:
        self.settings = settings
        self.detector = detector
        self.latest_frame_store = latest_frame_store

    async def process_message(
        self,
        *,
        db_session: AsyncSession,
        session_id: UUID,
        payload: bytes | str,
        is_binary: bool,
    ) -> FrameResult:
        metadata, image_bytes = self._parse_transport(payload=payload, is_binary=is_binary)
        started_at = time.perf_counter()
        image = self._decode_image(image_bytes)
        frame_width, frame_height = image.size
        rgb_array = np.array(image)
        detector_result = self.detector.detect(rgb_array, metadata.timestamp_ms)
        roi, warning = self._pick_roi(detector_result, frame_width, frame_height)

        session_repo = SessionRepository(db_session)
        roi_repo = RoiRepository(db_session)
        await session_repo.get_or_create(session_id)

        if roi is not None:
            await roi_repo.create(
                session_id=session_id,
                frame_id=metadata.frame_id,
                timestamp_ms=metadata.timestamp_ms,
                x=int(roi.x),
                y=int(roi.y),
                width=int(roi.width),
                height=int(roi.height),
                confidence=roi.confidence,
                frame_width=frame_width,
                frame_height=frame_height,
                detector_name=detector_result.detector_name,
            )

        annotated_bytes = draw_roi(image, roi)
        await self.latest_frame_store.set(session_id, annotated_bytes)
        await db_session.commit()

        processing_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return FrameResult(
            session_id=session_id,
            frame_id=metadata.frame_id,
            has_face=roi is not None,
            roi=(
                RoiBounds(
                    x=int(roi.x),
                    y=int(roi.y),
                    width=int(roi.width),
                    height=int(roi.height),
                    confidence=roi.confidence,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                if roi is not None
                else None
            ),
            processing_ms=processing_ms,
            annotated_image_base64=base64.b64encode(annotated_bytes).decode("ascii"),
            warning=warning,
        )

    def _parse_transport(
        self,
        *,
        payload: bytes | str,
        is_binary: bool,
    ) -> tuple[FrameMetadata, bytes]:
        if is_binary:
            if not isinstance(payload, bytes):
                raise FramePayloadError("binary frame payload expected")
            return self._parse_binary_payload(payload)
        if not isinstance(payload, str):
            raise FramePayloadError("text frame payload expected")
        return self._parse_json_payload(payload)

    def _parse_binary_payload(self, payload: bytes) -> tuple[FrameMetadata, bytes]:
        if (
            len(payload)
            > self.settings.max_frame_size_bytes + self.settings.max_metadata_size_bytes + 4
        ):
            raise FramePayloadError("frame payload exceeds configured size limit")
        if len(payload) < 5:
            raise FramePayloadError("binary payload too small")
        metadata_size = int.from_bytes(payload[:4], byteorder="big")
        if metadata_size <= 0 or metadata_size > self.settings.max_metadata_size_bytes:
            raise FramePayloadError("binary metadata size is invalid")
        metadata_end = 4 + metadata_size
        metadata = self._parse_metadata_bytes(payload[4:metadata_end])
        image_bytes = payload[metadata_end:]
        if not image_bytes:
            raise FramePayloadError(
                "binary payload missing image bytes",
                frame_id=metadata.frame_id,
            )
        self._validate_content_type(metadata)
        return metadata, image_bytes

    def _parse_json_payload(self, payload: str) -> tuple[FrameMetadata, bytes]:
        try:
            body = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FramePayloadError("text payload is not valid JSON") from exc
        if "image_base64" not in body:
            raise FramePayloadError("text payload missing image_base64")
        metadata = FrameMetadata.model_validate(body)
        try:
            image_bytes = base64.b64decode(body["image_base64"], validate=True)
        except Exception as exc:
            raise FramePayloadError(
                "image_base64 is not valid base64",
                frame_id=metadata.frame_id,
            ) from exc
        self._validate_content_type(metadata)
        return metadata, image_bytes

    def _parse_metadata_bytes(self, raw_metadata: bytes) -> FrameMetadata:
        try:
            decoded = raw_metadata.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FramePayloadError("binary metadata is not valid UTF-8") from exc
        try:
            body = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise FramePayloadError("binary metadata is not valid JSON") from exc
        return FrameMetadata.model_validate(body)

    def _decode_image(self, image_bytes: bytes) -> Image.Image:
        if len(image_bytes) > self.settings.max_frame_size_bytes:
            raise FramePayloadError("image payload exceeds configured size limit")
        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
        except UnidentifiedImageError as exc:
            raise FramePayloadError("image payload could not be decoded") from exc
        except OSError as exc:
            raise FramePayloadError("image payload could not be decoded") from exc
        if (
            image.width > self.settings.max_image_width
            or image.height > self.settings.max_image_height
        ):
            raise FramePayloadError("image dimensions exceed configured limits")
        if image.mode != "RGB":
            image = image.convert("RGB")
        return image

    def _validate_content_type(self, metadata: FrameMetadata) -> None:
        if metadata.content_type != "image/jpeg":
            raise FramePayloadError(
                "unsupported content_type; only image/jpeg is accepted",
                frame_id=metadata.frame_id,
            )

    def _pick_roi(
        self,
        detector_result: DetectorOutcome,
        frame_width: int,
        frame_height: int,
    ) -> tuple[RawDetection | None, str | None]:
        if not detector_result.detections:
            return None, None
        sorted_detections = sorted(
            detector_result.detections,
            key=lambda item: item.confidence if item.confidence is not None else -1.0,
            reverse=True,
        )
        normalized = normalize_roi(
            sorted_detections[0],
            frame_width=frame_width,
            frame_height=frame_height,
        )
        warning = None
        if len(sorted_detections) > 1:
            warning = "multiple faces detected; highest-confidence face selected"
        return normalized, warning

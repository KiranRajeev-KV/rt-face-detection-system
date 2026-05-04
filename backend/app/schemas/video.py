from uuid import UUID

from app.schemas.roi import RoiBounds
from pydantic import BaseModel, Field


class FrameMetadata(BaseModel):
    frame_id: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    content_type: str = "image/jpeg"


class FrameResult(BaseModel):
    type: str = "frame_result"
    session_id: UUID
    frame_id: int
    has_face: bool
    roi: RoiBounds | None
    processing_ms: float
    annotated_image_base64: str
    warning: str | None = None


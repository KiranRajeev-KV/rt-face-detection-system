from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RoiBounds(BaseModel):
    x: int
    y: int
    width: int
    height: int
    confidence: float | None
    frame_width: int
    frame_height: int


class RoiItem(RoiBounds):
    frame_id: int
    timestamp_ms: int
    detector_name: str
    created_at: datetime


class RoiListResponse(BaseModel):
    session_id: UUID
    count: int
    items: list[RoiItem]


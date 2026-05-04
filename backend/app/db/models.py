from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.schemas.roi import RoiItem
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class VideoSession(Base):
    __tablename__ = "video_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(Text, default="browser-webcam")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    detections: Mapped[list[RoiDetection]] = relationship(back_populates="session")


class RoiDetection(Base):
    __tablename__ = "roi_detections"
    __table_args__ = (
        Index("ix_roi_detections_session_frame_desc", "session_id", "frame_id"),
        Index("ix_roi_detections_session_created_desc", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("video_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    frame_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_width: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_height: Mapped[int] = mapped_column(Integer, nullable=False)
    detector_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[VideoSession] = relationship(back_populates="detections")

    def to_read_model(self) -> RoiItem:
        return RoiItem(
            frame_id=self.frame_id,
            timestamp_ms=self.timestamp_ms,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            confidence=self.confidence,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            detector_name=self.detector_name,
            created_at=self.created_at,
        )

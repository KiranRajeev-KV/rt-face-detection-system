from dataclasses import dataclass


@dataclass(slots=True)
class RawDetection:
    x: float
    y: float
    width: float
    height: float
    confidence: float | None


def normalize_roi(
    detection: RawDetection,
    frame_width: int,
    frame_height: int,
) -> RawDetection | None:
    x1 = max(0, min(frame_width, int(round(detection.x))))
    y1 = max(0, min(frame_height, int(round(detection.y))))
    x2 = max(0, min(frame_width, int(round(detection.x + detection.width))))
    y2 = max(0, min(frame_height, int(round(detection.y + detection.height))))

    width = max(0, x2 - x1)
    height = max(0, y2 - y1)
    if width == 0 or height == 0:
        return None
    return RawDetection(
        x=x1,
        y=y1,
        width=width,
        height=height,
        confidence=detection.confidence,
    )

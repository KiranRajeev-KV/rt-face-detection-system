from io import BytesIO

from app.services.roi_normalizer import RawDetection
from PIL import Image, ImageDraw


def draw_roi(image: Image.Image, roi: RawDetection | None) -> bytes:
    annotated = image.copy()
    if roi is not None:
        drawer = ImageDraw.Draw(annotated)
        drawer.rectangle(
            [roi.x, roi.y, roi.x + roi.width, roi.y + roi.height],
            outline=(0, 255, 0),
            width=4,
        )
    buffer = BytesIO()
    annotated.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()

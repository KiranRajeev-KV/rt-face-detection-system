import json
import struct
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image


def build_binary_payload(metadata: dict, image_bytes: bytes) -> bytes:
    metadata_json = json.dumps(metadata).encode("utf-8")
    return struct.pack(">I", len(metadata_json)) + metadata_json + image_bytes


def build_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (120, 80), color=(24, 24, 24))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_invalid_base64_payload_returns_frame_error(test_app):
    app, _detector = test_app
    session_id = uuid4()
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/video/feed?session_id={session_id}") as websocket:
            websocket.send_text(
                json.dumps(
                    {
                        "frame_id": 1,
                        "timestamp_ms": 1,
                        "content_type": "image/jpeg",
                        "image_base64": "***",
                    }
                )
            )
            message = websocket.receive_json()
    assert message["type"] == "frame_error"
    assert message["detail"] == "image_base64 is not valid base64"


def test_invalid_binary_payload_returns_frame_error(test_app):
    app, _detector = test_app
    session_id = uuid4()
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/video/feed?session_id={session_id}") as websocket:
            websocket.send_bytes(b"bad")
            message = websocket.receive_json()
    assert message["type"] == "frame_error"
    assert message["detail"] == "binary payload too small"


def test_valid_frame_without_face_returns_frame_result(test_app):
    app, _detector = test_app
    session_id = uuid4()
    image_bytes = build_jpeg_bytes()
    payload = build_binary_payload(
        {"frame_id": 2, "timestamp_ms": 1234, "content_type": "image/jpeg"},
        image_bytes,
    )
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/video/feed?session_id={session_id}") as websocket:
            websocket.send_bytes(payload)
            message = websocket.receive_json()
    assert message["type"] == "frame_result"
    assert message["has_face"] is False
    assert message["roi"] is None
    assert message["warning"] is None
    assert "annotated_image_base64" not in message

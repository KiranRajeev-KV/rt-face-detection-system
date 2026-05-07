# API Contract

## Base URL Assumptions

- Local backend base URL: `http://localhost:8000`
- Frontend defaults (`frontend/.env.example`):
  - `VITE_API_BASE_URL=http://localhost:8000`
  - `VITE_WS_BASE_URL=ws://localhost:8000`

## Endpoint Summary

| Method | Path | Purpose |
|---|---|---|
| `WS` | `/api/v1/video/feed` | Receive webcam frames for processing |
| `GET` | `/api/v1/video/stream` | Serve processed MJPEG stream |
| `GET` | `/api/v1/roi` | Serve ROI history |

Only these three are core application endpoints.

## Common Concepts

- `session_id`:
  - UUID identifying a video session.
- `frame_id`:
  - Non-negative integer from sender.
- `timestamp_ms`:
  - Non-negative integer timestamp (milliseconds).
- ROI coordinate system:
  - Pixel coordinates relative to source frame (`x`, `y`, `width`, `height`) with frame bounds included.
- Accepted frame image format:
  - JPEG (`image/jpeg`).

## WebSocket `/api/v1/video/feed`

### Purpose

Ingestion endpoint for frame uploads and per-frame processing metadata responses.

### Query Parameters

- `session_id` (required, UUID string)

### Connection Behavior

- If `session_id` is invalid UUID:
  - server closes WebSocket with code `1008` and reason `invalid session_id`.
- On valid connect:
  - session is created/activated before first frame is received.

### Accepted Payload Formats

1. Binary payload (primary path)
   - Format:
     - first 4 bytes: metadata length (big-endian uint32)
     - next N bytes: UTF-8 JSON metadata
     - remaining bytes: JPEG image
2. Text payload (supported)
   - JSON object containing metadata fields + `image_base64`.

### Frame Metadata Schema (request metadata)

```json
{
  "frame_id": 0,
  "timestamp_ms": 1715000000000,
  "content_type": "image/jpeg"
}
```

### Success Response Schema (`frame_result`)

```json
{
  "type": "frame_result",
  "session_id": "uuid",
  "frame_id": 0,
  "has_face": true,
  "roi": {
    "x": 120,
    "y": 70,
    "width": 180,
    "height": 180,
    "confidence": 0.91,
    "frame_width": 640,
    "frame_height": 480
  },
  "processing_ms": 23.47,
  "warning": null
}
```

Notes:

- Response is metadata-only.
- `annotated_image_base64` is not part of current contract.
- Processed image is served by `GET /api/v1/video/stream`.

### Error Response Schema (`frame_error`)

```json
{
  "type": "frame_error",
  "session_id": "uuid",
  "frame_id": 0,
  "detail": "error message"
}
```

`frame_id` may be `null` for unexpected internal failures.

### Validation/Error Cases

- Missing or malformed payload
- Invalid JSON/base64
- Binary metadata size invalid
- Missing image bytes
- Non-JPEG `content_type`
- Payload/image over configured limits
- Image decode failures

## GET `/api/v1/video/stream`

### Purpose

Continuous processed video stream for browser rendering.

### Query Parameters

- `session_id` (required, UUID)

### Success

- Status: `200`
- Content-Type: `multipart/x-mixed-replace; boundary=frame`
- Headers:
  - `Cache-Control: no-cache`
  - `X-Accel-Buffering: no`

### Per-Frame Multipart Format

Each frame part:

```text
--frame\r\n
Content-Type: image/jpeg\r\n
Content-Length: <len>\r\n
\r\n
<jpeg bytes>\r\n
```

### Behavior

- Missing session: `404` with `session_not_found`.
- Existing session + no frame yet: connection stays open and waits.
- New frame available: emits next multipart chunk.
- Disconnect/cancel: stream loop exits cleanly.
- Emission uses latest-frame version updates (not full frame queue replay).

## GET `/api/v1/roi`

### Purpose

Fetch recent ROI rows for a session.

### Query Parameters

- `session_id` (required, UUID)
- `limit` (optional, default `100`, min `1`, max `500`)

### Success Response (`RoiListResponse`)

```json
{
  "session_id": "uuid",
  "count": 2,
  "items": [
    {
      "frame_id": 2,
      "timestamp_ms": 200,
      "x": 12,
      "y": 12,
      "width": 32,
      "height": 32,
      "confidence": 0.9,
      "frame_width": 100,
      "frame_height": 100,
      "detector_name": "mediapipe.tasks.face_detector",
      "created_at": "2026-05-07T00:00:00Z"
    }
  ]
}
```

Rows are ordered newest-first by repository query (`frame_id desc`, then `created_at desc`).

### Error Behavior

- Missing session: `404` with `session_not_found`.
- Invalid query params: framework validation error response.

## Schemas

### `FrameResult` (`backend/app/schemas/video.py`)

- `type: "frame_result"`
- `session_id: UUID`
- `frame_id: int`
- `has_face: bool`
- `roi: RoiBounds | null`
- `processing_ms: float`
- `warning: string | null`

### `FrameError` (runtime payload)

- `type: "frame_error"`
- `session_id: string`
- `frame_id: int | null`
- `detail: string`

### `RoiBounds` (`backend/app/schemas/roi.py`)

- `x`, `y`, `width`, `height`: int
- `confidence`: float | null
- `frame_width`, `frame_height`: int

### `RoiItem`

- all `RoiBounds` fields +
- `frame_id: int`
- `timestamp_ms: int`
- `detector_name: string`
- `created_at: datetime`

### `RoiListResponse`

- `session_id: UUID`
- `count: int`
- `items: RoiItem[]`

## HTTP/WebSocket Errors

- `404 session_not_found` for missing session on stream/ROI.
- `400 invalid_frame_payload` for bad frame payloads in app-level JSON errors.
- `422 invalid_session_id` app error type exists; on WS invalid UUID path currently closes with `1008`.
- WebSocket `frame_error` payloads are used for per-frame processing/validation failures.

## Compatibility Notes

- MJPEG stream is designed for browser `<img>` consumption.
- It is not a seekable/random-access video file endpoint.
- Output is latest processed frame semantics per session.

Design context: [ARCHITECTURE.md](docs/ARCHITECTURE.md)

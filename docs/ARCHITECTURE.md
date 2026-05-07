# Architecture

## Architecture Overview

This system is a three-endpoint video-processing pipeline for a take-home assignment. The browser captures webcam frames and uploads them over WebSocket. The backend processes each frame (decode, detect, normalize ROI, draw ROI, persist ROI rows), then serves annotated output through MJPEG and ROI data through JSON. It is intentionally scoped for local/demo use with latest-frame semantics.

Endpoint-level behavior details are documented in [API_CONTRACT.md](docs/API_CONTRACT.md).

## Assignment Constraints Mapped to Implementation

- Exactly 3 core endpoints:
  - `WS /api/v1/video/feed`
  - `GET /api/v1/video/stream`
  - `GET /api/v1/roi`
- No OpenCV in application code:
  - Face detection uses MediaPipe.
  - ROI drawing uses Pillow.
- One-face assumption:
  - When multiple faces are detected, highest-confidence ROI is selected and warning is returned.
- ROI persistence:
  - ROI rows persisted in PostgreSQL (`roi_detections`).
- Frontend display:
  - Local camera preview + processed MJPEG stream + ROI metadata/history.
- Containerized setup:
  - Docker Compose runs `frontend`, `backend`, and `postgres`.

## High-Level Diagram

```mermaid
flowchart LR
    A[Browser / React Frontend] -- WS JPEG frames + metadata --> B[/api/v1/video/feed]
    B --> C[FrameProcessor]
    C --> D[MediaPipe FaceDetector]
    C --> E[ROI normalize + Pillow draw]
    C --> F[(LatestFrameStore<br/>latest frame + version)]
    C --> G[(PostgreSQL<br/>video_sessions + roi_detections)]
    A -- GET session_id --> H[/api/v1/video/stream MJPEG]
    H --> F
    H -- multipart/x-mixed-replace --> A
    A -- GET /api/v1/roi --> I[/api/v1/roi]
    I --> G
    I -- ROI JSON --> A
```

## Runtime Workflow

1. User clicks `Start` in frontend.
2. Frontend creates `session_id`, opens `WS /api/v1/video/feed?session_id=...`.
3. Backend accepts WebSocket and creates/activates session before first frame.
4. Frontend captures webcam frame to `<canvas>`, encodes JPEG, sends binary payload with metadata.
5. Backend parses payload, validates limits/type, decodes image, runs detector, normalizes ROI, draws ROI, stores latest annotated JPEG, persists ROI row (if ROI exists), and returns metadata result over WebSocket.
6. Frontend sets `<img src="/api/v1/video/stream?...">`; backend emits MJPEG parts when latest frame version changes.
7. Frontend polls `GET /api/v1/roi` every 2s to refresh ROI history.
8. On `Stop`, frontend clears timer, closes WebSocket, stops media tracks, and clears MJPEG URL.

## Backend Architecture

- API layer:
  - `backend/app/api/video_feed.py`: WebSocket ingestion loop and frame/error responses.
  - `backend/app/api/video_stream.py`: MJPEG `StreamingResponse`.
  - `backend/app/api/roi.py`: ROI history read endpoint.
- Schemas:
  - `backend/app/schemas/video.py`: `FrameMetadata`, `FrameResult`.
  - `backend/app/schemas/roi.py`: `RoiBounds`, `RoiItem`, `RoiListResponse`.
- Services:
  - `frame_processor.py`: parse/validate/decode/detect/draw/persist/store flow.
  - `face_detector.py`: MediaPipe detector wrapper with monotonic timestamp handling.
  - `latest_frame_store.py`: per-session latest frame + version + async wait.
  - `roi_normalizer.py`, `roi_drawer.py`: ROI normalization and Pillow rendering.
- Repositories:
  - `session_repository.py`: session get/get_or_create.
  - `roi_repository.py`: create ROI row + list by session.
- DB/session:
  - `db/models.py`, `db/session.py`, `db/init_db.py` (startup health + `create_all`).
- Config:
  - `core/config.py`: env-driven settings with `APP_` prefix.

## Frontend Architecture

- `frontend/src/App.tsx` owns:
  - webcam capture (`getUserMedia`)
  - frame upload loop (`setInterval`, binary payload framing)
  - WebSocket metadata handling (`frame_result`/`frame_error`)
  - processed feed display via `<img src={streamUrl}>`
  - ROI polling and dashboard rendering
  - stop/cleanup lifecycle (timer, socket, media tracks, stream URL reset)

## Data Model

- `video_sessions`:
  - `id` (UUID PK), `source`, `status`, timestamps.
- `roi_detections`:
  - UUID PK, FK `session_id -> video_sessions.id` (cascade delete),
  - frame/time fields (`frame_id`, `timestamp_ms`),
  - ROI box (`x`, `y`, `width`, `height`),
  - confidence, frame size, detector name, created_at.
- Indexes:
  - `(session_id, frame_id)`
  - `(session_id, created_at)`

Why relational DB is suitable here: ROI rows are structured, session-linked, time-ordered records that need predictable filtering/sorting and simple integrity constraints.

## Latest-Frame Streaming Design

- `LatestFrameStore` stores exactly one annotated JPEG per session plus a monotonically increasing version.
- Stream generator tracks `last_seen_version` and emits only when a newer version arrives.
- Waits use `asyncio.Condition` with timeout fallback for disconnect checks, avoiding tight polling loops.
- Resulting behavior is soft real-time/latest-frame semantics:
  - viewer sees newest processed frame
  - older intermediate processed frames may be skipped
  - no unbounded frame queue

## Error Handling and Edge Cases

- Invalid `session_id` on WS: connection closed with policy violation (`1008`) and invalid-session handling.
- Missing session on stream/ROI: `404 session_not_found`.
- Existing session with no frame yet: MJPEG request stays open and waits.
- Invalid frame payload:
  - malformed binary/text JSON/base64
  - missing image bytes
  - unsupported content type
  - oversized payload
  - oversized image dimensions
  - returns `frame_error` payload over WebSocket.
- No face detected: `has_face=false`, `roi=null`.
- Multiple faces: highest-confidence ROI + warning string.
- Stream disconnect/cancel: generator exits on `request.is_disconnected()` or cancellation.

## Security Fundamentals

- CORS configured from environment (`APP_CORS_ORIGINS`).
- Frame-size/metadata-size/image-dimension limits enforced in processing path.
- Content type restricted to `image/jpeg`.
- No authn/authz currently; acceptable for local assignment scope, not production-ready.
- DB credentials and app settings are environment-driven (`backend/.env.example` defaults).

## Pragmatism vs Over-Engineering

The architecture uses WebSocket ingestion + MJPEG egress + relational storage because that satisfies assignment requirements with low operational complexity. It intentionally avoids WebRTC signaling/media transport complexity and avoids extra infra layers (Redis/Kafka/Celery) not required for the deliverable.

## Testing Strategy

Backend tests cover:

- frame payload validation and WebSocket error handling
- metadata-only `FrameResult` expectation
- ROI normalization and multiple-face selection behavior
- ROI API ordering and response shape
- MJPEG stream contract pieces (404 missing session, content type/headers, chunk formatting, first chunk emission from generator)

Tests intentionally avoid fully consuming infinite stream responses.

## Known Limitations and Future Improvements

Current limitations:

- Latest-frame semantics can skip intermediate frames during high load.
- Minimal session/frame cleanup policy for long-running deployments.
- No authentication/authorization.

Possible future improvements (not currently implemented):

- Adaptive upload FPS based on measured p95 end-to-end latency.
- `requestVideoFrameCallback` based capture loop for smoother scheduling.
- Session TTL/cleanup for DB rows and in-memory latest-frame entries.
- Production-grade video transport (e.g., WebRTC) if lower-latency bi-directional media is required.

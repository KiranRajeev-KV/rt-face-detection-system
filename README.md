# Real-Time Face Detection Streaming System

Containerized take-home assignment project with a React frontend, FastAPI backend, and PostgreSQL. The browser captures webcam frames, uploads JPEG frames over WebSocket, the backend detects faces and draws ROI boxes without OpenCV, persists ROI rows, and serves a processed MJPEG stream for display.

## Assignment Fit

- Implements exactly three core application endpoints:
  - `WS /api/v1/video/feed` (ingestion)
  - `GET /api/v1/video/stream` (processed MJPEG feed)
  - `GET /api/v1/roi` (ROI history)
- ROI drawing is implemented with Pillow (no `cv2` usage in app code).
- Frontend displays processed video from the MJPEG endpoint and ROI/latency/status metadata from WebSocket + ROI API.

## Tech Stack

- Backend: FastAPI, Python 3.12, SQLAlchemy, Pydantic Settings
- Face detection: MediaPipe Tasks face detector (`blaze_face_short_range.tflite`)
- ROI drawing: Pillow
- Database: PostgreSQL
- Frontend: React + TypeScript + Vite
- Tooling/containers: Docker Compose, `uv` (backend), npm (frontend)

## Prerequisites

- Docker + Docker Compose for the quickest run path
- Optional local dev:
  - Python 3.12 + `uv`
  - Node.js 22+ + npm

## Quick Start (Docker)

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- FastAPI docs (framework-generated): `http://localhost:8000/docs`

## Local Development

Backend:

```bash
cd backend
cp .env.example .env
uv sync --dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Environment variables are defined in `backend/.env.example` and `frontend/.env.example`.

## Running Tests and Checks

Backend tests:

```bash
cd backend
uv run pytest
```

Backend lint:

```bash
cd backend
uv run ruff check app
```

Frontend build:

```bash
cd frontend
npm run build
```

## How to Use the App

1. Open `http://localhost:5173`.
2. Click `Start`.
3. Allow camera permission in the browser.
4. Observe:
   - local camera tile
   - processed MJPEG tile (`/api/v1/video/stream`)
   - latest ROI stats and warnings
   - ROI history table (polled from `/api/v1/roi`)
5. Click `Stop` to close WebSocket, stop camera tracks, and clear stream URL.

## API Overview

- `WS /api/v1/video/feed?session_id=<uuid>`
- `GET /api/v1/video/stream?session_id=<uuid>`
- `GET /api/v1/roi?session_id=<uuid>&limit=<1..500>`

Full contract: [API_CONTRACT.md](docs/API_CONTRACT.md)

## Architecture Overview

<img width="1448" height="1086" alt="image" src="https://github.com/user-attachments/assets/7e7d780c-1049-4d1c-913d-b1b9bb1ac9c9" />


The browser uploads JPEG frames with frame metadata over a WebSocket ingestion channel. The backend decodes the image, runs MediaPipe face detection, normalizes/clips ROI bounds, draws ROI on the frame with Pillow, stores the latest annotated frame in memory, and persists ROI rows in PostgreSQL. The processed feed endpoint serves a multipart MJPEG stream with latest-frame semantics per session. The ROI endpoint serves recent ROI rows for dashboard display. The design favors a small, assignment-scoped architecture with clear separation between API, services, repositories, and database layers.

Deep design notes: [ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Known Limitations

- Soft real-time with latest-frame semantics: intermediate frames may be skipped under load.
- Session and latest-frame lifecycle cleanup is minimal; in-memory latest frames reset on backend restart.
- No auth/authorization layer (acceptable for local take-home scope).
- Face selection uses highest confidence when multiple faces are detected; assignment assumes one face.

## AI Usage Disclosure

See [AI-USAGE.md](AI-USAGE.md).

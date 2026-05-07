# AI Usage Disclosure

## Summary

AI assistance was used for implementation support and documentation work in this assignment. AI was used as an engineering copilot, not as an unreviewed source of truth.

## What AI Was Used For

- Reviewing code structure and identifying documentation gaps.
- Drafting and refining technical documentation language.
- Verifying API contract consistency against backend/frontend code.
- Suggesting streaming-focused clarifications (latest-frame semantics, MJPEG behavior).
- Assisting with test/check command execution flow and result reporting.

## What Was Human-Owned

- Interpreting assignment requirements and tradeoffs.
- Final decisions on architecture and endpoint behavior.
- Reviewing and accepting/rejecting AI-generated edits.
- Running repository checks and validating outcomes.
- Final responsibility for submission quality and correctness.

## Important Design Decisions

- WebSocket is used for ingestion (`/api/v1/video/feed`).
- Processed output is served via MJPEG stream (`/api/v1/video/stream`).
- WebSocket `frame_result` is metadata-only; image bytes are not returned there.
- ROI drawing is implemented with Pillow, not OpenCV.
- Latest-frame semantics are implemented via in-memory per-session store + versioned waits.
- ROI detections are persisted in PostgreSQL as relational rows linked to sessions.

## Disclosure Statement

AI tools were used to accelerate development and documentation, while final engineering judgment, validation, and submission ownership remained with the human author.

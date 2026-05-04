from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    error_code = "application_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SessionNotFoundError(AppError):
    status_code = 404
    error_code = "session_not_found"

    def __init__(self, session_id: UUID):
        super().__init__(f"session {session_id} not found")


class FramePayloadError(AppError):
    status_code = 400
    error_code = "invalid_frame_payload"

    def __init__(self, message: str, frame_id: int | None = None):
        self.frame_id = frame_id
        super().__init__(message)


class DetectorInitializationError(AppError):
    status_code = 503
    error_code = "detector_initialization_failed"


class SessionIdentifierError(AppError):
    status_code = 422
    error_code = "invalid_session_id"


class FrameNotReadyError(AppError):
    status_code = 404
    error_code = "latest_frame_not_ready"

    def __init__(self, session_id: UUID):
        super().__init__(f"no processed frame available for session {session_id}")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "detail": exc.message},
        )


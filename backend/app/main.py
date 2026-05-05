from contextlib import asynccontextmanager

from app.api import roi, video_feed, video_stream
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.init_db import wait_for_database
from app.db.session import session_manager
from app.services.dependencies import app_state
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    effective_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configure_logging(effective_settings.log_level)
        app_state.configure(effective_settings)
        session_manager.configure(effective_settings.database_url)
        await wait_for_database(effective_settings)
        yield
        await session_manager.dispose()

    app = FastAPI(
        title="Mega AI Face Detection API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=effective_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(video_feed.router)
    app.include_router(video_stream.router)
    app.include_router(roi.router)
    app.state.settings = effective_settings
    return app


app = create_app()

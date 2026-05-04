import asyncio

from app.core.config import Settings
from app.db.models import Base
from app.db.session import session_manager
from sqlalchemy import text


async def wait_for_database(settings: Settings) -> None:
    last_error: Exception | None = None
    engine = session_manager.engine
    assert engine is not None
    for _ in range(settings.db_connect_retries):
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SELECT 1"))
                await connection.run_sync(Base.metadata.create_all)
            return
        except Exception as exc:  # pragma: no cover
            last_error = exc
            await asyncio.sleep(settings.db_connect_retry_delay_seconds)
    if last_error is not None:
        raise last_error

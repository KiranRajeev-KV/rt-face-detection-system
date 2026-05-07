import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", case_sensitive=False)

    env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+psycopg://face_stream:face_stream@postgres:5432/face_stream"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    max_frame_size_bytes: int = 1_048_576
    max_metadata_size_bytes: int = 16_384
    max_image_width: int = 1280
    max_image_height: int = 720
    detector_min_confidence: float = 0.5
    detector_model_path: str = "/app/models/blaze_face_short_range.tflite"
    log_level: str = "INFO"
    db_connect_retries: int = 15
    db_connect_retry_delay_seconds: int = 2

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

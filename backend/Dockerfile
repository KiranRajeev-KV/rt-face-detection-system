FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libxcb1 libgl1 libegl1 libgles2 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY . .
RUN env UV_CACHE_DIR=/tmp/uv-cache uv sync --no-dev

RUN mkdir -p /app/models \
    && curl -fsSL https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite \
      -o /app/models/blaze_face_short_range.tflite

EXPOSE 8000

CMD ["env", "UV_CACHE_DIR=/tmp/uv-cache", "uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

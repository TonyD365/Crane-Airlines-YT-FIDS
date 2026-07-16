# syntax=docker/dockerfile:1
#
# Crane Airlines YouTube FIDS
# Single-stage image: the runtime needs FFmpeg and fonts anyway, so a builder
# stage would only add complexity without shrinking the result.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Crane-Airlines-YT-FIDS" \
      org.opencontainers.image.description="Airport style FIDS rendered with Pillow and streamed to YouTube via FFmpeg" \
      org.opencontainers.image.source="https://github.com/TonyD365/Crane-Airlines-YT-FIDS" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg           -> the encoder / RTMP publisher
# fonts-dejavu-core, fonts-liberation -> board typography
# fontconfig       -> font lookup for the registry
# tini             -> PID 1 that reaps FFmpeg and forwards SIGTERM
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ffmpeg \
        fontconfig \
        fonts-dejavu-core \
        fonts-liberation \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first: this layer is cached across code changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app.py ./
COPY crane_fids ./crane_fids
COPY assets ./assets

# Run unprivileged: nothing here needs root.
RUN useradd --create-home --uid 10001 fids \
    && chown -R fids:fids /app
USER fids

ENV WIDTH=1920 \
    HEIGHT=1080 \
    FPS=30 \
    LOG_LEVEL=INFO \
    AIRPORT_NAME="CRANE INTERNATIONAL AIRPORT" \
    FONT_DIR=/app/assets/fonts

# Liveness: the renderer must be able to compose a frame.
HEALTHCHECK --interval=5m --timeout=30s --start-period=30s --retries=3 \
    CMD python -c "import sys; from crane_fids.config import Config; from crane_fids.renderer import FidsRenderer; sys.exit(0 if FidsRenderer.from_config(Config.from_env()) else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "app.py"]

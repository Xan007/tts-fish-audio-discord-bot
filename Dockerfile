FROM python:3.11-slim

# Install FFmpeg and system dependencies for Discord audio playback
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies using uv
RUN uv sync --no-dev --frozen || uv sync --no-dev

# Copy application code
COPY src/ ./src/
COPY README.md .

# Create directory for SQLite storage
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/bot.db

CMD ["uv", "run", "python", "-m", "src.main"]

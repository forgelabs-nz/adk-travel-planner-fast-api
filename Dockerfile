# Dockerfile for Google ADK Multi-Agent System
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy uv installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY server.py config.py callback_logging.py ./
COPY movie_pitch_agent/ ./movie_pitch_agent/

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose port
EXPOSE 8010

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8010/health')" || exit 1

# Run the server
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010"]

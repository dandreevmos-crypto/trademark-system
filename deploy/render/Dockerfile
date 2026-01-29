# Dockerfile for Render deployment (lightweight, no Celery/Redis)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (including libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY deploy/render/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY deploy/render/ ./deploy/render/

# Replace config and database with Render versions
COPY deploy/render/config_render.py ./app/config.py
COPY deploy/render/database_render.py ./app/database.py
COPY deploy/render/main_render.py ./app/main.py
COPY deploy/render/api_v1_render.py ./app/api/v1/__init__.py

# Create data directory for files
RUN mkdir -p /app/data /app/data/files

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Render uses PORT env variable)
EXPOSE 10000

# Run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}

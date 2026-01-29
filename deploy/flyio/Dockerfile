# Dockerfile for Fly.io deployment (lightweight, no Celery/Redis)
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
COPY deploy/flyio/requirements-flyio.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY deploy/flyio/ ./deploy/flyio/

# Replace config and database with Fly.io versions
COPY deploy/flyio/config_flyio.py ./app/config.py
COPY deploy/flyio/database_flyio.py ./app/database.py
COPY deploy/flyio/main_flyio.py ./app/main.py
COPY deploy/flyio/api_v1_flyio.py ./app/api/v1/__init__.py

# Create data directory for files
RUN mkdir -p /app/data /app/data/files

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Simple Dockerfile for Photools
FROM python:3.12-slim

# Ensure all security updates are applied
RUN apt-get update && apt-get upgrade -y && apt-get clean

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=false \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Install system dependencies
RUN apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.3

# Configure Poetry
RUN poetry config virtualenvs.create false

# Set work directory
WORKDIR /app

# Copy Poetry files first (for better Docker layer caching)
COPY pyproject.toml poetry.lock ./

# Debug: Show what we copied
RUN ls -la pyproject.toml poetry.lock

# Install dependencies exactly as specified in poetry.lock
RUN poetry install --only=main --verbose && \
    rm -rf $POETRY_CACHE_DIR

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p uploads models logs

# Expose port
EXPOSE 8090

# Default command
CMD ["poetry", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8090", "--reload"]
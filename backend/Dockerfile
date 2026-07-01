# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps needed by some network libs / cryptography.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY README.md ./
RUN pip install --upgrade pip && pip install -e .

# Copy application code.
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

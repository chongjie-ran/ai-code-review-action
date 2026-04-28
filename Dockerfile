# CodeLens AI GitHub Action
# Multi-stage build for small image
FROM python:3.11-slim AS builder

WORKDIR /build

# Install dependencies
RUN pip install --no-cache-dir --user \
    requests>=2.31.0 \
    PyJWT>=2.8.0

FROM python:3.11-slim

WORKDIR /app

# Copy only what we need
COPY --from=builder /root/.local /root/.local
COPY src/ /app/src/
COPY scripts/ /app/scripts/

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Entrypoint script handles all GitHub API + CodeLens API communication
ENTRYPOINT ["python", "/app/scripts/entrypoint.py"]

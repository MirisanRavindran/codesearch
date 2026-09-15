# Multi-stage build:
#   1. Build the React frontend
#   2. Install Python deps + copy backend
#   3. Serve everything from FastAPI
#

# ---- Stage 1: frontend ----
FROM node:20-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build
# Output: /app/dist/

# ---- Stage 2: backend ----
FROM python:3.11-slim

WORKDIR /app

# System deps: build tools for faiss + sentence-transformers wheels
# (some transitive C deps compile on install for arm64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps first — layer caches when only code changes
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -e .

# Backend code
COPY backend ./backend

# Built frontend from stage 1
COPY --from=frontend /app/dist ./static

# Expected volume mount point for FAISS index + metadata
VOLUME /data
ENV DATA_DIR=/data

EXPOSE 8000

# Uvicorn workers=1 because the model + index live in memory per worker.
# For higher throughput, front with nginx and run multiple containers.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

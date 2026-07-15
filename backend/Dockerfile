# ──────────────────────────────────────────────
# Shubham AI — Backend (Render)
# ──────────────────────────────────────────────
# Render auto-detects this Dockerfile from backend/.
# CPU-only torch keeps the image under Render's build memory limit.
#
# On the Starter (free) plan, no persistent disk is attached. The
# app's lifespan auto-ingest hook rebuilds the small Chroma index
# (a few MB) from data/raw/ on every cold start. Add a disk (paid
# plan) and set HF_HOME under it to skip the rebuild entirely.
# ──────────────────────────────────────────────

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/backend/data/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/backend/data/.cache/sentence-transformers \
    PORT=8001

WORKDIR /app

# OS deps:
#   - build-essential / gcc: build wheels for sentence-transformers, etc.
#   - libgomp1: OpenMP runtime for torch.
#   - portaudio19-dev: needed by pyaudio (Vapi dependency).
#   - ffmpeg: audio transcoding for voice / media endpoints.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libgomp1 \
        portaudio19-dev \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch FIRST so the heavier wheels don't drag the
# default (CUDA) ones along. This is the single biggest build-time win.
RUN pip install --upgrade pip && \
    pip install \
        torch==2.6.0 \
        --index-url https://download.pytorch.org/whl/cpu

# Now install the rest of the backend deps.
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy the rest of the backend source.
COPY . /app/backend/

# Render expects the working directory of the app to be explicit.
WORKDIR /app/backend

# Render exposes $PORT (default 10000 for Web Services). Use 0.0.0.0 so
# the container is reachable from Render's proxy.
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

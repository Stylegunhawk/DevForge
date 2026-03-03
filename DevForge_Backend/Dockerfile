# =============================================================================
# DevForge Unified Dockerfile
# =============================================================================
# Optimized for size and security.
# Features:
# - Multi-stage build (reduces size by removing compilers)
# - CPU-only PyTorch (saves ~1-2GB)
# - Non-root user (security)
# - Runtime-only dependencies
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (removed in final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libmagic-dev \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .

# 1. Install CPU-only Torch first (Major size optimization)
# This prevents downloading the massive NVIDIA/CUDA binaries.
# We use --extra-index-url so that ARM64 Mac users can still fall back to 
# default PyPI wheels (which are already small for ARM).
RUN pip install --no-cache-dir torch==2.2.2 torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cpu

# 2. Install remaining requirements
# We use --extra-index-url so that any packages depending on torch (like transformers)
# also search the CPU-only index, preventing a massive CUDA download.
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# 3. Install production server
RUN pip install --no-cache-dir gunicorn

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

# Metadata
LABEL maintainer="DevForge Team"
LABEL version="0.9.0"

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 devforge && \
    mkdir -p data/uploads data/chromadb && \
    chown -R devforge:devforge /app

# Copy application code
# IMPORTANT: Relying on .dockerignore to exclude tests/, debug files, and sensitive data
COPY . .

# Set permission for code (in case of volume mounting issues)
RUN chown -R devforge:devforge /app

# Switch to non-root user
USER devforge

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE 8001

# Default Command (Overridden by docker-compose)
# Uses Gunicorn by default for production safety
CMD ["gunicorn", "src.main:app", \
    "-k", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8001", \
    "--workers", "4", \
    "--timeout", "120"]
# SafeReach Backend — Production Dockerfile
# Multi-stage build: keeps final image lean

FROM python:3.11-slim AS base

WORKDIR /app

# Install system deps (PostGIS client, GDAL for GeoAlchemy2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libgdal-dev \
    libgeos-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# ── Dependencies stage ────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM deps AS runtime

COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 safereach && chown -R safereach:safereach /app
USER safereach

# Create directories for model files
RUN mkdir -p app/ai/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

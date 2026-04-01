# ── Stage 1: build deps ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed to compile Python packages (psycopg2, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps only (WeasyPrint GTK stack + libpq)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi8 \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security
RUN useradd --create-home --shell /bin/false appuser

# App code — exclude dev artifacts via .dockerignore
COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Docker daemon health check — uses the fast liveness probe (no deps, instant)
# interval: 30s, timeout: 5s, retries: 3 → container marked unhealthy after 90s
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request, sys; \
         r = urllib.request.urlopen('http://localhost:8000/health', timeout=4); \
         sys.exit(0 if r.status == 200 else 1)" \
    || exit 1

# Production: no --reload, workers scaled via env
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--no-access-log"]

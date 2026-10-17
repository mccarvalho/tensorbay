# syntax=docker/dockerfile:1

############################
# Builder
############################
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps for asyncpg/cryptography wheels if needed.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

############################
# Runtime
############################
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=dev

WORKDIR /app

# Non-root user
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /install /usr/local
COPY neocloud ./neocloud
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

USER appuser

EXPOSE 8000

# Container port matches the ALB target group health check (/health) and the
# container_port variable in the Terraform (8000).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "neocloud.main:app", "--host", "0.0.0.0", "--port", "8000"]

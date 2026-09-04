# ===== Etapa 1: build de dependencias =====
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Dependencias del sistema para compilar wheels (bcrypt, pillow).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --prefix=/install \
    "fastapi>=0.110" "uvicorn[standard]>=0.29" "gunicorn>=21.2" \
    "sqlalchemy>=2.0" "alembic>=1.13" "pymysql>=1.1" \
    "pydantic>=2.6" "pydantic-settings>=2.2" "pyjwt>=2.8" "bcrypt>=4.1" \
    "python-ulid>=2.2" "python-barcode>=0.15" "qrcode[pil]>=7.4" \
    "httpx>=0.27" "python-multipart>=0.0.9" "email-validator>=2.1"

# ===== Etapa 2: imagen final ligera =====
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Runtime de pillow.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libpng16-16 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Código de la aplicación.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY docker/entrypoint.sh ./entrypoint.sh
RUN sed -i 's/\r//' ./entrypoint.sh && chmod +x ./entrypoint.sh

# Usuario no-root.
RUN useradd -m appuser
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8080/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]

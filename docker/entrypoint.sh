#!/usr/bin/env bash
set -e

echo "[entrypoint] Aplicando migraciones (alembic upgrade head)..."
python -m alembic upgrade head

# Sembrar datos iniciales solo si se solicita (RUN_SEEDS=1).
if [ "${RUN_SEEDS:-0}" = "1" ]; then
  echo "[entrypoint] Ejecutando seeds idempotentes..."
  python -m app.seeds.run
fi

echo "[entrypoint] Iniciando servidor en :8080"
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 60

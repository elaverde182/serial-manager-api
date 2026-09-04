"""Arranque de la aplicación FastAPI."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.middleware import LoginRateLimitMiddleware, SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Sistema de Identificación y Trazabilidad de Equipos. "
        "Backend REST con autenticación JWT y proveedor de identidad conectable."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    LoginRateLimitMiddleware,
    max_attempts=settings.login_max_attempts,
    window_s=settings.login_window_s,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(IntegrityError)
def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Convierte violaciones de integridad (duplicados / FK inválida) en 409 en vez de 500."""
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Conflicto de integridad: registro duplicado o referencia inválida.",
            "code": "integrity_error",
        },
    )


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness: la app está arriba."""
    return {"status": "ok", "app": settings.app_name, "version": __version__}


@app.get("/health/db", tags=["health"])
def health_db() -> JSONResponse:
    """Readiness: la conexión a la base de datos responde."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok", "database": "up"})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=503, content={"status": "error", "database": str(exc)}
        )

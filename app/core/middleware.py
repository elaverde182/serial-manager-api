"""Middlewares: cabeceras de seguridad y rate-limit simple en login."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers.setdefault("Cache-Control", "no-store")
        return response


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Limita intentos de login por IP (ventana deslizante en memoria)."""

    def __init__(self, app, *, path_suffix: str = "/auth/login", max_attempts: int = 10, window_s: int = 60):
        super().__init__(app)
        self.path_suffix = path_suffix
        self.max_attempts = max_attempts
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.endswith(self.path_suffix):
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            hits = self._hits[ip]
            while hits and now - hits[0] > self.window_s:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Demasiados intentos de login. Intente más tarde."},
                )
            hits.append(now)
        return await call_next(request)

"""Agregador de routers de la API v1."""
from fastapi import APIRouter

from app.api.v1.endpoints import audit, auth, catalogs, equipment, labels, sync, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(catalogs.router)
api_router.include_router(equipment.router)
api_router.include_router(labels.router)
api_router.include_router(sync.router)
api_router.include_router(audit.router)

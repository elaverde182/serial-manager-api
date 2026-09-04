"""Endpoints de usuarios y roles (solo administrador)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.models.catalog import Country
from app.models.user import Role, User
from app.schemas.user import RoleOut, UserCreate, UserOut, UserUpdate

router = APIRouter(tags=["usuarios"])


def _get_role(db: Session, name: str) -> Role:
    role = db.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
    if not role:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Rol inexistente: {name}")
    return role


def _check_country(db: Session, code: str | None) -> None:
    if code and not db.get(Country, code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"País inexistente: {code}")


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: object = Depends(security.require_role("admin")),
):
    return db.execute(select(User).order_by(User.id)).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: object = Depends(security.require_role("admin")),
):
    exists = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "El usuario ya existe")
    _check_country(db, payload.default_country_code)
    role = _get_role(db, payload.role_name)
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=security.hash_password(payload.password),
        role_id=role.id,
        provider="local",
        default_country_code=payload.default_country_code or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(security.require_role("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(security.require_role("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if payload.email is not None:
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password:
        user.password_hash = security.hash_password(payload.password)
    if payload.role_name:
        user.role_id = _get_role(db, payload.role_name).id
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.default_country_code is not None:
        code = payload.default_country_code or None
        _check_country(db, code)
        user.default_country_code = code
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(security.require_role("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    user.is_active = False
    db.commit()
    return {"detail": "Usuario desactivado"}


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _: object = Depends(security.get_current_principal),
):
    return db.execute(select(Role).order_by(Role.id)).scalars().all()

"""Servicio de generación de seriales: ULID + consecutivo atómico + código aleatorio."""
from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ulid import ULID

from app.models.catalog import Country, EquipmentType, Laboratory, SerialFormat
from app.models.equipment import Consecutive, EquipmentTag
from app.models.user import User

DEFAULT_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class SerialError(Exception):
    """Error de negocio al generar el serial."""


def check_country_allowed(
    db: Session, *, user_id: int | None, role: str, country_code: str
) -> None:
    """Un no-admin solo puede generar seriales de su país asignado.

    El país del payload no es confiable (el bloqueo del formulario es solo
    visual); aquí se valida contra el default_country_code asignado por el
    administrador. Lanza SerialError si no coincide o no tiene país asignado.
    """
    if role == "admin":
        return
    user = db.get(User, user_id) if user_id else None
    assigned = user.default_country_code if user else None
    if not assigned:
        raise SerialError(
            "No tienes un país asignado; solicita al administrador que lo asigne"
        )
    if country_code != assigned:
        raise SerialError(
            f"Solo puedes generar seriales de tu país asignado ({assigned})"
        )


def _gen_random(alphabet: str, length: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _resolve_format(db: Session, country_code: str, lab_id: int | None) -> SerialFormat:
    """Busca el formato más específico: país+lab → país → global."""
    candidates = db.execute(
        select(SerialFormat).where(SerialFormat.is_active.is_(True))
    ).scalars().all()

    def score(fmt: SerialFormat) -> int:
        s = 0
        if fmt.country_code == country_code:
            s += 2
        elif fmt.country_code is not None:
            return -1  # país distinto: no aplica
        if fmt.laboratory_id == lab_id and lab_id is not None:
            s += 1
        elif fmt.laboratory_id is not None:
            return -1
        return s

    best: SerialFormat | None = None
    best_score = -1
    for fmt in candidates:
        sc = score(fmt)
        if sc > best_score:
            best_score, best = sc, fmt
    if best is None:
        # Fallback en memoria si no hay formatos sembrados.
        return SerialFormat(
            template="{country}-{consecutive:06d}-{random}",
            random_length=6,
            random_alphabet=DEFAULT_ALPHABET,
        )
    return best


def _next_consecutive(db: Session, country_code: str, lab_id: int | None) -> int:
    """Incrementa atómicamente el consecutivo con bloqueo de fila (FOR UPDATE)."""
    stmt = select(Consecutive).where(
        Consecutive.country_code == country_code,
        Consecutive.laboratory_id.is_(lab_id) if lab_id is None
        else Consecutive.laboratory_id == lab_id,
    )
    # with_for_update: bloquea la fila en MySQL/Postgres (SQLite lo ignora sin error).
    row = db.execute(stmt.with_for_update()).scalar_one_or_none()
    if row is None:
        row = Consecutive(
            country_code=country_code, laboratory_id=lab_id, current_value=0
        )
        db.add(row)
        db.flush()
    row.current_value += 1
    db.flush()
    return row.current_value


def _render_serial(
    template: str, country: Country, lab: Laboratory | None, consec: int, rnd: str
) -> str:
    return template.format(
        country=country.prefix or country.code,
        lab=lab.code if lab else "",
        consecutive=consec,
        random=rnd,
    )


def generate_tag(
    db: Session,
    *,
    country_code: str,
    laboratory_id: int | None,
    equipment_type_id: int | None,
    reason: str | None,
    notes: str | None,
    created_by: int | None,
    client_op_id: str | None = None,
    serial_code: str | None = None,
) -> EquipmentTag:
    """Genera un equipo con serial único. Maneja concurrencia y anti-duplicados.

    Si `serial_code` viene dado (serial definitivo ya generado offline por el
    cliente), se conserva tal cual en vez de generar uno nuevo: así la etiqueta
    impresa sin conexión sigue siendo válida al sincronizar. Si ese serial ya
    existe (colisión entre dispositivos), se lanza SerialError para que el
    cliente lo regenere.
    """
    country = db.get(Country, country_code)
    if not country or not country.is_active:
        raise SerialError(f"País inválido o inactivo: {country_code}")

    lab = None
    if laboratory_id is not None:
        lab = db.get(Laboratory, laboratory_id)
        if not lab or lab.country_code != country_code:
            raise SerialError("Laboratorio inválido para el país indicado")

    # Idempotencia: si ya existe el client_op_id, devolver el existente.
    if client_op_id:
        existing = db.execute(
            select(EquipmentTag).where(EquipmentTag.client_op_id == client_op_id)
        ).scalar_one_or_none()
        if existing:
            return existing

    # El serial del MODELO seleccionado se genera con la longitud que le
    # corresponde (correo del cliente, punto 6): bloque plano alfanumérico de esa
    # longitud exacta, sin prefijo ni separadores (imita el serial de fábrica).
    # Si no se indica modelo (caso no esperado en el flujo real), se cae al
    # formato clásico PAÍS-CONSECUTIVO-ALEATORIO.
    serial_length: int | None = None
    if equipment_type_id is not None:
        et = db.get(EquipmentType, equipment_type_id)
        if et and et.serial_length:
            serial_length = et.serial_length

    # Serial definitivo del cliente (offline): validar que no exista ya.
    if serial_code:
        exists = db.execute(
            select(EquipmentTag).where(EquipmentTag.serial_code == serial_code)
        ).scalar_one_or_none()
        if exists:
            raise SerialError(
                f"El serial '{serial_code}' ya existe (colisión al sincronizar)"
            )

    fmt = _resolve_format(db, country_code, laboratory_id)
    alphabet = fmt.random_alphabet or DEFAULT_ALPHABET

    consec = _next_consecutive(db, country_code, laboratory_id)

    # Reintento ante colisión del código aleatorio o del consecutivo (ambos UNIQUE).
    last_err: Exception | None = None
    for _ in range(10):
        if serial_code:
            # Serial ya definido por el cliente: se conserva; solo se reasigna el
            # consecutivo si hubiera colisión de fila por concurrencia.
            serial = serial_code
            rnd = serial_code[:20]
        elif serial_length:
            # Serial plano de longitud fija; alfabeto sin ambiguos (sin O/0, I/1)
            # para lectura/escaneo confiable. El consecutivo se conserva en la
            # columna para trazabilidad aunque no aparezca en el serial.
            serial = _gen_random(DEFAULT_ALPHABET, serial_length)
            rnd = serial
        else:
            rnd = _gen_random(alphabet, fmt.random_length or 6)
            serial = _render_serial(fmt.template, country, lab, consec, rnd)
        tag = EquipmentTag(
            id=str(ULID()),
            serial_code=serial,
            country_code=country_code,
            laboratory_id=laboratory_id,
            consecutive=consec,
            random_code=rnd,
            equipment_type_id=equipment_type_id,
            status="active",
            reason=reason,
            notes=notes,
            created_by=created_by,
            client_op_id=client_op_id,
        )
        db.add(tag)
        try:
            db.flush()
            return tag
        except IntegrityError as exc:
            db.rollback()
            last_err = exc
            # Re-asignar consecutivo tras rollback y reintentar el aleatorio.
            consec = _next_consecutive(db, country_code, laboratory_id)
    raise SerialError(f"No se pudo generar un serial único: {last_err}")

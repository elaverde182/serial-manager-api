"""Datos iniciales idempotentes (roles, admin, países, catálogo del Excel, etiqueta, formato)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.database import Base
from app.models.catalog import Country, EquipmentType, LabelSize, SerialFormat
from app.models.user import Role, User

# Catálogo de equipos del archivo del cliente (serializado de equipo proyecto.xlsx)
EQUIPMENT_CATALOG = {
    "Data": [
        "TG2492", "TG2482", "F@ST3890", "F@ST3896",
        "FG1100", "IP3442", "Adtran 424RG 1", "Adtran 424RG 2",
    ],
    "Video": [
        "eSTREAM 4k", "Fuse 4k", "DMS1004", "DCX3520", "DCX525", "VIP6102",
    ],
}

# Catálogo real del cliente: cada modelo con la LONGITUD EXACTA de su serial de
# fábrica (correo del equipo). Se siembran bajo la categoría "CPE" y el serial
# generado tendrá justo esa cantidad de caracteres alfanuméricos.
MODEL_SERIAL_LENGTHS: list[tuple[str, int]] = [
    ("TG1682G", 15), ("DMS1004HDHM", 12), ("RP324U", 13), ("Fast@3890", 15),
    ("CT700", 12), ("EFSGCDW362", 16), ("ONHUAHG8V5", 16), ("ONHUAHG8Q2", 16),
    ("CT700 mini SIM", 12), ("DCX700", 12), ("FG1100R", 13), ("DCX700 M-Card", 12),
    ("RP362M", 13), ("TG862A", 15), ("DCX3200 F2", 12), ("TG862G", 15),
    ("DCX3210", 12), ("G-240W-A", 12), ("G-241W-A", 12), ("DCX525e", 12),
    ("IP3442M", 13), ("DG1660A", 15), ("CH7469LLA", 14), ("DCX3510-M", 12),
    ("DCX3520e-M", 12), ("DCX3200 F3", 12), ("DG1670A", 15), ("TG1672G", 15),
    ("TG2492", 12), ("TG2492LGL", 12), ("TG2492LGV", 12), ("TG2492P", 12),
    ("TG2492LGF", 12), ("TG2482A", 15), ("HG8245W5", 16), ("IPA3102HDW", 15),
    ("IPA1114HDW", 15),
]
MODELS_CATEGORY = "CPE"

COUNTRIES = [
    ("CO", "Colombia", "CO"),
    ("US", "Estados Unidos", "US"),
    ("CL", "Chile", "CL"),
    ("TT", "Trinidad y Tobago", "TT"),
    ("PR", "Puerto Rico", "PR"),
    ("CR", "Costa Rica", "CR"),
    ("PA", "Panamá", "PA"),
    ("PFZ", "Panamá FTZ", "PFZ"),
    ("DO", "República Dominicana", "DO"),
]

# Usuarios de prueba (uno por país) para validar el país por defecto por usuario.
# Solo se siembran fuera de producción.
TEST_USERS = [
    ("operador_co", "Operador Colombia", "CO"),
    ("operador_us", "Operador Estados Unidos", "US"),
    ("operador_cl", "Operador Chile", "CL"),
    ("operador_tt", "Operador Trinidad y Tobago", "TT"),
    ("operador_pr", "Operador Puerto Rico", "PR"),
    ("operador_cr", "Operador Costa Rica", "CR"),
    ("operador_pa", "Operador Panamá", "PA"),
    ("operador_pfz", "Operador Panamá FTZ", "PFZ"),
    ("operador_do", "Operador República Dominicana", "DO"),
]
TEST_USER_PASSWORD = "operador123"


def seed(db: Session) -> None:
    # --- Roles ---
    roles = {}
    for name, desc in [
        ("admin", "Gestiona catálogos, usuarios y configuración."),
        ("supervisor", "Gestiona el catálogo de modelos (altas y ediciones)."),
        ("operator", "Genera seriales, imprime e ingresa/descarta equipos."),
    ]:
        role = db.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if not role:
            role = Role(name=name, description=desc)
            db.add(role)
            db.flush()
        roles[name] = role

    # --- Usuario admin (solo modo local) ---
    admin = db.execute(
        select(User).where(User.username == settings.admin_username)
    ).scalar_one_or_none()
    if not admin:
        db.add(
            User(
                username=settings.admin_username,
                full_name=settings.admin_fullname,
                password_hash=security.hash_password(settings.admin_password),
                role_id=roles["admin"].id,
                provider="local",
            )
        )

    # --- Países ---
    for code, name, prefix in COUNTRIES:
        if not db.get(Country, code):
            db.add(Country(code=code, name=name, prefix=prefix))
    db.flush()

    # --- Usuarios de prueba (solo fuera de producción) ---
    if settings.app_env != "production":
        for username, full_name, country_code in TEST_USERS:
            exists = db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            if not exists:
                db.add(
                    User(
                        username=username,
                        full_name=full_name,
                        password_hash=security.hash_password(TEST_USER_PASSWORD),
                        role_id=roles["operator"].id,
                        provider="local",
                        default_country_code=country_code,
                    )
                )

    # --- Catálogo de tipos de equipo (demo) ---
    for category, models in EQUIPMENT_CATALOG.items():
        for model in models:
            exists = db.execute(
                select(EquipmentType).where(
                    EquipmentType.category == category, EquipmentType.model == model
                )
            ).scalar_one_or_none()
            if not exists:
                db.add(EquipmentType(category=category, model=model))

    # --- Catálogo real del cliente con longitud de serial por modelo ---
    for model, length in MODEL_SERIAL_LENGTHS:
        row = db.execute(
            select(EquipmentType).where(
                EquipmentType.category == MODELS_CATEGORY, EquipmentType.model == model
            )
        ).scalar_one_or_none()
        if row is None:
            db.add(
                EquipmentType(
                    category=MODELS_CATEGORY, model=model, serial_length=length
                )
            )
        elif row.serial_length != length:
            # Mantener la longitud sincronizada si el catálogo del cliente cambia.
            row.serial_length = length

    # --- Tamaño de etiqueta por defecto (63x25mm @203dpi, Code128) ---
    # `zpl_template` vacío = usar el render paramétrico de label_service, que
    # escala el contenido a los mm configurados. Solo se llena para plantillas
    # hechas a medida.
    has_size = db.execute(select(LabelSize).limit(1)).scalar_one_or_none()
    if not has_size:
        db.add(
            LabelSize(
                name="63mm x 25mm",
                width_mm=63,
                height_mm=25,
                dpi=203,
                zpl_template="",
                barcode_type="code128",
                is_default=True,
            )
        )

    # --- Formato de serial global por defecto ---
    has_fmt = db.execute(select(SerialFormat).limit(1)).scalar_one_or_none()
    if not has_fmt:
        db.add(
            SerialFormat(
                country_code=None,
                laboratory_id=None,
                template="{country}-{consecutive:06d}-{random}",
                random_length=6,
            )
        )

    db.commit()


def main() -> None:
    # En dev/SQLite creamos las tablas si no existen (en prod lo hace Alembic).
    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
        print("[OK] Seeds aplicados correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""Modelos ORM. Importar todo aquí asegura que Base.metadata los conozca."""
from app.models.audit import AuditLog
from app.models.catalog import (
    Country,
    EquipmentType,
    Laboratory,
    LabelSize,
    SerialFormat,
)
from app.models.equipment import (
    Consecutive,
    EquipmentStatusHistory,
    EquipmentTag,
)
from app.models.printing import PrintJob
from app.models.sync import SyncLog
from app.models.user import Role, User

__all__ = [
    "AuditLog",
    "Country",
    "EquipmentType",
    "Laboratory",
    "LabelSize",
    "SerialFormat",
    "Consecutive",
    "EquipmentStatusHistory",
    "EquipmentTag",
    "PrintJob",
    "SyncLog",
    "Role",
    "User",
]

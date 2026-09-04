"""Tipo JSON portátil (MySQL JSON / SQLite TEXT-backed)."""
from sqlalchemy import JSON

# El tipo JSON genérico de SQLAlchemy mapea a JSON nativo en MySQL 8+
# y a TEXT serializado en SQLite, sin cambiar el código de la aplicación.
JSONType = JSON

"""Punto de composición de los adaptadores salientes de IncidentOps."""

import os

from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"
SQLITE_URL_PREFIX = "sqlite:///"


def create_incident_repository() -> IncidentRepositoryPort:
    """Selecciona el adaptador saliente a partir de DATABASE_URL.

    Formatos admitidos: una ruta directa (`/ruta/incidentops.db`), una URL
    SQLite (`sqlite:///ruta/incidentops.db`) o `sqlite:///:memory:`
    (default).
    """
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return SqliteIncidentRepository(_resolve_sqlite_path(database_url))


def _resolve_sqlite_path(database_url: str) -> str:
    if database_url.startswith(SQLITE_URL_PREFIX):
        return database_url[len(SQLITE_URL_PREFIX):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    return database_url

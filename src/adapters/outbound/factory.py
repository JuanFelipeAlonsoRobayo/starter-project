"""Punto de composición de los adaptantes salientes de IncidentOps."""

import os

from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"
SQLITE_URL_PREFIX = "sqlite:///"
POSTGRES_URL_PREFIXES = ("postgres://", "postgresql://")


def create_repository(database_url: str) -> IncidentRepositoryPort:
    """Selecciona el adaptante saliente según la URL.

    URLs PostgreSQL (`postgres://`/`postgresql://`) → `PostgresIncidentRepository`;
    el resto se resuelve como SQLite: una ruta directa (`/ruta/incidentops.db`),
    una URL SQLite (`sqlite:///ruta/incidentops.db`) o `sqlite:///:memory:`
    (default).
    """
    if database_url.startswith(POSTGRES_URL_PREFIXES):
        return PostgresIncidentRepository(database_url)
    return SqliteIncidentRepository(_resolve_sqlite_path(database_url))


def create_incident_repository() -> IncidentRepositoryPort:
    """Selecciona el adaptante saliente a partir de `DATABASE_URL` (wrapper de compatibilidad)."""
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_repository(database_url)


def _resolve_sqlite_path(database_url: str) -> str:
    if database_url.startswith(SQLITE_URL_PREFIX):
        return database_url[len(SQLITE_URL_PREFIX):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    return database_url

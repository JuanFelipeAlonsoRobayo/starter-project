"""Puertos secundarios de la aplicación IncidentOps."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from src.domain.models import Incident


class IncidentReadPort(Protocol):
    """Puerto de solo lectura para obtener los incidentes registrados."""

    def list_incidents(self) -> list[Incident]:
        """Devuelve todos los incidentes registrados, sin filtrar por estado."""
        ...


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Puerto de repositorio de incidentes y políticas de SLA definido por la aplicación.

    Supersedes a `IncidentReadPort` (cubre `list_incidents`); se verifica de
    forma dinámica con `isinstance` sobre el adaptante saliente.
    """

    def save_incident(
        self, incident: Incident, duplicate_group_key: str | None = None
    ) -> None:
        """Persiste un incidente (insert-or-replace); `duplicate_group_key` es forward-looking (H003)."""
        ...

    def get_incident(self, incident_id: str) -> Incident | None:
        """Devuelve el incidente por ID persistente, o None si no existe."""
        ...

    def find_open_duplicates(
        self, duplicate_group_key: str, created_at: datetime, exclude_incident_id: str | None = None
    ) -> list[Incident]:
        """Incidentes abiertos (OPEN/IN_PROGRESS) con el mismo grupo de duplicados creados antes de `created_at`; excluye el ID dado."""
        ...

    def list_active_incidents(
        self, reference_time: datetime, component: str | None = None
    ) -> list[Incident]:
        """Devuelve incidentes activos (OPEN/IN_PROGRESS); opcionalmente acotados a componente. El dominio refiltra/ordena."""
        ...

    def check_health(self) -> bool:
        """Verifica el estado de operación del adaptante saliente."""
        ...

    def list_incidents(self) -> list[Incident]:
        """Devuelve todos los incidentes (para la ruta de triaje)."""
        ...

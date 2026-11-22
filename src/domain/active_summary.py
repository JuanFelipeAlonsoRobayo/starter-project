"""Construcción determinista del resumen de incidentes activos."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Tuple, cast

from src.domain.models import ActiveIncidentStatus, Incident, SeverityLevel
from src.domain.sla_calculator import evaluate_sla_status

ACTIVE_STATUSES: frozenset[ActiveIncidentStatus] = frozenset({"OPEN", "IN_PROGRESS"})
SEVERITY_ORDER: dict[SeverityLevel, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass(frozen=True)
class ActiveIncidentDetail:
    """Detalle observable de un incidente activo en el instante de referencia."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: ActiveIncidentStatus
    elapsed_minutes: int
    is_breached: bool
    requires_escalation: bool


@dataclass(frozen=True)
class ActiveIncidentSummary:
    """Resumen determinista de los incidentes activos de un conjunto."""

    reference_time: datetime
    component: Optional[str]
    incidents: Tuple[ActiveIncidentDetail, ...]

    @property
    def total_active(self) -> int:
        """Cantidad de incidentes activos incluidos en el resumen."""
        return len(self.incidents)

    @property
    def breached_count(self) -> int:
        """Cantidad de incidentes activos que ya incumplieron su SLA."""
        return sum(1 for incident in self.incidents if incident.is_breached)


def normalize_component_filter(component: Optional[str]) -> Optional[str]:
    """Normaliza el filtro recortando espacios y comparando sin mayúsculas."""
    if component is None:
        return None
    normalized = component.strip().lower()
    return normalized or None


def build_active_incident_summary(
    incidents: Iterable[Incident],
    reference_time: datetime,
    component: Optional[str] = None,
) -> ActiveIncidentSummary:
    """Filtra, evalúa y ordena los incidentes activos en un instante de referencia.

    El instante debe ser naive, coherente con las marcas de tiempo almacenadas.
    El orden es severidad más crítica primero, luego el incidente más antiguo y,
    como desempate estable, el identificador ascendente.
    """
    if reference_time.tzinfo is not None:
        raise ValueError("reference_time debe ser una fecha sin zona horaria.")

    normalized_component = normalize_component_filter(component)
    selected = [
        incident
        for incident in incidents
        if incident.status in ACTIVE_STATUSES
        and (
            normalized_component is None
            or incident.component.strip().lower() == normalized_component
        )
    ]
    selected.sort(
        key=lambda incident: (
            SEVERITY_ORDER[incident.severity],
            incident.created_at,
            incident.incident_id,
        )
    )

    details = []
    for incident in selected:
        evaluation = evaluate_sla_status(incident, reference_time=reference_time)
        details.append(
            ActiveIncidentDetail(
                incident_id=incident.incident_id,
                title=incident.title,
                component=incident.component,
                severity=incident.severity,
                status=cast(ActiveIncidentStatus, incident.status),
                elapsed_minutes=evaluation.elapsed_minutes,
                is_breached=evaluation.is_breached,
                requires_escalation=evaluation.requires_escalation,
            )
        )

    return ActiveIncidentSummary(
        reference_time=reference_time,
        component=normalized_component,
        incidents=tuple(details),
    )

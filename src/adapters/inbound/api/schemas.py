"""Esquemas de transporte del adaptador HTTP de IncidentOps."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from src.domain.models import ActiveIncidentStatus, RecommendedTeam, SeverityLevel


class TriageRequest(BaseModel):
    """Cuerpo de entrada de POST /triage."""

    model_config = ConfigDict(extra="forbid")

    incident_id: str
    raw_text: str


class TriageResponse(BaseModel):
    """Objeto de salida compartido con el CLI."""

    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    rationale: str


class ActiveIncidentItem(BaseModel):
    """Detalle de un incidente activo dentro del resumen (sin `allowed_minutes`)."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: ActiveIncidentStatus
    elapsed_minutes: int
    is_breached: bool
    requires_escalation: bool


class ActiveIncidentSummaryResponse(BaseModel):
    """Objeto de salida compartido por HTTP y CLI para el resumen."""

    reference_time: str
    component: Optional[str]
    total_active: int
    breached_count: int
    incidents: List[ActiveIncidentItem]


class ErrorDetail(BaseModel):
    """Detalle estable de un error de transporte."""

    code: str
    message: str


class ErrorEnvelope(BaseModel):
    """Sobre único de errores HTTP y CLI."""

    error: ErrorDetail

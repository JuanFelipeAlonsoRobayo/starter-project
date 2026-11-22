"""Esquemas de transporte del adaptador HTTP de IncidentOps."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from src.domain.models import ActiveIncidentStatus, IncidentStatus, RecommendedTeam, SeverityLevel


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


class CreateIncidentRequest(BaseModel):
    """Cuerpo de entrada de POST /api/v1/incidents."""

    model_config = ConfigDict(extra="forbid")

    title: str
    raw_text: str
    incident_id: Optional[str] = None
    created_at: Optional[datetime] = None
    status: Optional[IncidentStatus] = None


class IncidentCreatedResponse(BaseModel):
    """Objeto de salida compartido con el CLI (creación)."""

    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    rationale: str
    is_duplicate: bool
    duplicate_of: List[str]


class SLAEvaluationResponse(BaseModel):
    """Objeto de salida compartido con el CLI (auditoría de SLA)."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool


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

"""Esquemas de transporte del adaptador HTTP de triaje."""

from pydantic import BaseModel, ConfigDict

from src.domain.models import RecommendedTeam, SeverityLevel


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


class ErrorDetail(BaseModel):
    """Detalle estable de un error de transporte."""

    code: str
    message: str


class ErrorEnvelope(BaseModel):
    """Sobre único de errores HTTP y CLI."""

    error: ErrorDetail

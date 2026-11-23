"""Casos de uso compartidos por los adaptadores de IncidentOps."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union, get_args
from uuid import uuid4

from src.application.ports import IncidentRepositoryPort
from src.domain.active_summary import (
    ActiveIncidentSummary,
    build_active_incident_summary,
    normalize_component_filter,
)
from src.domain.models import Incident, IncidentStatus, RecommendedTeam, SeverityLevel, TriageResult
from src.domain.sla_calculator import (
    ReferenceTimeBeforeCreationError,
    SLAEvaluation,
    evaluate_sla_status,
    to_naive_utc,
)
from src.domain.triage_rules import classify_incident_report

MAX_RAW_TEXT_LENGTH = 10_000


class ValidationError(Exception):
    """Error de validación de entrada con un código estable para los adaptadores."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IncidentCreationResult:
    """Resultado de la creación de un incidente: clasificación + flags de duplicado."""

    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    rationale: str
    is_duplicate: bool
    duplicate_of: List[str]


class IncidentNotFoundError(Exception):
    """El incidente solicitado no existe."""

    def __init__(self, incident_id: str) -> None:
        super().__init__(f"El incidente {incident_id} no existe.")
        self.incident_id = incident_id


class IncidentService:
    """Orquesta los casos de uso deterministas sin depender de frameworks ni de IO."""

    def __init__(self, incident_repository: Optional[IncidentRepositoryPort] = None) -> None:
        self._incident_repository = incident_repository

    def check_health(self) -> bool:
        """Verifica el estado de operación del repositorio saliente."""
        if self._incident_repository is None:
            return False
        return self._incident_repository.check_health()

    def create_incident(
        self,
        title: str,
        raw_text: str,
        incident_id: Optional[str] = None,
        created_at: Optional[Union[str, datetime]] = None,
        status: Optional[IncidentStatus] = None,
    ) -> IncidentCreationResult:
        """Registra un incidente nuevo y calcula su indicación de duplicado."""
        if not isinstance(title, str) or not title.strip():
            raise ValidationError("EMPTY_TITLE", "title no puede estar vacío.")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValidationError("EMPTY_RAW_TEXT", "raw_text no puede estar vacío.")

        clean_raw_text = raw_text.strip()
        if len(clean_raw_text) > MAX_RAW_TEXT_LENGTH:
            raise ValidationError(
                "RAW_TEXT_TOO_LONG",
                f"raw_text no puede superar {MAX_RAW_TEXT_LENGTH} caracteres.",
            )

        resolved_status: IncidentStatus = status if status else "OPEN"
        if resolved_status not in get_args(IncidentStatus):
            raise ValidationError("INVALID_STATUS", "status no es un estado válido.")

        resolved_id = (
            incident_id.strip()
            if incident_id and incident_id.strip()
            else f"INC-{uuid4().hex[:8]}"
        )
        resolved_created_at = self._resolve_creation_time(created_at)

        triage = classify_incident_report(resolved_id, clean_raw_text)
        incident = Incident(
            incident_id=resolved_id,
            title=title.strip(),
            component=triage.component,
            severity=triage.severity,
            status=resolved_status,
            created_at=resolved_created_at,
            duplicate_group_key=triage.duplicate_group_key,
            recommended_team=triage.recommended_team,
        )

        if self._incident_repository is None:
            raise RuntimeError("El registro requiere un repositorio de incidentes configurado.")
        self._incident_repository.save_incident(incident, triage.duplicate_group_key)

        duplicates = self._incident_repository.find_open_duplicates(
            duplicate_group_key=triage.duplicate_group_key,
            created_at=resolved_created_at,
            exclude_incident_id=resolved_id,
        )
        return IncidentCreationResult(
            incident_id=resolved_id,
            severity=triage.severity,
            component=triage.component,
            recommended_team=triage.recommended_team,
            duplicate_group_key=triage.duplicate_group_key,
            rationale=triage.rationale,
            is_duplicate=bool(duplicates),
            duplicate_of=[duplicate.incident_id for duplicate in duplicates],
        )

    def evaluate_incident_sla(
        self,
        incident_id: str,
        reference_time: Optional[Union[str, datetime]] = None,
    ) -> SLAEvaluation:
        """Audita el SLA de un incidente almacenado."""
        if self._incident_repository is None:
            raise RuntimeError("El SLA requiere un repositorio de incidentes configurado.")

        resolved_reference_time = self._resolve_audit_time(reference_time)
        incident = self._incident_repository.get_incident(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)

        try:
            return evaluate_sla_status(incident, resolved_reference_time)
        except ReferenceTimeBeforeCreationError as exc:
            raise ValidationError(
                "REFERENCE_TIME_BEFORE_CREATION",
                "reference_time no puede ser anterior a la creación del incidente.",
            ) from exc

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Valida el reporte y delega su clasificación en el dominio."""
        if not incident_id or not incident_id.strip():
            raise ValidationError("EMPTY_INCIDENT_ID", "incident_id no puede estar vacío.")

        clean_raw_text = raw_text.strip()
        if not clean_raw_text:
            raise ValidationError("EMPTY_RAW_TEXT", "raw_text no puede estar vacío.")

        if len(clean_raw_text) > MAX_RAW_TEXT_LENGTH:
            raise ValidationError(
                "RAW_TEXT_TOO_LONG",
                f"raw_text no puede superar {MAX_RAW_TEXT_LENGTH} caracteres.",
            )

        return classify_incident_report(incident_id=incident_id, raw_text=clean_raw_text)

    def summarize_active_incidents(
        self,
        component: Optional[str] = None,
        reference_time: Optional[Union[str, datetime]] = None,
    ) -> ActiveIncidentSummary:
        """Construye el resumen determinista de incidentes activos."""
        resolved_reference_time = self._resolve_reference_time(reference_time)

        if self._incident_repository is None:
            raise RuntimeError("El resumen requiere un repositorio de incidentes configurado.")

        try:
            incidents = self._incident_repository.list_incidents()
            return build_active_incident_summary(
                incidents=incidents,
                reference_time=resolved_reference_time,
                component=component,
            )
        except ReferenceTimeBeforeCreationError as exc:
            raise ValidationError(
                "REFERENCE_TIME_BEFORE_CREATION",
                "reference_time no puede ser anterior a la creación de un incidente activo.",
            ) from exc

    def get_active_incidents_summary(
        self,
        component_filter: Optional[str] = None,
        reference_time: Optional[Union[str, datetime]] = None,
    ) -> ActiveIncidentSummary:
        """Construye el resumen determinista de incidentes activos.

        Llamada al puerto `list_active_incidents` + dominio
        (`build_active_incident_summary`): SLA, orden y refiltro.
        """
        resolved_reference_time = self._resolve_reference_time(reference_time)

        if self._incident_repository is None:
            raise RuntimeError("El resumen requiere un repositorio de incidentes configurado.")

        try:
            incidents = self._incident_repository.list_active_incidents(
                reference_time=resolved_reference_time,
                component=normalize_component_filter(component_filter),
            )
            return build_active_incident_summary(
                incidents=incidents,
                reference_time=resolved_reference_time,
                component=component_filter,
            )
        except ReferenceTimeBeforeCreationError as exc:
            raise ValidationError(
                "REFERENCE_TIME_BEFORE_CREATION",
                "reference_time no puede ser anterior a la creación de un incidente activo.",
            ) from exc

    @staticmethod
    def _resolve_reference_time(
        value: Optional[Union[str, datetime]],
    ) -> datetime:
        """Normaliza el instante de referencia o falla con un código estable."""
        if value is None:
            return datetime.now().replace(microsecond=0)

        if isinstance(value, datetime):
            parsed = value
        else:
            raw_value = value.strip()
            if not raw_value:
                return datetime.now().replace(microsecond=0)
            try:
                parsed = datetime.fromisoformat(raw_value)
            except ValueError as exc:
                raise ValidationError(
                    "INVALID_REFERENCE_TIME",
                    "reference_time debe ser una fecha ISO-8601 válida sin zona horaria.",
                ) from exc

        if parsed.tzinfo is not None:
            raise ValidationError(
                "INVALID_REFERENCE_TIME",
                "reference_time debe ser una fecha ISO-8601 válida sin zona horaria.",
            )

        return parsed

    @staticmethod
    def _resolve_creation_time(value: Optional[Union[str, datetime]]) -> datetime:
        """Normaliza el instante de creación o falla con un código estable."""
        if value is None:
            return datetime.now().replace(microsecond=0)
        if isinstance(value, datetime):
            parsed = value
        else:
            raw_value = value.strip()
            if not raw_value:
                return datetime.now().replace(microsecond=0)
            try:
                parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValidationError(
                    "INVALID_CREATED_AT",
                    "created_at debe ser una fecha ISO-8601 válida.",
                ) from exc
        return to_naive_utc(parsed)

    @staticmethod
    def _resolve_audit_time(value: Optional[Union[str, datetime]]) -> datetime:
        """Normaliza el instante de auditoría (acepta naive o aware) o falla con un código estable."""
        if value is None:
            return datetime.now().replace(microsecond=0)
        if isinstance(value, datetime):
            parsed = value
        else:
            raw_value = value.strip()
            if not raw_value:
                return datetime.now().replace(microsecond=0)
            try:
                parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValidationError(
                    "INVALID_REFERENCE_TIME",
                    "reference_time debe ser una fecha ISO-8601 válida.",
                ) from exc
        return to_naive_utc(parsed)

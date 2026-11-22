"""Casos de uso compartidos por los adaptadores de IncidentOps."""

from src.domain.models import TriageResult
from src.domain.triage_rules import classify_incident_report

MAX_RAW_TEXT_LENGTH = 10_000


class ValidationError(Exception):
    """Error de validación de entrada con un código estable para los adaptadores."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class IncidentService:
    """Orquesta el triaje determinista sin depender de frameworks ni de IO."""

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

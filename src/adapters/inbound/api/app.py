"""Adaptador primario HTTP para incidentes de IncidentOps."""

from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import (
    ActiveIncidentItem,
    ActiveIncidentSummaryResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import create_incident_repository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService, ValidationError

VALIDATION_STATUS = {
    "EMPTY_INCIDENT_ID": 422,
    "EMPTY_RAW_TEXT": 422,
    "RAW_TEXT_TOO_LONG": 400,
    "INVALID_REFERENCE_TIME": 422,
    "REFERENCE_TIME_BEFORE_CREATION": 400,
}


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app(incident_repository: IncidentRepositoryPort | None = None) -> FastAPI:
    """Construye la aplicación HTTP como adaptador delgado sobre IncidentService."""
    app = FastAPI(title="IncidentOps API", version="0.1.0")
    repository = (
        incident_repository
        if incident_repository is not None
        else create_incident_repository()
    )
    service = IncidentService(incident_repository=repository)

    @app.middleware("http")
    async def require_json(request: Request, call_next: Any):
        if request.method == "POST" and request.url.path == "/triage":
            content_type = request.headers.get("content-type", "")
            if not content_type.lower().startswith("application/json"):
                return _error_response(
                    415,
                    "UNSUPPORTED_MEDIA_TYPE",
                    "El cuerpo debe enviarse como application/json.",
                )
        return await call_next(request)

    @app.post("/triage", response_model=TriageResponse)
    def triage(payload: TriageRequest) -> TriageResponse | JSONResponse:
        try:
            result = service.triage_incident(payload.incident_id, payload.raw_text)
        except ValidationError as exc:
            status_code = VALIDATION_STATUS.get(exc.code, 422)
            return _error_response(status_code, exc.code, exc.message)

        return TriageResponse(
            incident_id=result.incident_id,
            severity=result.severity,
            component=result.component,
            recommended_team=result.recommended_team,
            duplicate_group_key=result.duplicate_group_key,
            rationale=result.rationale,
        )

    @app.get(
        "/api/v1/incidents/summary",
        response_model=ActiveIncidentSummaryResponse,
    )
    def summary(
        component: str | None = Query(default=None),
        reference_time: str | None = Query(default=None),
    ) -> ActiveIncidentSummaryResponse | JSONResponse:
        """Devuelve el resumen determinista de incidentes activos."""
        try:
            result = service.get_active_incidents_summary(
                component_filter=component,
                reference_time=reference_time,
            )
        except ValidationError as exc:
            status_code = VALIDATION_STATUS.get(exc.code, 422)
            return _error_response(status_code, exc.code, exc.message)

        return ActiveIncidentSummaryResponse(
            reference_time=result.reference_time.isoformat(),
            component=result.component,
            total_active=result.total_active,
            breached_count=result.breached_count,
            incidents=[
                ActiveIncidentItem(
                    incident_id=incident.incident_id,
                    title=incident.title,
                    component=incident.component,
                    severity=incident.severity,
                    status=incident.status,
                    elapsed_minutes=incident.elapsed_minutes,
                    is_breached=incident.is_breached,
                    requires_escalation=incident.requires_escalation,
                )
                for incident in result.incidents
            ],
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,
            "INVALID_REQUEST",
            "La solicitud no cumple el esquema esperado.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(500, "INTERNAL_ERROR", "Error interno inesperado.")

    return app


app = create_app()

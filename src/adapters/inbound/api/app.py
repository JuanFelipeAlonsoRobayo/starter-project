"""Adaptador primario HTTP para el triaje de incidentes."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import TriageRequest, TriageResponse
from src.application.services import IncidentService, ValidationError

VALIDATION_STATUS = {
    "EMPTY_INCIDENT_ID": 422,
    "EMPTY_RAW_TEXT": 422,
    "RAW_TEXT_TOO_LONG": 400,
}


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app() -> FastAPI:
    """Construye la aplicación HTTP como adaptador delgado sobre IncidentService."""
    app = FastAPI(title="IncidentOps API", version="0.1.0")
    service = IncidentService()

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

"""Adaptador primario de línea de comandos para IncidentOps."""

import json
from typing import Any, Dict, Optional

import typer

from src.adapters.outbound.factory import create_incident_repository
from src.application.services import (
    IncidentCreationResult,
    IncidentNotFoundError,
    IncidentService,
    ValidationError,
)
from src.domain.active_summary import ActiveIncidentSummary
from src.domain.models import SLAEvaluation, TriageResult

app = typer.Typer(help="IncidentOps CLI")
service = IncidentService()


@app.callback()
def main() -> None:
    """CLI de IncidentOps."""



def _result_payload(result: TriageResult) -> Dict[str, Any]:
    return {
        "incident_id": result.incident_id,
        "severity": result.severity,
        "component": result.component,
        "recommended_team": result.recommended_team,
        "duplicate_group_key": result.duplicate_group_key,
        "rationale": result.rationale,
    }


def _summary_payload(summary: ActiveIncidentSummary) -> Dict[str, Any]:
    return {
        "reference_time": summary.reference_time.isoformat(),
        "component": summary.component,
        "total_active": summary.total_active,
        "breached_count": summary.breached_count,
        "incidents": [
            {
                "incident_id": incident.incident_id,
                "title": incident.title,
                "component": incident.component,
                "severity": incident.severity,
                "status": incident.status,
                "elapsed_minutes": incident.elapsed_minutes,
                "is_breached": incident.is_breached,
                "requires_escalation": incident.requires_escalation,
            }
            for incident in summary.incidents
        ],
    }


def _emit_error(code: str, message: str) -> None:
    typer.echo(
        json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=False),
        err=True,
    )


@app.command("triage")
def triage(
    incident_id: str = typer.Option(..., "--incident-id", help="Identificador del incidente."),
    raw_text: str = typer.Option(..., "--raw-text", help="Texto crudo del reporte."),
    human: bool = typer.Option(False, "--human", help="Presenta una salida legible."),
) -> None:
    """Clasifica un reporte y muestra su severidad, componente y equipo recomendado."""
    try:
        result = service.triage_incident(incident_id, raw_text)
    except ValidationError as exc:
        _emit_error(exc.code, exc.message)
        raise typer.Exit(code=2)
    except Exception:
        _emit_error("INTERNAL_ERROR", "Error interno inesperado.")
        raise typer.Exit(code=1)

    if human:
        typer.echo(f"Incidente: {result.incident_id}")
        typer.echo(f"Severidad: {result.severity}")
        typer.echo(f"Componente: {result.component}")
        typer.echo(f"Equipo: {result.recommended_team}")
        typer.echo(f"Clave de duplicado: {result.duplicate_group_key}")
        typer.echo(f"Motivo: {result.rationale}")
        return

    typer.echo(json.dumps(_result_payload(result), ensure_ascii=False))


@app.command("summary")
def summary(
    component: Optional[str] = typer.Option(
        None,
        "--component",
        help="Componente por el que filtrar el resumen.",
    ),
    reference_time: Optional[str] = typer.Option(
        None,
        "--reference-time",
        help="Instante ISO-8601 de evaluación del SLA.",
    ),
) -> None:
    """Muestra el resumen de incidentes activos y su estado de SLA."""
    try:
        summary_service = IncidentService(
            incident_repository=create_incident_repository()
        )
        result = summary_service.get_active_incidents_summary(
            component_filter=component,
            reference_time=reference_time,
        )
    except ValidationError as exc:
        _emit_error(exc.code, exc.message)
        raise typer.Exit(code=2)
    except Exception:
        _emit_error("INTERNAL_ERROR", "Error interno inesperado.")
        raise typer.Exit(code=1)

    typer.echo(json.dumps(_summary_payload(result), ensure_ascii=False))


@app.command("health")
def health() -> None:
    """Ejecuta `SELECT 1` real sobre la base configurada y muestra el estado de salud (per `contracts/health_endpoint_contract.md`)."""
    svc = IncidentService(incident_repository=create_incident_repository())
    if svc.check_health():
        typer.echo(json.dumps({"status": "ok", "database": "connected"}, ensure_ascii=False))
    else:
        typer.echo(json.dumps({"status": "error", "database": "unavailable"}, ensure_ascii=False))
        raise typer.Exit(code=1)


def _incident_created_payload(result: IncidentCreationResult) -> Dict[str, Any]:
    """Payload JSON de salida compartido entre HTTP y CLI (creación)."""
    return {
        "incident_id": result.incident_id,
        "severity": result.severity,
        "component": result.component,
        "recommended_team": result.recommended_team,
        "duplicate_group_key": result.duplicate_group_key,
        "rationale": result.rationale,
        "is_duplicate": result.is_duplicate,
        "duplicate_of": result.duplicate_of,
    }


def _sla_payload(result: SLAEvaluation) -> Dict[str, Any]:
    """Payload JSON de salida compartido entre HTTP y CLI (auditoría de SLA)."""
    return {
        "incident_id": result.incident_id,
        "severity": result.severity,
        "elapsed_minutes": result.elapsed_minutes,
        "allowed_minutes": result.allowed_minutes,
        "remaining_minutes": result.remaining_minutes,
        "is_breached": result.is_breached,
        "requires_escalation": result.requires_escalation,
    }


@app.command("create")
def create(
    title: str = typer.Option(..., "--title", help="Título del incidente."),
    raw_text: str = typer.Option(..., "--raw-text", help="Texto crudo del reporte original."),
    incident_id: Optional[str] = typer.Option(
        None, "--incident-id", help="Identificador (autogenerado si se omite)."
    ),
    created_at: Optional[str] = typer.Option(
        None, "--created-at", help="Instante ISO-8601 (default: ahora)."
    ),
    status: Optional[str] = typer.Option(
        None, "--status", help="Estado del incidente (default: OPEN)."
    ),
) -> None:
    """Registra un incidente nuevo y muestra su clasificación y duplicados."""
    svc = IncidentService(incident_repository=create_incident_repository())
    try:
        result = svc.create_incident(
            title=title,
            raw_text=raw_text,
            incident_id=incident_id,
            created_at=created_at,
            status=status,
        )
    except ValidationError as exc:
        _emit_error(exc.code, exc.message)
        raise typer.Exit(code=1)
    except Exception:
        _emit_error("INTERNAL_ERROR", "Error interno inesperado.")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(_incident_created_payload(result), ensure_ascii=False))


@app.command("sla")
def sla(
    incident_id: str = typer.Option(..., "--incident-id", help="Identificador del incidente."),
    reference_time: Optional[str] = typer.Option(
        None,
        "--reference-time",
        help="Instante ISO-8601 de evaluación del SLA (default: ahora).",
    ),
) -> None:
    """Muestra la auditoría de SLA de un incidente almacenado."""
    svc = IncidentService(incident_repository=create_incident_repository())
    try:
        result = svc.evaluate_incident_sla(
            incident_id=incident_id,
            reference_time=reference_time,
        )
    except IncidentNotFoundError:
        _emit_error("INCIDENT_NOT_FOUND", f"El incidente {incident_id} no existe.")
        raise typer.Exit(code=2)
    except ValidationError as exc:
        _emit_error(exc.code, exc.message)
        raise typer.Exit(code=1)
    except Exception:
        _emit_error("INTERNAL_ERROR", "Error interno inesperado.")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(_sla_payload(result), ensure_ascii=False))


if __name__ == "__main__":
    app()

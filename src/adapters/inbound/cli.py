"""Adaptador primario de línea de comandos para el triaje de incidentes."""

import json
from typing import Any, Dict

import typer

from src.application.services import IncidentService, ValidationError
from src.domain.models import TriageResult

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


if __name__ == "__main__":
    app()

"""Escenarios BDD H003: lifecycle — creación de incidentes, duplicados y auditoría de SLA.

Ver spec.md — Escenarios BDD de aceptación (specs/003-save-incidents-sla/spec.md).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app

CREATION_PATH = "/api/v1/incidents"
CREATION_KEYS = {
    "incident_id",
    "severity",
    "component",
    "recommended_team",
    "duplicate_group_key",
    "rationale",
    "is_duplicate",
    "duplicate_of",
}
SLA_KEYS = {
    "incident_id",
    "severity",
    "elapsed_minutes",
    "allowed_minutes",
    "remaining_minutes",
    "is_breached",
    "requires_escalation",
}


def _http_client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Cliente HTTP sobre una instancia compartida de SqliteIncidentRepository."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return TestClient(create_app())


def test_bdd_creation_without_previous_duplicates(api_client: TestClient) -> None:
    """Escenario 1 — Registro inicial sin duplicados previos."""
    response = api_client.post(
        CREATION_PATH,
        json={
            "title": "Pasarela de pagos devuelve 502 al cobrar",
            "raw_text": "La pasarela de pagos devuelve 502 al cobrar",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == CREATION_KEYS
    assert body["is_duplicate"] is False
    assert body["duplicate_of"] == []


def test_bdd_creation_detects_open_duplicate(api_client: TestClient) -> None:
    """Escenario 2 — Detección de duplicado abierto en la creación."""
    # Given que hay un incidente abierto equivalente registrado
    first = api_client.post(
        CREATION_PATH,
        json={
            "title": "Pasarela de pagos devuelve 502 al cobrar",
            "raw_text": "La pasarela de pagos devuelve 502 al cobrar",
        },
    )
    assert first.status_code == 201
    open_id = first.json()["incident_id"]

    # And que existe un incidente equivalente con status RESOLVED
    resolved = api_client.post(
        CREATION_PATH,
        json={
            "title": "Pasarela de pagos devuelve 502 al cobrar",
            "raw_text": "La pasarela de pagos devuelve 502 al cobrar",
            "status": "RESOLVED",
        },
    )
    assert resolved.status_code == 201

    # When se crea un incidente nuevo equivalente
    new = api_client.post(
        CREATION_PATH,
        json={
            "title": "Pasarela de pagos devuelve 502 al cobrar",
            "raw_text": "La pasarela de pagos devuelve 502 al cobrar",
        },
    )
    # Then responde 201
    assert new.status_code == 201
    body = new.json()
    # And la respuesta de creación incluye is_duplicate true
    assert body["is_duplicate"] is True
    # And duplicate_of incluye el incident_id del incidente equivalente abierto
    assert open_id in body["duplicate_of"]
    # And duplicate_of no incluye incidentes RESOLVED
    assert resolved.json()["incident_id"] not in body["duplicate_of"]


def test_bdd_sla_audit_business_hours_deterministic(api_client: TestClient) -> None:
    """Escenario 3 — Auditoría deterministica de SLA en horario hábil."""
    created = api_client.post(
        CREATION_PATH,
        json={
            "title": "Exports Lentos",
            "raw_text": "La exportación de reportes es lenta: más de 10,000 registros, tarda unos segundos.",
            "created_at": "2026-11-06T17:00:00",
        },
    )
    assert created.status_code == 201
    incident_id = created.json()["incident_id"]
    assert created.json()["severity"] == "P2"

    response = api_client.get(
        f"/api/v1/incidents/{incident_id}/sla",
        params={"reference_time": "2026-11-09T09:00:00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == SLA_KEYS
    assert body["elapsed_minutes"] == 120
    assert body["allowed_minutes"] == 480
    assert body["remaining_minutes"] == 360
    assert body["is_breached"] is False
    assert body["requires_escalation"] is False


def test_bdd_sla_audit_not_found_and_before_creation(api_client: TestClient) -> None:
    """Escenario 4 — Consulta de SLA para ID inexistente y tiempo anterior a creación."""
    response = api_client.get("/api/v1/incidents/INC-NONE/sla")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INCIDENT_NOT_FOUND"

    created = api_client.post(
        CREATION_PATH,
        json={
            "title": "Incidente del futuro",
            "raw_text": "Algo sucede",
            "created_at": "2026-11-09T10:00:00",
        },
    )
    assert created.status_code == 201
    incident_id = created.json()["incident_id"]

    response = api_client.get(
        f"/api/v1/incidents/{incident_id}/sla",
        params={"reference_time": "2026-11-09T09:00:00"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REFERENCE_TIME_BEFORE_CREATION"


def test_bdd_cli_create_and_sla_equivalent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: CliRunner,
) -> None:
    """Escenario 5 — Operación equivalente mediante los comandos CLI create y sla."""
    client = _http_client(tmp_path / "lifecycle.db", monkeypatch)

    create_result = cli_runner.invoke(
        cli_app,
        [
            "create",
            "--title",
            "Exports Lentos",
            "--raw-text",
            "La exportación de reportes es lenta: más de 10,000 registros, tarda unos segundos.",
            "--created-at",
            "2026-11-06T17:00:00",
        ],
    )
    assert create_result.exit_code == 0, create_result.output
    create_payload = json.loads(create_result.stdout)
    assert set(create_payload.keys()) == CREATION_KEYS
    assert create_payload["severity"] == "P2"
    assert create_payload["is_duplicate"] is False
    assert create_payload["duplicate_of"] == []
    incident_id = create_payload["incident_id"]

    reference_time = "2026-11-09T09:00:00"
    http_response = client.get(
        f"/api/v1/incidents/{incident_id}/sla",
        params={"reference_time": reference_time},
    )
    assert http_response.status_code == 200
    sla_result = cli_runner.invoke(
        cli_app,
        ["sla", "--incident-id", incident_id, "--reference-time", reference_time],
    )
    assert sla_result.exit_code == 0, sla_result.output
    assert json.loads(sla_result.stdout) == http_response.json()

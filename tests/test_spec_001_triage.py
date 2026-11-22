"""Pruebas de aceptación BDD para H001 (specs/001-triage-endpoint-manual.md)."""

import json

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from src.adapters.inbound.cli import app as cli_app


def test_scenario_1_http_502_payments_outage_classified_as_p0(api_client: TestClient) -> None:
    """Escenario 1 — Caída crítica HTTP 502 en pasarela de pagos."""
    payload = {
        "incident_id": "INC-1000",
        "raw_text": "La pasarela de pagos devuelve 502 al intentar cobrar con tarjeta",
    }

    response = api_client.post("/triage", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "incident_id",
        "severity",
        "component",
        "recommended_team",
        "duplicate_group_key",
        "rationale",
    }
    assert body["incident_id"] == "INC-1000"
    assert body["severity"] == "P0"
    assert body["component"] == "payments-gateway"
    assert body["recommended_team"] == "Backend-Core"
    assert body["duplicate_group_key"] == "payments-gateway:http-502-outage"


def test_scenario_2_http_locked_account_mentioning_hoy_is_p2_not_p0(
    api_client: TestClient,
) -> None:
    """Escenario 2 — Cuenta individual bloqueada mencionando 'hoy'."""
    payload = {
        "incident_id": "INC-1002",
        "raw_text": "Mi cuenta está bloqueada y necesito ingresar hoy",
    }

    response = api_client.post("/triage", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == "INC-1002"
    assert body["severity"] == "P2"
    assert body["severity"] != "P0"
    assert body["component"] == "auth-identity"
    assert body["recommended_team"] == "Security-IAM"
    assert body["duplicate_group_key"] == "auth-identity:account-lockout"


@pytest.mark.parametrize(
    ("incident_id", "raw_text", "expected_code"),
    [
        ("INC-1003", " ", "EMPTY_RAW_TEXT"),
        ("", "La pasarela de pagos devuelve 502", "EMPTY_INCIDENT_ID"),
    ],
)
def test_scenario_3_http_rejects_empty_or_whitespace_inputs(
    api_client: TestClient,
    incident_id: str,
    raw_text: str,
    expected_code: str,
) -> None:
    """Escenario 3 — Entradas vacías o con solo espacios."""
    response = api_client.post(
        "/triage",
        json={"incident_id": incident_id, "raw_text": raw_text},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == expected_code
    if raw_text.strip():
        assert raw_text not in response.text


def test_scenario_4_cli_parity_with_http(
    api_client: TestClient,
    cli_runner: CliRunner,
) -> None:
    """Escenario 4 — Paridad del CLI con HTTP."""
    incident_id = "INC-1001"
    raw_text = "La pasarela de pagos devuelve 502 al intentar cobrar con tarjeta"

    cli_result = cli_runner.invoke(
        cli_app,
        ["triage", "--incident-id", incident_id, "--raw-text", raw_text],
    )

    assert cli_result.exit_code == 0
    cli_payload = json.loads(cli_result.stdout)
    assert cli_payload["incident_id"] == incident_id
    assert cli_payload["severity"] == "P0"
    assert cli_payload["component"] == "payments-gateway"
    assert cli_payload["recommended_team"] == "Backend-Core"
    assert cli_payload["duplicate_group_key"] == "payments-gateway:http-502-outage"

    http_response = api_client.post(
        "/triage",
        json={"incident_id": incident_id, "raw_text": raw_text},
    )
    assert http_response.status_code == 200
    assert cli_payload == http_response.json()

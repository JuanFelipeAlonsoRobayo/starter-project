"""Pruebas de aceptación BDD para H002 (specs/002-active-incident-summary/spec.md)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService, ValidationError
from src.domain.models import Incident

REFERENCE_TIME = "2026-11-20T12:00:00"
SUMMARY_PATH = "/api/v1/incidents/summary"
SUMMARY_KEYS = {
    "reference_time",
    "component",
    "total_active",
    "breached_count",
    "incidents",
}
INCIDENT_KEYS = {
    "incident_id",
    "title",
    "component",
    "severity",
    "status",
    "elapsed_minutes",
    "is_breached",
    "requires_escalation",
}


def _seed_database(db_path: Path, incidents: Iterable[Incident]) -> None:
    repository = SqliteIncidentRepository(str(db_path))
    repository.seed_incidents(incidents)
    repository.close()


def _http_client(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    return TestClient(create_app())


def _scenario_1_incidents() -> List[Incident]:
    return [
        Incident(
            incident_id="INC-3001",
            title="La pasarela de pagos devuelve 502 al cobrar",
            component="payments-gateway",
            severity="P0",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 10, 0, 0),
        ),
        Incident(
            incident_id="INC-3002",
            title="Autenticación intermitente",
            component="auth-identity",
            severity="P1",
            status="IN_PROGRESS",
            created_at=datetime(2026, 11, 20, 9, 0, 0),
        ),
        Incident(
            incident_id="INC-3003",
            title="Exportación de reportes lenta",
            component="reporting-api",
            severity="P2",
            status="RESOLVED",
            created_at=datetime(2026, 11, 20, 8, 0, 0),
            resolved_at=datetime(2026, 11, 20, 8, 30, 0),
        ),
        Incident(
            incident_id="INC-3004",
            title="Conexiones agotadas en base de datos",
            component="database-cluster",
            severity="P0",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 11, 0, 0),
        ),
    ]


def _scenario_2_incidents() -> List[Incident]:
    return [
        Incident(
            incident_id="INC-3101",
            title="La pasarela de pagos devuelve 502 al cobrar",
            component="payments-gateway",
            severity="P0",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 10, 30, 0),
        ),
        Incident(
            incident_id="INC-3102",
            title="Confirmación de pagos lenta",
            component="payments-gateway",
            severity="P2",
            status="IN_PROGRESS",
            created_at=datetime(2026, 11, 20, 10, 0, 0),
        ),
        Incident(
            incident_id="INC-3103",
            title="Autenticación intermitente",
            component="auth-identity",
            severity="P1",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 8, 0, 0),
        ),
    ]


def test_bdd_global_summary_excludes_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escenario 1 — El resumen global excluye los incidentes resueltos."""
    _seed_database(tmp_path / "incidents.db", _scenario_1_incidents())
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(SUMMARY_PATH, params={"reference_time": REFERENCE_TIME})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == SUMMARY_KEYS
    assert body["reference_time"] == REFERENCE_TIME
    assert body["component"] is None
    assert body["total_active"] == 3
    assert body["breached_count"] == 1
    assert [incident["incident_id"] for incident in body["incidents"]] == [
        "INC-3001",
        "INC-3004",
        "INC-3002",
    ]
    assert all(incident["status"] != "RESOLVED" for incident in body["incidents"])
    assert all(set(incident.keys()) == INCIDENT_KEYS for incident in body["incidents"])

    first_incident = body["incidents"][0]
    assert first_incident["elapsed_minutes"] == 120
    assert first_incident["is_breached"] is True
    assert first_incident["requires_escalation"] is True


def test_bdd_summary_filtered_by_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escenario 2 — El resumen se acota al componente solicitado."""
    _seed_database(tmp_path / "incidents.db", _scenario_2_incidents())
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(
        SUMMARY_PATH,
        params={"component": "Payments-Gateway", "reference_time": REFERENCE_TIME},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["component"] == "payments-gateway"
    assert body["total_active"] == 2
    assert body["breached_count"] == 1
    assert [incident["incident_id"] for incident in body["incidents"]] == [
        "INC-3101",
        "INC-3102",
    ]

    first_incident = body["incidents"][0]
    assert first_incident["elapsed_minutes"] == 90
    assert first_incident["is_breached"] is True
    assert first_incident["requires_escalation"] is True

    second_incident = body["incidents"][1]
    assert second_incident["elapsed_minutes"] == 120
    assert second_incident["is_breached"] is False
    assert second_incident["requires_escalation"] is False


@pytest.mark.parametrize(
    ("incidents", "params"),
    [
        (
            [
                Incident(
                    incident_id="INC-3201",
                    title="Reporte resuelto",
                    component="payments-gateway",
                    severity="P2",
                    status="RESOLVED",
                    created_at=datetime(2026, 11, 20, 10, 0, 0),
                    resolved_at=datetime(2026, 11, 20, 10, 30, 0),
                ),
                Incident(
                    incident_id="INC-3202",
                    title="Autenticación resuelta",
                    component="auth-identity",
                    severity="P3",
                    status="RESOLVED",
                    created_at=datetime(2026, 11, 20, 9, 0, 0),
                    resolved_at=datetime(2026, 11, 20, 9, 30, 0),
                ),
            ],
            {"reference_time": REFERENCE_TIME},
        ),
        (
            [
                Incident(
                    incident_id="INC-3301",
                    title="Pago activo",
                    component="payments-gateway",
                    severity="P0",
                    status="OPEN",
                    created_at=datetime(2026, 11, 20, 11, 0, 0),
                ),
            ],
            {"component": "auth-identity", "reference_time": REFERENCE_TIME},
        ),
    ],
)
def test_bdd_empty_summary_is_successful(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    incidents: List[Incident],
    params: dict,
) -> None:
    """Escenario 3 — El resumen vacío es una respuesta exitosa."""
    _seed_database(tmp_path / "incidents.db", incidents)
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(SUMMARY_PATH, params=params)

    assert response.status_code == 200
    body = response.json()
    assert body["component"] == params.get("component")
    assert body["total_active"] == 0
    assert body["breached_count"] == 0
    assert body["incidents"] == []


def test_bdd_cli_parity_with_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escenario 4 — El CLI devuelve el mismo resumen que HTTP."""
    _seed_database(tmp_path / "incidents.db", _scenario_2_incidents())
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    http_response = client.get(
        SUMMARY_PATH,
        params={"component": "payments-gateway", "reference_time": REFERENCE_TIME},
    )
    assert http_response.status_code == 200

    cli_result = CliRunner().invoke(
        cli_app,
        [
            "summary",
            "--component",
            "payments-gateway",
            "--reference-time",
            REFERENCE_TIME,
        ],
    )

    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout) == http_response.json()


@pytest.mark.parametrize(
    "reference_time",
    [
        "no-es-fecha",
        "2026-02-30T10:00:00",
        "2026-11-20T12:00:00Z",
        "2026-11-20T12:00:00+00:00",
    ],
)
def test_contract_invalid_reference_time_returns_422(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference_time: str,
) -> None:
    """Contrato — Una fecha inválida se rechaza con un código estable."""
    _seed_database(tmp_path / "incidents.db", _scenario_2_incidents())
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(SUMMARY_PATH, params={"reference_time": reference_time})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REFERENCE_TIME"


def test_contract_reference_time_before_creation_returns_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato — El instante anterior a la creación no produce valores inventados."""
    _seed_database(
        tmp_path / "incidents.db",
        [
            Incident(
                incident_id="INC-3401",
                title="Incidente del futuro",
                component="payments-gateway",
                severity="P0",
                status="OPEN",
                created_at=datetime(2026, 11, 20, 12, 0, 0),
            )
        ],
    )
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(
        SUMMARY_PATH,
        params={"reference_time": "2026-11-20T11:00:00"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REFERENCE_TIME_BEFORE_CREATION"


def test_contract_cli_invalid_reference_time_exits_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato — El CLI traduce la fecha inválida a código de salida 2."""
    monkeypatch.setenv("DATABASE_URL", ":memory:")

    cli_result = CliRunner().invoke(
        cli_app,
        ["summary", "--reference-time", "no-es-fecha"],
    )

    assert cli_result.exit_code == 2
    assert json.loads(cli_result.stderr)["error"]["code"] == "INVALID_REFERENCE_TIME"


def test_contract_blank_component_means_no_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato — Un componente en blanco equivale a no filtrar."""
    _seed_database(tmp_path / "incidents.db", _scenario_1_incidents())
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(
        SUMMARY_PATH,
        params={"component": "   ", "reference_time": REFERENCE_TIME},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["component"] is None
    assert body["total_active"] == 3


def test_contract_escalation_required_status_is_not_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato — `ESCALATION_REQUIRED` no se almacena como estado activo."""
    _seed_database(
        tmp_path / "incidents.db",
        [
            Incident(
                incident_id="INC-3601",
                title="Incidente con escalamiento almacenado",
                component="payments-gateway",
                severity="P0",
                status="ESCALATION_REQUIRED",
                created_at=datetime(2026, 11, 20, 10, 0, 0),
            )
        ],
    )
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(SUMMARY_PATH, params={"reference_time": REFERENCE_TIME})

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 0
    assert body["breached_count"] == 0
    assert body["incidents"] == []


def test_contract_breach_and_escalation_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato — El límite exacto no incumple; el 75 % sí escala."""
    _seed_database(
        tmp_path / "incidents.db",
        [
            Incident(
                incident_id="INC-3701",
                title="Exactamente en el límite P0",
                component="payments-gateway",
                severity="P0",
                status="OPEN",
                created_at=datetime(2026, 11, 20, 11, 0, 0),
            ),
            Incident(
                incident_id="INC-3702",
                title="Un minuto por encima del límite P0",
                component="payments-gateway",
                severity="P0",
                status="OPEN",
                created_at=datetime(2026, 11, 20, 10, 59, 0),
            ),
        ],
    )
    client = _http_client(tmp_path / "incidents.db", monkeypatch)

    response = client.get(SUMMARY_PATH, params={"reference_time": REFERENCE_TIME})

    assert response.status_code == 200
    body = response.json()
    incidents = {incident["incident_id"]: incident for incident in body["incidents"]}
    assert incidents["INC-3701"]["elapsed_minutes"] == 60
    assert incidents["INC-3701"]["is_breached"] is False
    assert incidents["INC-3701"]["requires_escalation"] is True
    assert incidents["INC-3702"]["elapsed_minutes"] == 61
    assert incidents["INC-3702"]["is_breached"] is True
    assert incidents["INC-3702"]["requires_escalation"] is True
    assert body["breached_count"] == 1


def test_contract_cli_empty_summary_exits_0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato — El estado vacío también es exitoso por CLI."""
    _seed_database(
        tmp_path / "incidents.db",
        [
            Incident(
                incident_id="INC-3501",
                title="Incidente resuelto",
                component="payments-gateway",
                severity="P2",
                status="RESOLVED",
                created_at=datetime(2026, 11, 20, 10, 0, 0),
                resolved_at=datetime(2026, 11, 20, 10, 30, 0),
            )
        ],
    )
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'incidents.db'}")

    cli_result = CliRunner().invoke(
        cli_app,
        ["summary", "--reference-time", REFERENCE_TIME],
    )

    assert cli_result.exit_code == 0
    body = json.loads(cli_result.stdout)
    assert body["total_active"] == 0
    assert body["breached_count"] == 0
    assert body["incidents"] == []


def test_port_compliance_over_sqlite_repository() -> None:
    """Port — SqliteIncidentRepository cumple IncidentRepositoryPort (runtime_checkable)."""
    repository = SqliteIncidentRepository(":memory:")
    assert isinstance(repository, IncidentRepositoryPort)
    assert repository.check_health() is True


def test_repository_save_get_and_find_open_duplicates() -> None:
    """Port — save_incident/get_incident/find_open_duplicates y índice compuesto (component, status)."""
    repository = SqliteIncidentRepository(":memory:")
    incident = Incident(
        incident_id="INC-5001",
        title="Reporte de backup fallido",
        component="payments-gateway",
        severity="P0",
        status="OPEN",
        created_at=datetime(2026, 11, 20, 10, 0, 0),
    )
    repository.save_incident(incident)
    assert repository.get_incident("INC-5001") == incident
    assert repository.get_incident("INC-9999") is None

    indexes = [row[1] for row in repository.conn.execute("PRAGMA index_list(incidents)")]
    assert "idx_incidents_component_status" in indexes
    columns = [
        row[2]
        for row in repository.conn.execute("PRAGMA index_info('idx_incidents_component_status')")
    ]
    assert columns == ["component", "status"]
    assert repository.find_open_duplicates("KEY", datetime(2030, 1, 1)) == []


def test_list_active_incidents_status_and_component_filter() -> None:
    """Port — list_active_incidents incluye activos, excluye RESOLVED/ESCALATION_REQUIRED
    y aplica el filtro por componente normalizado (trim + case, blanco = sin filtro)."""
    repository = SqliteIncidentRepository(":memory:")
    repository.seed_incidents(
        [
            Incident(
                incident_id="INC-5101",
                title="Payments gateway down",
                component="payments-gateway",
                severity="P0",
                status="OPEN",
                created_at=datetime(2026, 11, 20, 10, 0, 0),
            ),
            Incident(
                incident_id="INC-5102",
                title="Auth flaky",
                component="auth-identity",
                severity="P2",
                status="IN_PROGRESS",
                created_at=datetime(2026, 11, 20, 9, 0, 0),
            ),
            Incident(
                incident_id="INC-5103",
                title="Payments slow",
                component="payments-gateway",
                severity="P2",
                status="RESOLVED",
                created_at=datetime(2026, 11, 20, 8, 0, 0),
                resolved_at=datetime(2026, 11, 20, 8, 30, 0),
            ),
            Incident(
                incident_id="INC-5104",
                title="Incidente con escalamiento",
                component="payments-gateway",
                severity="P0",
                status="ESCALATION_REQUIRED",
                created_at=datetime(2026, 11, 20, 10, 0, 0),
            ),
        ]
    )
    reference_time = datetime(2026, 11, 20, 12, 0, 0)

    active_all = repository.list_active_incidents(reference_time=reference_time)
    assert {incident.incident_id for incident in active_all} == {"INC-5101", "INC-5102"}

    filtered = repository.list_active_incidents(
        reference_time=reference_time, component="  PAYMENTS-GATEWAY  "
    )
    assert [incident.incident_id for incident in filtered] == ["INC-5101"]

    no_matches = repository.list_active_incidents(reference_time=reference_time, component="no-match")
    assert no_matches == []


def test_service_get_active_incidents_summary_uses_port_and_maps_errors() -> None:
    """Service — get_active_incidents_summary orquesta el puerto y preserva
    REFERENCE_TIME_BEFORE_CREATION."""
    repository = SqliteIncidentRepository(":memory:")
    repository.save_incident(
        Incident(
            incident_id="INC-5201",
            title="Deshacer",
            component="payments-gateway",
            severity="P0",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 10, 0, 0),
        )
    )
    service = IncidentService(incident_repository=repository)

    summary = service.get_active_incidents_summary(
        component_filter="Payments-Gateway",
        reference_time="2026-11-20T12:00:00",
    )
    assert summary.total_active == 1
    assert summary.incidents[0].incident_id == "INC-5201"

    with pytest.raises(ValidationError) as excinfo:
        service.get_active_incidents_summary(reference_time="2026-11-20T09:00:00")
    assert excinfo.value.code == "REFERENCE_TIME_BEFORE_CREATION"

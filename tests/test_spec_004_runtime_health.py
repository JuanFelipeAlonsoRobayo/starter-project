"""Pruebas BDD del runtime de salud — Hito 004 (specs/004-postgres-container-runtime/spec.md).

Escenarios BDD:
1. Chequeo de salud real mediante endpoint HTTP y comando CLI.
2. Chequeo de salud ante fallo de conectividad.
3. Selección transparente del motor SQLite/PostgreSQL vía `DATABASE_URL`.
4. Orquestación reproducible en 2 contenedores (api + db).
"""

import json
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_incident_repository, create_repository
from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.application.ports import IncidentRepositoryPort

REPO_ROOT = Path(__file__).resolve().parents[1]


def _double_unavailable() -> mock.Mock:
    """Doble: puerto cumpliente pero `check_health()` retorna False (fallo de conectividad)."""
    double = mock.Mock(spec=IncidentRepositoryPort)
    double.check_health.return_value = False
    return double


def test_health_ok_http_and_cli() -> None:
    """Escenario BDD 1: `GET /health` → 200 `{"status":"ok","database":"connected"}`; CLI `health` → JSON con `SELECT 1` real sobre la base configurada."""
    client = TestClient(create_app(SqliteIncidentRepository(":memory:")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}

    result = CliRunner().invoke(cli_app, ["health"], env={"DATABASE_URL": "sqlite:///:memory:"})
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "ok", "database": "connected"}


def test_health_unavailable_http() -> None:
    """Escenario BDD 2: `GET /health` → 503 `{"status":"error","database":"unavailable"}` ante fallo de conectividad."""
    client = TestClient(create_app(_double_unavailable()))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_health_unavailable_cli() -> None:
    """Escenario BDD 2 (CLI): comando `health` → JSON `{"status":"error","database":"unavailable"}`, exit 1."""
    with mock.patch(
        "src.adapters.inbound.cli.create_incident_repository",
        return_value=_double_unavailable(),
    ):
        result = CliRunner().invoke(cli_app, ["health"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"status": "error", "database": "unavailable"}


def test_create_repository_dual_selection(tmp_path: Path) -> None:
    """Escenario BDD 3: selección transparente SQLite/PostgreSQL vía `DATABASE_URL`."""
    assert isinstance(create_repository("sqlite:///:memory:"), SqliteIncidentRepository)
    assert isinstance(create_repository(f"sqlite:///{tmp_path}/incidentops.db"), SqliteIncidentRepository)
    assert isinstance(create_incident_repository(), SqliteIncidentRepository)
    assert issubclass(PostgresIncidentRepository, IncidentRepositoryPort)
    with mock.patch("psycopg.connect", return_value=mock.Mock()):
        assert isinstance(
            create_repository("postgresql://incidentops:incidentops@db:5432/incidentops"),
            PostgresIncidentRepository,
        )


def test_docker_compose_structure() -> None:
    """Escenario BDD 4: Orquestación reproducible en 2 contenedores (`api` + `db`) con `docker-compose.yml` (`db` `postgres:16-alpine`, volumen, `pg_isready`; `api` con `DATABASE_URL`, `depends_on: service_healthy`, healthcheck sobre `/health`)."""
    assert (REPO_ROOT / "Dockerfile").is_file()
    assert (REPO_ROOT / ".dockerignore").is_file()
    assert (REPO_ROOT / "docker-compose.yml").is_file()
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "services:" in compose
    assert "db:" in compose and "api:" in compose
    assert "image: postgres:16-alpine" in compose
    assert "depends_on:" in compose
    assert "condition: service_healthy" in compose
    assert "pg_isready" in compose
    assert "/health" in compose

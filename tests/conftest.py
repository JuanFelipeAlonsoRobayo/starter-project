"""Fixtures compartidos para las pruebas de aceptación BDD de IncidentOps."""

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app


@pytest.fixture()
def api_client() -> TestClient:
    """Cliente HTTP en proceso sobre el adaptador FastAPI."""
    return TestClient(create_app())


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Ejecutor en proceso para el adaptador CLI de Typer."""
    return CliRunner()

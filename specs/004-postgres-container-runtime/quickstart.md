# Quickstart — Servicio en contenedores con base de datos dedicada y chequeo de salud

## Puertas de calidad (solo cambio de comportamiento => puertas del hito)

```bash
uv run ruff check src/                    # sin errores (Constitución IV)
uv run pytest -q                          # incluye tests/test_spec_004_runtime_health.py
```

## Escenarios de validación ejecutables

### Scenario A: despliegue en contenedores y chequeo de salud real (HTTP)

```bash
docker compose up -d --wait                                   # db (postgres:16-alpine) + api
curl -s http://localhost:8000/health
# expect: {"status":"ok","database":"connected"} (200 OK)
```

### Scenario B: doble de prueba — chequeo ante fallo de conectividad

```bash
uv run python -m pytest tests/test_spec_004_runtime_health.py -v
# BDD RNF-002: /health -> 503 {"status":"error","database":"unavailable"} con doble (check_health False)
```

### Scenario C: selección dual SQLite/PostgreSQL via `DATABASE_URL`

```bash
uv run python - <<'PY'
from src.adapters.outbound.factory import create_repository, create_incident_repository
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.application.ports import IncidentRepositoryPort

assert isinstance(create_repository("sqlite:///:memory:"), SqliteIncidentRepository)
assert issubclass(PostgresIncidentRepository, IncidentRepositoryPort)
assert isinstance(create_incident_repository(), SqliteIncidentRepository)  # default sin DATABASE_URL
print("dual selection OK")
PY
```

### Scenario D: CLI `health`

```bash
uv run python -m src.adapters.inbound.cli health
# stdout: {"status":"ok","database":"connected"}; exit 0
```

### Scenario E: estructura de archivos Docker

```bash
test -f Dockerfile && test -f .dockerignore && test -f docker-compose.yml && echo "docker files OK"
```

## Actualización recomendada (AGENTS.md)

Al cerrar este hito, AGENTS.md debe reflejar:

- `DATABASE_URL` formas aceptadas (dual: `postgresql://` → PostgreSQL; `sqlite:///`/ruta/absenta → SQLite).
- `create_repository(database_url) -> IncidentRepositoryPort` (nuevo); `create_incident_repository()` compat.
- `IncidentService.check_health() -> bool` (nuevo); `GET /health` y comando `health` (chequeo real, 200/503).
- Puertas nuevas: `uv run ruff check src/`; `uv run pytest -q`; ejecución vía `docker compose up -d --wait`.
- Dependencias: `psycopg[binary]>=3.3.9` (per ADR-004).

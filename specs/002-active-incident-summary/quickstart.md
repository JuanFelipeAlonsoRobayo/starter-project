# Quickstart — Hito 002: Puertos y adaptadores para el resumen de incidentes activos

Scenarios de validación ejecutables (prerrequisito: `uv sync`). El contrato
observable del endpoint HTTP/CLI está definido en
[spec.md — Contrato de interfaces y salida](spec.md#contrato-de-interfaces-y-salida).

## Puertas de calidad (solo cambio de comportamiento => puertas del hito)

```bash
uv run ruff check src/                     # sin errores (Constitución IV)
uv run pytest -v                           # escenarios H002 + nuevos del hito
uv run python -m src.domain.sla_calculator # casos asertados (sin cambio, referencia)
```

## Configuración del entorno (`DATABASE_URL`)

Selección de repositorio en `src/adapters/outbound/factory.py`:

| `DATABASE_URL` | Repositorio resultante |
| --- | --- |
| *(no definido)* | `SqliteIncidentRepository(":memory:")` |
| `/ruta/incidentops.db` | `SqliteIncidentRepository("/ruta/incidentops.db")` |
| `sqlite:///ruta/incidentops.db` | `SqliteIncidentRepository("ruta/incidentops.db")` |
| `sqlite:///:memory:` | `SqliteIncidentRepository(":memory:")` |

## Verificación de arquitectura hexagonal (nuevo)

```bash
# Verificación de cumplimiento del puerto (RuntimeCheckable)
uv run python - <<'PY'
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.application.ports import IncidentRepositoryPort

repo = SqliteIncidentRepository(":memory:")
assert isinstance(repo, IncidentRepositoryPort)
assert repo.check_health() is True
print("port compliance OK")
PY
```

```bash
# Índice compuesto presente y verificable (búsqueda por componente)
uv run python - <<'PY'
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository

repo = SqliteIncidentRepository(":memory:")
indexes = [row[1] for row in repo.conn.execute("PRAGMA index_list(incidents)")]
assert "idx_incidents_component_status" in indexes
columns = [row[2] for row in repo.conn.execute("PRAGMA index_info('idx_incidents_component_status')")]
assert columns == ["component", "status"]
print("composite index OK:", columns)
PY
```

## Scenario: HTTP — resumen filtrado con instante fijo

```bash
uv run uvicorn src.adapters.inbound.api.app:app --port 8000
curl "http://127.0.0.1:8000/api/v1/incidents/summary?component=payments-gateway&reference_time=2026-11-20T12:00:00"
# expect HTTP 200 con body JSON de spec.md#json-de-salida
```

## Scenario: CLI — mismo resumen que HTTP (paridad REST/CLI)

```bash
uv run python -m src.adapters.inbound.cli summary --component payments-gateway --reference-time 2026-11-20T12:00:00
# stdout: objeto JSON idéntico al body de GET /api/v1/incidents/summary
```

## Scenario: puerto de repositorio — `list_active_incidents`

```bash
uv run python - <<'PY'
from datetime import datetime
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.domain.models import Incident

repo = SqliteIncidentRepository(":memory:")
repo.save_incident(Incident("INC-1", "T", "comp", "P0", "OPEN", datetime(2026, 11, 20, 10, 0, 0)))
repo.save_incident(Incident("INC-2", "T", "comp", "P0", "RESOLVED", datetime(2026, 11, 20, 10, 0, 0)))

active = repo.list_active_incidents(reference_time=datetime(2026, 11, 20, 12, 0, 0))
assert [i.incident_id for i in active] == ["INC-1"]
assert repo.get_incident("INC-2") is not None
assert repo.find_open_duplicates("k", datetime.now()) == []
print("repository OK")
PY
```

## Actualización recomendada (AGENTS.md)

Al cerrar este hito, AGENTS.md debe reflejar:

- `DATABASE_URL` default `sqlite:///:memory:` y formas aceptadas (nuevo default).
- `create_incident_repository() -> IncidentRepositoryPort` y `SqliteIncidentRepository` con índices `(component, status)` + INNER JOIN `sla_policies`.
- `IncidentRepositoryPort` y los métodos nuevos del adaptante.
- Puertas nuevas: `uv run ruff check src/`.

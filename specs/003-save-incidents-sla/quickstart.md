# Quickstart — Hito 003: Creación de incidentes, detección de duplicados y auditoría de SLA

Escenarios de validación ejecutables (prerrequisito: `uv sync`). El contrato observable
de creación y auditoría está definido en
[contracts/incident_creation_contract.md](contracts/incident_creation_contract.md) y
[contracts/sla_audit_contract.md](contracts/sla_audit_contract.md); los escenarios BDD
están en [spec.md — Escenarios BDD de aceptación](spec.md#escenarios-bdd-de-aceptación).

## Puertas de calidad

```bash
uv run ruff check src/                     # sin errores (Constitución IV)
uv run pytest -v                           # escenarios H003 (TestClient + CliRunner)
```

## Verificación de arquitectura hexagonal y de índices

```bash
uv run python - <<'PY'
from src.adapters.outbound.sqlite_repository import SqliteIncidentRepository
from src.application.ports import IncidentRepositoryPort

repo = SqliteIncidentRepository(":memory:")
assert isinstance(repo, IncidentRepositoryPort)
indexes = [row[1] for row in repo.conn.execute("PRAGMA index_list(incidents)")]
assert "idx_incidents_dup_key" in indexes
cols = [row[2] for row in repo.conn.execute("PRAGMA index_info('idx_incidents_dup_key')")]
assert cols == ["duplicate_group_key", "status"]
print("port + índice OK:", cols)
PY
```

## Escenario 1 — Creación inicial sin duplicados previos (HTTP 201)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "Pasarela de pagos rechaza cargos", "raw_text": "La pasarela de pagos rechaza cargos con error 500."}'
# expect: 201
curl -s -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "Pasarela de pagos rechaza cargos", "raw_text": "La pasarela de pagos rechaza cargos con error 500."}' | jq '{is_duplicate, duplicate_of, severity, component, recommended_team}'
# expect: is_duplicate=false, duplicate_of=[]
```

(Equivalente CLI: `uv run python -m src.adapters.inbound.cli create --title "..." --raw-text "..."` → JSON con `is_duplicate=false`, `duplicate_of=[]`.)

## Escenario 2 — Detección de duplicado abierto (201, is_duplicate=true)

```bash
# El incidente #1 (escenario 1) tiene el mismo duplicate_group_key y estado OPEN.
curl -s -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "Pasarela de pagos rechaza cargos", "raw_text": "La pasarela de pagos rechaza cargos con error 500."}' | jq '{is_duplicate, duplicate_of}'
# expect: is_duplicate=true, duplicate_of=["<incident_id del #1>"]
# (incidentes con status RESOLVED no aparecen en duplicate_of)
```

## Escenario 3 — Auditoría deterministica de SLA en horario hábil (P2)

```bash
# Incidente registrado con severity P2, creado viernes 2026-11-06T17:00:00
curl -s -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "Exports Lentos", "raw_text": "La exportación de reportes es lenta: más de 10,000 registros, tarda unos segundos.", "created_at": "2026-11-06T17:00:00"}' | jq '.severity'
# expect: P2
curl -s "http://127.0.0.1:8000/api/v1/incidents/<INC-XXXXXXXX>/sla?reference_time=2026-11-09T09:00:00" | jq
# expect: {incident_id, severity: "P2", elapsed_minutes: 120, allowed_minutes: 480,
#          remaining_minutes: 360, is_breached: false, requires_escalation: false}
```

## Escenario 4 — 404 para ID inexistente y 422 para reference_time < created_at

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8000/api/v1/incidents/INC-NONE/sla"
# expect: 404
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8000/api/v1/incidents/<INC-XXXXXXXX>/sla?reference_time=2026-11-06T16:00:00"
# expect: 422 (creado 17:00)
```

## Escenario 5 — Operación equivalente mediante CLI create y sla

```bash
uv run python -m src.adapters.inbound.cli create --title "Exports Lentos" --raw-text "La exportación de reportes es lenta: más de 10,000 registros, tarda unos segundos." --created-at 2026-11-06T17:00:00 | jq '{is_duplicate, duplicate_of}'
uv run python -m src.adapters.inbound.cli sla --incident-id <INC-XXXXXXXX> --reference-time 2026-11-09T09:00:00 | jq
# stdout JSON = cuerpo HTTP equivalente (paridad REST/CLI)
```

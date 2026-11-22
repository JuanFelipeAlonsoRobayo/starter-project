# Data Model — Hito 002: Puertos y adaptadores para el resumen de incidentes activos

## 1. `IncidentRepositoryPort` (puerto de repositorio en la aplicación)

```python
@runtime_checkable
class IncidentRepositoryPort(Protocol):
    def save_incident(self, incident: Incident) -> None: ...
    def get_incident(self, incident_id: str) -> Incident | None: ...
    def find_open_duplicates(
        self, duplicate_group_key: str, created_at: datetime, exclude_incident_id: str | None = None
    ) -> list[Incident]: ...
    def list_active_incidents(self, reference_time: datetime, component: str | None = None) -> list[Incident]: ...
    def check_health(self) -> bool: ...
    def list_incidents(self) -> list[Incident]: ...
```

Contrato detallado: `contracts/incident_repository_port.md`.

- El puerto es el contrato secundario definido por la aplicación (Constitución II); `SqliteIncidentRepository` lo implementa.
- `list_incidents` incorpora `IncidentReadPort` (lectura-toda) para la ruta de triaje; su comportamiento es idéntico al actual.
- La verificación de cumplimiento es dinámica (`runtime_checkable`) y se comprueba en tests (`isinstance`).

## 2. `SqliteIncidentRepository` (adaptante saliente, `src/adapters/outbound/sqlite_repository.py`)

- Constructor: `SqliteIncidentRepository(db_path: str = ":memory:")` (compatibilidad con `factory.py` y tests).
- Esquema: `incidents` + índice compuesto `idx_incidents_component_status (component, status)`; `sla_policies` poblada desde `SLA_POLICY_TABLE` (ADR-002); `incidents.duplicate_group_key` nullable + índice parcial forward-looking. Detalle: `contracts/sqlite_incident_repository.md`.
- Métodos de puerto:
  - `save_incident(incident)` — INSERT OR REPLACE (per `incidents`).
  - `get_incident(incident_id)` — SELECT por PK; `Incident` o `None`.
  - `find_open_duplicates(...)` — activos con mismo `duplicate_group_key`, `created_at <= given`, excluye el ID dado.
  - `list_active_incidents(reference_time, component=None)` — una consulta única con `INNER JOIN sla_policies ON p.severity = i.severity`; `reference_time` se valida en el dominio (el adaptante no filtra por él para preservar el error `REFERENCE_TIME_BEFORE_CREATION`).
  - `check_health()` — `SELECT 1` sobre la conexión.
- `seed_incidents(incidents)` — wrapper del hito anterior sobre `save_incident` (compatibilidad con `tests/test_spec_002_summary.py`).

## 3. `IncidentService` — nuevo caso de uso (`src/application/services.py`)

```python
def get_active_incidents_summary(
    self,
    component_filter: str | None = None,
    reference_time: str | datetime | None = None,
) -> ActiveIncidentSummary
```

- Orquesta: resolver `reference_time` → `list_active_incidents` → `build_active_incident_summary` (SLA + orden en dominio).
- Preserva `ValidationError("REFERENCE_TIME_BEFORE_CREATION", ...)`; constructor: `IncidentService(incident_repository: IncidentRepositoryPort | None = None)`.

## 4. Superficies entrantes

- `schemas.py`: `ActiveIncidentItem` (campos: incident_id, title, component, severity, status, elapsed_minutes, is_breached, requires_escalation); `ActiveIncidentSummaryResponse.incidents: List[ActiveIncidentItem]`.
- `app.py`: `GET /api/v1/incidents/summary` → `service.get_active_incidents_summary(component=..., reference_time=...)`.
- `cli.py`: `summary --component --reference-time` → `IncidentService.get_active_incidents_summary`.

## 5. Inventario de pruebas (`tests/test_spec_002_summary.py`)

Escenarios H002 existentes mantenidos. Añadidos:
- Port compliance: `isinstance(SqliteIncidentRepository(":memory:"), IncidentRepositoryPort)`; `check_health() is True`; round-trip `save_incident`/`get_incident`; `find_open_duplicates([])` sobre uno vacío.
- `list_active_incidents`: excluye `ESCALATION_REQUIRED`/`RESOLVED`; filtro por componente normalizado (mayúsculas/espacios); `EXPLAIN QUERY PLAN` usa el índice compuesto con filtro de componente.
- `get_active_incidents_summary`: propagación de `REFERENCE_TIME_BEFORE_CREATION` (ValidationError) para instante anterior a creación.

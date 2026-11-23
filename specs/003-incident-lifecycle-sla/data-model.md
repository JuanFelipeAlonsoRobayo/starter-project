# Data Model — Hito 003: Lifecycle — creación de incidentes, detección de duplicados y auditoría de SLA

## 1. `Incident` (`src/domain/models.py`) — extendido

```python
@dataclass
class Incident:
    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    recommended_team: Optional[RecommendedTeam] = None
    duplicate_group_key: Optional[str] = None
```

- `recommended_team`: calculado por `classify_incident_report` (`TriageResult.recommended_team`); expuesto en la respuesta de creación; sin columna de persistencia nueva.
- `duplicate_group_key`: clave de duplicados del sistema; nullable (consistente con la columna existente del adaptante saliente).

## 2. `to_naive_utc` (`src/domain/sla_calculator.py`)

Función pública puro: `to_naive_utc(value: datetime) -> datetime`. Aplicada en `evaluate_sla_status` (created_at/resolved_at/reference_time).

## 3. `IncidentCreationResult` (`src/application/services.py`)

```python
@dataclass(frozen=True)
class IncidentCreationResult:
    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    rationale: str
    is_duplicate: bool
    duplicate_of: List[str]
```

## 4. `IncidentNotFoundError` (`src/application/services.py`)

```python
class IncidentNotFoundError(Exception):
    """El incidente solicitado no existe."""

    def __init__(self, incident_id: str) -> None:
        super().__init__(f"El incidente {incident_id} no existe.")
        self.incident_id = incident_id
```

## 5. `IncidentService` — casos de uso nuevos (`src/application/services.py`)

```python
def create_incident(
    self,
    title: str,
    raw_text: str,
    incident_id: Optional[str] = None,
    created_at: Optional[Union[str, datetime]] = None,
    status: Optional[IncidentStatus] = None,
) -> IncidentCreationResult
```

- Validación: `title`/`raw_text` obligatorios no vacíos tras `strip()` → `ValidationError("EMPTY_TITLE"/"EMPTY_RAW_TEXT", ...)` (422 API / exit 1 CLI).
- ID: `incident_id` dado o autogenerado `INC-<HEX8>`.
- `status`: default `"OPEN"`; validación contra `IncidentStatus` (`INVALID_STATUS`).
- Clasificación: `classify_incident_report(incident_id, raw_text)` (dominio).
- Persistencia: `save_incident(incident, duplicate_group_key)`.
- Duplicados: `find_open_duplicates(duplicate_group_key, created_at, exclude_incident_id=incident_id)` → `is_duplicate=bool(duplicates)`, `duplicate_of=[d.incident_id for d in duplicates]`.

```python
def evaluate_incident_sla(
    self,
    incident_id: str,
    reference_time: Optional[Union[str, datetime]] = None,
) -> SLAEvaluation
```

- `get_incident(incident_id)` → `IncidentNotFoundError` si no existe (404 / exit 2).
- `reference_time`: str/datetime/None → `ValidationError("INVALID_REFERENCE_TIME")` si no ISO-8601; normalizado a naive UTC.
- Delega en `evaluate_sla_status`; `ReferenceTimeBeforeCreationError` → `ValidationError("REFERENCE_TIME_BEFORE_CREATION")` (422 API / exit 1 CLI).

## 6. `SqliteIncidentRepository` (`src/adapters/outbound/sqlite_repository.py`)

- Esquema nuevo: `CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status);` (columna `duplicate_group_key` ya existía — forward-looking H002; índice parcial legacy conservado).
- `save_incident`: persiste `incident.duplicate_group_key` (fallback al parámetro).
- `get_incident`: UNCHANGED (ya implementa el puerto); `_row_to_incident` adiciona `duplicate_group_key` (coherente).
- `find_open_duplicates`: filtra `status IN (OPEN_DUPLICATE_STATUSES)` — constante de dominio en `src/domain/models.py` — y aplica la equivalencia por coincidencia exacta de `duplicate_group_key`; docstrings actualizados.
- Constantes de dominio: `OPEN_DUPLICATE_STATUSES = ('OPEN', 'IN_PROGRESS', 'ESCALATION_REQUIRED')` en `src/domain/models.py` — conjunto canónico de estados abiertos para duplicados, consumido por `find_open_duplicates` y documentado en `ports.py`.
- Verificación: `PRAGMA index_list(incidents)` incluye `idx_incidents_dup_key`; `PRAGMA index_info('idx_incidents_dup_key')` → `['duplicate_group_key', 'status']`.

## 7. Superficies entrantes (`src/adapters/inbound/`)

- `api/schemas.py`: `CreateIncidentRequest` (title, raw_text, incident_id?, created_at?, status?; `extra="forbid"`), `IncidentCreatedResponse` (incident_id, severity, component, recommended_team, duplicate_group_key, rationale, is_duplicate, duplicate_of), `SLAEvaluationResponse` (incident_id, severity, elapsed_minutes, allowed_minutes, remaining_minutes, is_breached, requires_escalation).
- `api/app.py`: `POST /api/v1/incidents` (201) → `IncidentService.create_incident`; `GET /api/v1/incidents/{incident_id}/sla` → `IncidentService.evaluate_incident_sla`. `VALIDATION_STATUS` extendido (`EMPTY_TITLE`, `INVALID_CREATED_AT`, `INVALID_STATUS` → 422; sla route: `REFERENCE_TIME_BEFORE_CREATION`/`INVALID_REFERENCE_TIME` → 422, `INCIDENT_NOT_FOUND` → 404).
- `cli.py`: `create` → JSON de `IncidentCreatedResponse`; `sla` → JSON de `SLAEvaluationResponse`. Paridad REST/CLI.

## 8. Inventario de pruebas (`tests/test_spec_003_lifecycle_sla.py`) — 5 escenarios BDD

1. **Registro inicial sin duplicados previos** — `TestClient.post("/api/v1/incidents")` → 201; `is_duplicate=false`, `duplicate_of=[]`.
2. **Detección de duplicado abierto en la creación** — POST #2 → 201; `is_duplicate=true`; `duplicate_of` incluye ID del incidente #1; incidentes `RESOLVED` no aparecen.
3. **Auditoría deterministica de SLA en horario hábil** — P2 creado viernes 2026-11-06T17:00:00, consultado lunes 2026-11-09T09:00:00 → `elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`, `requires_escalation=false`.
4. **Consulta de SLA para ID inexistente y tiempo anterior a creación** — `404`; `422` con `reference_time < created_at`.
5. **Operación equivalente mediante los comandos CLI `create` y `sla`** — `CliRunner`: JSON de creación par por HTTP; JSON de `sla` igual que HTTP para el mismo instante.
Plus: port compliance (`isinstance` + `check_health`), índice (`PRAGMA`), normalización aware/naive, `find_open_duplicates` con `ESCALATION_REQUIRED` y `RESOLVED`.

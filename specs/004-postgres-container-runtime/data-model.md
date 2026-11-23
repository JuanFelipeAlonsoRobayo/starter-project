# Data Model — Servicio en contenedores con base de datos dedicada y chequeo de salud (per ADR-004)

## 1. `IncidentRepositoryPort` (puerto de repositorio en la aplicación)

*(Sin cambios — puerto existente, per hito 002)*

```python
@runtime_checkable
class IncidentRepositoryPort(Protocol):
    def save_incident(self, incident: Incident) -> None: ...
    def get_incident(self, incident_id: str) -> Incident | None: ...
    def find_open_duplicates(
        self, duplicate_group_key: str, created_at: datetime, exclude_incident_id: str | None = None
    ) -> list[Incident]: ...
    def list_active_incidents(self, reference_time: datetime, component: str | None = None) -> list[Incident]: ...
    def check_health(self) -> bool: ...          # ya en el puerto
    def list_incidents(self) -> list[Incident]: ...
```

El puerto incluye `check_health() -> bool` desde el Hito 002; `IncidentRepositoryPort` ya se satisface por ambos adaptantes concretos.

## 2. `PostgresIncidentRepository` (nuevo — `src/adapters/outbound/postgres_repository.py`)

### 2.1 Constructor

- `PostgresIncidentRepository(conninfo: str)`; conexión `psycopg.connect(conninfo, autocommit=True)`; `row_factory = psycopg.rows.dict_row` (per design R1); esquema inicializado en `_init_schema()`.

### 2.2 Esquema (PostgreSQL, sin ORM; paridad semántica con `SqliteIncidentRepository`)

```sql
CREATE TABLE IF NOT EXISTS sla_policies (
    severity TEXT PRIMARY KEY,
    max_resolution_minutes INTEGER NOT NULL,
    operates_24x7 INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,           -- ISO 8601, paridad temporal con SQLite (TEXT)
    resolved_at TEXT,
    duplicate_group_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status);
CREATE INDEX IF NOT EXISTS idx_incidents_duplicate_group_key
    ON incidents (duplicate_group_key) WHERE duplicate_group_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status);
```

`sla_policies` poblada desde `SLA_POLICY_TABLE` (per ADR-002, como `SqliteIncidentRepository`).

### 2.3 Semántica de puerto

- `save_incident(incident)` — `INSERT ... ON CONFLICT (incident_id) DO UPDATE SET ...` (upsert SQL estándar; equivalente a `INSERT OR REPLACE` de SQLite); params `%s`.
- `get_incident(incident_id)` — `SELECT ... WHERE incident_id = %s`, `.fetchone()`; `Incident | None`.
- `find_open_duplicates(...)` — activos (`status IN (OPEN/IN_PROGRESS)`) con mismo `duplicate_group_key` y `created_at <= %s`, excluye el ID dado, ordenado `created_at ASC, incident_id ASC`.
- `list_active_incidents(reference_time, component=None)` — `INNER JOIN sla_policies` + filtro de componente sin mayúsculas (igual que SQLite).
- `check_health() -> bool` — `SELECT 1` real sobre la conexión; devuelve `False` sobre `psycopg.Error`.
- `list_incidents()` — lectura-toda para la ruta de triaje.
- `close()` — cierra la conexión.

### 2.4 Mapeo fila → `Incident` (adaptante, per Constitución II; sin reglas de negocio)

```python
def _row_to_incident(row: dict) -> Incident:
    return Incident(
        incident_id=row["incident_id"],
        title=row["title"],
        component=row["component"],
        severity=row["severity"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        duplicate_group_key=row["duplicate_group_key"],
    )
```

### 2.5 Señales de verificación

- `issubclass(PostgresIncidentRepository, IncidentRepositoryPort)` → `True` (Protocol `runtime_checkable`).
- `create_repository("postgresql://incidentops:incidentops@db:5432/incidentops")` → instancia de `PostgresIncidentRepository`.
- Índices presentes (via `information_schema.statistics`); timestamps almacenados como ISO 8601 en `TEXT`.

## 3. `SqliteIncidentRepository` — método `check_health()`

- Ya implementado (`src/adapters/outbound/sqlite_repository.py:151`): `self.conn.execute("SELECT 1").fetchone()`; `True`; sobre `sqlite3.Error` → `False`.
- El plan los cataloga como verificación de contrato; sin cambios en el archivo.

## 4. `IncidentService.check_health()` (nuevo — `src/application/services.py`)

```python
def check_health(self) -> bool:
    """Verifica el estado de operación del repositorio saliente."""
    if self._incident_repository is None:
        return False
    return self._incident_repository.check_health()
```

## 5. Superficies entrantes

- `schemas.py`: `HealthResponse` (campos: `status: str`, `database: str`; contrato según `contracts/health_endpoint_contract.md`).
- `app.py`: `GET /health` → `HealthResponse(status="ok", database="connected")` o `JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})`.
- `cli.py`: `health` — emite JSON `{"status": "ok", "database": "connected"}` (exit 0) o `{"status": "error", "database": "unavailable"}` (exit 1) sobre `IncidentService(incident_repository=create_incident_repository()).check_health()`.

## 6. DuckDB/Duck typing — no.

*(Nada; la arquitectura es doble: SQLite embebido + PostgreSQL dedicado.)*

## 7. Inventario de pruebas (`tests/test_spec_004_runtime_health.py`)

- **BDD RNF-001 (dual)**:
  - `create_repository("sqlite:///:memory:")` → `SqliteIncidentRepository`;
  - `create_repository("/ruta/incidentops.db")` → `SqliteIncidentRepository`;
  - `create_repository("postgresql://incidentops:incidentops@db:5432/incidentops")` → `PostgresIncidentRepository` (`issubclass(PostgresIncidentRepository, IncidentRepositoryPort)`);
  - `create_incident_repository()` sin `DATABASE_URL` → `SqliteIncidentRepository`;
  - `create_incident_repository()` con `DATABASE_URL=postgresql://...` → `PostgresIncidentRepository`.
- **BDD RNF-002 (chequeo real sin caché)**:
  - `TestClient(create_app(repository)).get("/health")` → 200 `{"status": "ok", "database": "connected"}`;
  - Doble: `unittest.mock`/`MonkeyPatch` con `IncidentService.check_health() → False` → 503 `{"status": "error", "database": "unavailable"}`;
  - `check_health()` pasa por `SELECT 1` real: `repo = SqliteIncidentRepository(":memory:"); assert repo.check_health() is True`.
- **BDD RNF-003 (estructura Docker)**: `Dockerfile`, `.dockerignore`, `docker-compose.yml` existen; compose parsea con `yaml.safe_load`; `services` = `{"api", "db"}`; `db.image == "postgres:16-alpine"`; `api.depends_on["db"]["condition"] == "service_healthy"`; `db.healthcheck["test"]` contiene `"pg_isready"`; `api.healthcheck["test"]` referencia `/health`.
- **CLI**: `CliRunner()(["health"])` → stdout `{"status": "ok", "database": "connected"}`, exit_code 0 (con `DATABASE_URL` default/SQLite); caso de fallo con doble → exit_code 1 y `{"status": "error", "database": "unavailable"}`.

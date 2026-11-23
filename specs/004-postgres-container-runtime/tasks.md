# Tasks: Servicio en contenedores con base de datos dedicada y chequeo de salud de conectividad

**Input**: Design documents from `specs/004-postgres-container-runtime/`

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `data-model.md`, `contracts/`, `research.md`, `quickstart.md`

**Tests**: `tests/test_spec_004_runtime_health.py` (BDD RNF-001–RNF-003 + escenarios BDD 1–2 del spec; ver data-model.md inventario). Pruebas BDD existentes sin regresión.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/` at repository root

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and deployment files (RNF-003)

- [x] T001 [P] Create `Dockerfile` — base `python:3.12-slim`, bootstrap `uv` (`ghcr.io/astral-sh/uv:latest` → `/uv`), `uv sync --frozen --no-dev`, `CMD ["uv","run","--no-sync","uvicorn","src.adapters.inbound.api.app:app","--host","0.0.0.0","--port","8000"]` (raíz) — realizado
- [x] T002 [P] Create `.dockerignore` — excluye `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `tests/`, `docs/`, `specs/`, `data/`, `.git/`, `Imagenes-Evidencias/`, `CONTEXT_LOG.md`, `SDD_LOG.md`, `*.py[cod]`, `*.log` (raíz) — realizado
- [x] T003 [P] Create `docker-compose.yml` — `db`: `image: postgres:16-alpine`, volumen `incidentops_pgdata`, healthcheck `pg_isready`; `api`: `build: .`, `DATABASE_URL: postgresql://incidentops:incidentops@db:5432/incidentops`, `depends_on: db (condition: service_healthy)`, healthcheck GET `/health` sobre `localhost:8000` (raíz) — realizado
- [x] T004 [P] `pyproject.toml` + `uv.lock`: añadir `psycopg[binary]>=3.3.9` como dependencia de ejecución (justificada por ADR-004); ya aplicado (`uv add psycopg[binary]`, `uv lock`)
- [x] T005 [P] Verificar entorno: `uv sync`; `uv run ruff check src/` (puerta Constitución IV); `uv run python -c "import psycopg"` → 3.3.9 — verificado

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Núcleo del hito: adaptante PostgreSQL sin ORM + factory dual [US1]

> **⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 [US1] Implement `PostgresIncidentRepository` in `src/adapters/outbound/postgres_repository.py`: — realizado
  - `__init__(conninfo: str)`: `psycopg.connect(conninfo, autocommit=True)`; `row_factory = psycopg.rows.dict_row` [DM PostgresIncidentRepository.__init__]
  - `_init_schema()`: tabla `sla_policies` (`severity TEXT PRIMARY KEY`, `max_resolution_minutes INTEGER NOT NULL`, `operates_24x7 INTEGER NOT NULL`) poblada desde `SLA_POLICY_TABLE`; tabla `incidents` (`incident_id TEXT PRIMARY KEY`, `title`, `component`, `severity`, `status`, `created_at TEXT ISO 8601`, `resolved_at TEXT`, `duplicate_group_key`); índices `idx_incidents_component_status (component, status)`, `idx_incidents_duplicate_group_key` (parcial `WHERE duplicate_group_key IS NOT NULL`), `idx_incidents_dup_key (duplicate_group_key, status)` [DM PostgresIncidentRepository._init_schema]
  - `save_incident(incident)`: `INSERT ... ON CONFLICT (incident_id) DO UPDATE SET ...` (upsert SQL estándar; equivalente a `INSERT OR REPLACE` de SQLite) [DM PostgresIncidentRepository.save_incident]
  - `get_incident(incident_id) -> Incident | None`; `find_open_duplicates(...)`; `list_active_incidents(...)` con `INNER JOIN sla_policies` [DM PostgresIncidentRepository.list_active_incidents]
  - `check_health() -> bool`: `SELECT 1` real; `False` sobre `psycopg.Error` [DM PostgresIncidentRepository.check_health]
  - `list_incidents()`; `close()`; `_row_to_incident(row) -> Incident` (map fila→`Incident`; sin reglas de negocio — per Constitución II)
- [x] T007 [US1] Modificar `src/adapters/outbound/factory.py`: — realizado
  - Añadir `create_repository(database_url: str) -> IncidentRepositoryPort`: `postgresql://`/`postgres://` → `PostgresIncidentRepository(database_url)`; `sqlite:///ruta`, `sqlite://`, ruta directa o ausente → `SqliteIncidentRepository(_resolve_sqlite_path(...))`; default `sqlite:///:memory:`
  - Mantener `create_incident_repository() -> IncidentRepositoryPort` como wrapper (leer `DATABASE_URL` del entorno, delegar en `create_repository`)
- [x] T008 [US1] Verificar: `issubclass(PostgresIncidentRepository, IncidentRepositoryPort)`; `isinstance(create_repository("sqlite:///:memory:"), SqliteIncidentRepository)`; `create_incident_repository()` sin `DATABASE_URL` → `SqliteIncidentRepository` — verificado (`factory/repository OK`)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Ejecución del servicio en contenedores (Priority: P1) 🎯 MVP

**Goal**: El servicio se ejecuta desplegido en contenedores con la base de datos relacional dedicada (ADR-004) seleccionada transparentemente vía `DATABASE_URL`.

**Independent Test**: `docker compose up -d --wait`; `curl http://localhost:8000/health` → 200; logs de `db` con `pg_isready` asentando conexiones.

### Implementation for User Story 1

- [x] T009 [US1] Validación de despliegue: `docker compose up -d --wait`; `curl -s http://localhost:8000/health` → 200 `{"status":"ok","database":"connected"}`; verificar contenedores `api`+`db` en ejecución y log de `db` (`pg_isready`). (Integración) — verificado (`HTTP/1.1 200 OK` + `{"status":"ok","database":"connected"}`; `docker compose ps`: api Healthy, db Healthy)

---

## Phase 4: User Story 2 - Chequeo real de salud de conectividad (Priority: P1)

**Goal**: El servicio expone un chequeo real de salud de conectividad: endpoint HTTP `GET /health` (200/503) y comando CLI `health` con el mismo contrato (per spec RNF-002 + contrato).

**Independent Test**: `curl http://localhost:8000/health` → 200 `{"status":"ok","database":"connected"}`; con doble → 503 `{"status":"error","database":"unavailable"}`; `cli health` → JSON + exit 0/1.

### Implementation for User Story 2

- [x] T010 [P] [US2] Implement `IncidentService.check_health()` in `src/application/services.py` — delegar al puerto `IncidentRepositoryPort.check_health()` (puerto existente desde Hito 002; `SqliteIncidentRepository.check_health()` existente — `SELECT 1` sobre la conexión) — realizado
- [x] T011 [US2] Implement `HealthResponse` and `GET /health` in `src/adapters/inbound/api/schemas.py` + `src/adapters/inbound/api/app.py` — 200 `{"status":"ok","database":"connected"}` / 503 `{"status":"error","database":"unavailable"}` (contrato per `contracts/health_endpoint_contract.md`; ejecuta `check_health()` real per petición — sin caché) [DM HealthResponse] — realizado
- [x] T012 [P] [US2] Implement `health` command in `src/adapters/inbound/cli.py` — JSON `{"status":"ok","database":"connected"}` (exit 0) o `{"status":"error","database":"unavailable"}` (exit 1) sobre `IncidentService.check_health()` — realizado
- [x] T013 [US2] Escribir `tests/test_spec_004_runtime_health.py` — BDD: `/health` 200 (`{"status":"ok","database":"connected"}`); `/health` 503 con doble (`check_health()` False → `{"status":"error","database":"unavailable"}`); `create_repository` dual (SQLite + PostgreSQL cumplen `IncidentRepositoryPort`); CLI `health`; estructura Docker (per data-model inventario) — realizado
- [x] T014 [US2] Verificar: `uv run pytest -q` sin errores — verificado (34 passed)

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T015 [P] Documentación: actualizar `AGENTS.md` (según recomendación de `quickstart.md`): `create_repository(database_url)`, `create_incident_repository()` compat, `IncidentService.check_health()`, `GET /health` + `health` CLI, `psycopg[binary]>=3.3.9` — realizado
- [x] T016 [US1] Ejecutar validación de `quickstart.md`: escenarios A–E (curl /health, doble, dual selection, CLI, estructura Docker) — verificado (A: 200 OK + `{"status":"ok","database":"connected"}`, `api`/`db` Healthy; B: 34 passed; C: dual selection OK; D: CLI health exit 0; E: files exist; ruff OK)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion (paralel al US1 por puntos independientes; refuerzo estándar por shared contracts)
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1 - Ejecución del servicio en contenedores)**: Can start after Foundational (Phase 2). Independent Test: `docker compose up -d --wait` → `curl /health` → 200.
- **User Story 2 (P1 - Chequeo real de salud)**: Can start after Foundational (Phase 2). Independent Test: curl /health 200; CLI health.

### Within Each User Story

- Tests (if included) MUST be written first
- Dependency order: models/services → endpoints/commands → integration validation
- Story complete before moving to next priority

### Parallel Opportunities

- Setup: T001, T002, T003 [P] — different files
- Foundational: T006 (base para T007); T007 depende de T006; T008 depende de T006+T007
- US2: T010, T012 [P] (different files); T011 depende de T010; T013 depende de T011; T014 depende de T013
- Polish: T015 [P] — different file; T016 depende de US1+US2

---

## Parallel Example: User Story 1

```bash
# Setup (paralelo):
Task: "Create Dockerfile"            # T001
Task: "Create .dockerignore"         # T002
Task: "Create docker-compose.yml"    # T003

# After Foundational (Phase 2):
Task: "Validación de despliegue"     # T009 (integración US1)
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T008)
3. Complete Phase 3: User Story 1 (T009)
4. **STOP and VALIDATE**: `docker compose up -d --wait` → `curl http://localhost:8000/health` → 200

### Incremental Delivery

1. Setup → Foundational → Foundation listo
2. Add US1 → deploy/demo (MVP)
3. Add US2 → tests + validation green

### Parallel Team Strategy

1. Team completes Setup (T001–T005)
2. Worker A: T006 → T007 → T008 (Foundational)
3. Once Foundational is done: Worker B: US1 (T009); Worker C: US2 (T010–T013)
4. Phase 5 (T015–T016) al final

---

## Notes

- Formato estricto: `- [ ] [TaskID] [P?] [Story] Description with file path` — todos los tasks incluyen ficheros y checkbox
- Citas de restricciones (data-model.md) integradas: T006 (`PostgresIncidentRepository.save_incident`/`check_health`/`list_active_incidents`/`_init_schema`), T011 (`HealthResponse`)
- `[P]` marca solo tareas con archivos distintos y sin dependencias inversas
- Ejecutar validación BDD antes de implementar (US2)
- T004: ya aplicado antes de generar (comando `uv add psycopg[binary]`; `uv.lock` refrescado) — reflejado en el checkbox de Phase 1

# Tasks: Hito 002 — Puertos y adaptadores para el resumen de incidentes activos

**Input**: Design documents from `specs/002-active-incident-summary/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: `tests/test_spec_002_summary.py` se extiende con port-compliance (T015). Pruebas BDD H002 mantienen cubiertos los 4 escenarios sin regresión.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/` at repository root
- Paths are project-relative to repository root

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, architecture config

- [x] T001 [P] Create project structure per implementation plan (`specs/002-active-incident-summary/plan.md`): estructura `src/application/`, `src/adapters/outbound/`, `src/adapters/inbound/api/`, `src/adapters/inbound/cli.py`; `pyproject.toml` + `src/domain/ruff.toml` + `src/application/ruff.toml` + `src/adapters/inbound/ruff.toml`
- [x] T002 [P] Add root Ruff configuration: `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "TID"]` in `pyproject.toml` (research.md R6)
- [x] T003 [P] Add `src/domain/ruff.toml`: `extend = "../../pyproject.toml"`, select, `[lint.flake8-tidy-imports] ban-relative-imports = "parents"`, `[lint.flake8-tidy-imports.extend-banned-api]` de la tabla de fronteras (research.md R6; skill hexagonal)
- [x] T004 [P] Add `src/application/ruff.toml`: `extend = "../../pyproject.toml"`, select, `ban-relative-imports = "parents"`, `extend-banned-api` (solo veta `src.adapters`; construcción sin veta de `src.application`)
- [x] T005 [P] Add `src/adapters/inbound/ruff.toml`: `extend = "../../../pyproject.toml"`, select, `ban-relative-imports = "parents"`, `extend-banned-api`: `sqlite3`, `psycopg`, `sqlalchemy`, `src.adapters.outbound.sqlite_repository`

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST complete before ANY user story

- [x] T006 [P] Define `IncidentRepositoryPort` Protocol in `src/application/ports.py` (@runtime_checkable; métodos `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents`, `check_health`, `list_incidents`; contracts/incident_repository_port.md; data-model.md §1)
- [x] T007 Implement `SqliteIncidentRepository` optimized in `src/adapters/outbound/sqlite_repository.py`: schema `sla_policies` + índice compuesto `idx_incidents_component_status` + índice parcial `idx_incidents_duplicate_group_key`; `list_active_incidents` con `INNER JOIN sla_policies` (contracts/sqlite_incident_repository.md); `save_incident`, `get_incident`, `find_open_duplicates`, `check_health`; wrapper `seed_incidents` (research.md R3; data-model.md §2)
- [x] T008 Update `src/adapters/outbound/factory.py`: `create_incident_repository() -> IncidentRepositoryPort`; `DEFAULT_DATABASE_URL = "sqlite:///:memory:"`; `_resolve_sqlite_path` preservando `:memory:` y rutas (research.md R2)
- [x] T009 Add `IncidentService.get_active_incidents_summary(component_filter, reference_time)` in `src/application/services.py`: resuelve `reference_time`, llama `list_active_incidents` con `normalize_component_filter`, construye `build_active_incident_summary` (SLA via `src/domain/sla_calculator.py`); mapping `REFERENCE_TIME_BEFORE_CREATION` (research.md R4; data-model.md §3)

## Phase 3: User Story 1 — Consultar el estado operativo por HTTP (Priority: P1) 🎯 MVP

**Goal**: El resumen de incidentes activos con total, incumplimientos y detalle por HTTP.

**Independent Test**: quickstart.md escenario HTTP — GET /api/v1/incidents/summary devuelve 200 con `total_active`/`breached_count`/`incidents`; determinístico con `reference_time` fijo (spec.md#contrato-de-interfaces-y-salida).

- [x] T010 [P] [US1] Add `ActiveIncidentItem` in `src/adapters/inbound/api/schemas.py`; `ActiveIncidentSummaryResponse.incidents: List[ActiveIncidentItem]`; retirar `ActiveIncidentDetailResponse` (data-model.md §4; research.md R5)
- [x] T011 [US1] Update `GET /api/v1/incidents/summary` in `src/adapters/inbound/api/app.py`: delegar en `IncidentService.get_active_incidents_summary` (data-model.md §4; spec.md#contrato-de-interfaces-y-salida)

## Phase 4: User Story 2 — Obtener el mismo resumen desde la terminal (Priority: P2)

**Goal**: El CLI expone el mismo resumen que HTTP (paridad REST/CLI obligatoria).

**Independent Test**: quickstart.md escenario CLI — stdout JSON idéntico al body HTTP con mismos parámetros (spec.md#contrato-cli; quickstart.md).

- [x] T012 [US2] Update `summary` command in `src/adapters/inbound/cli.py`: usar `IncidentService.get_active_incidents_summary` (data-model.md §4; quickstart.md escenario CLI)

## Phase 5: User Story 3 — Acotar el resumen a un componente (Priority: P3)

**Goal**: Filtrar el resumen por componente sin que un filtro sin coincidencias sea error.

**Independent Test**: filtro reduce resultados al componente indicado; componente vacío = sin filtro; sin coincidencias = resumen vacío exitoso (spec.md#contrato-de-interfaces-y-salida).

- [x] T013 [P] [US3] Implementar filtro por componente: normalización (`strip().lower()`, `normalize_component_filter`) en `IncidentService` (data-model.md §3) + condición SQL `lower(TRIM(component)) = lower(TRIM(?))` en `SqliteIncidentRepository.list_active_incidents` (contracts/sqlite_incident_repository.md); componente en blanco = sin filtro

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T014 Verify quality gates: `uv run ruff check src/` (0 errores) + `uv run pytest -v` (quickstart.md; Constitution IV/V)
- [x] T015 [P] Extend `tests/test_spec_002_summary.py`: port compliance — `isinstance(SqliteIncidentRepository, IncidentRepositoryPort)`, `check_health() is True`, round-trip `save_incident`/`get_incident`, `find_open_duplicates == []`; casos BDD: estados incluyen OPEN/IN_PROGRESS y excluyen RESOLVED/ESCALATION_REQUIRED, filtro por componente normalizado, `PRAGMA index_list(incidents)` muestra `idx_incidents_component_status` y `PRAGMA index_info` su columna de búsqueda es `(component, status)`; caso de servicio REFERENCE_TIME_BEFORE_CREATION (data-model.md §5)
- [x] T016 [P] Update `AGENTS.md`: `DATABASE_URL` default `sqlite:///:memory:` + formas aceptadas (quickstart.md); `create_incident_repository() -> IncidentRepositoryPort`; `SqliteIncidentRepository` (índices `(component, status)` + INNER JOIN `sla_policies`); `IncidentRepositoryPort` y métodos nuevos; puertas nuevas (`uv run ruff check src/`)

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: Setup — BLOCKS user stories
- **User Stories (Phase 3–5)**: Foundational completion; US2 after US1; US3 after Foundational (paralelo con US1)
- **Polish (Phase 6)**: depends on all stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational
- **US2 (P2)**: after US1 (paridad REST/CLI compartida)
- **US3 (P3)**: Foundational, independent of US1

### Within Each User Story

- T010 → T011 (response type → endpoint)
- US2 after US1 (paridad observable)

## Parallel Opportunities

- Setup: T002–T005 (archivos distintos)
- Foundational: T006 → T007 → T008 → T009 (chain)
- US1: T010 → T011
- US3 independent of US1 (paralelo)
- Polish: T015, T016 (archivos distintos)

### Parallel Example: User Story 1

```bash
# Stories in parallel when capacity allows (US1 → US2 after, US3 parallel):
Task: "T010 — Add ActiveIncidentItem in src/adapters/inbound/api/schemas.py"
Task: "T013 — Implementar filtro por componente [US3]"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (port → repo → factory → service)
3. Complete Phase 3: US1 (endpoint) → STOP and VALIDATE via quickstart.md escenario HTTP
4. Add US2 (CLI) → validar paridad
5. Add US3 (filtro) → validar escenarios de filtro
6. Phase 6: Polish (T014–T016)

### Incremental Delivery

Setup → Foundational → US1 (validar) → US2 (validar) → US3 (validar) → Polish

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story
- Each user story independently testable via quickstart.md escenarios
- Constitucion IV/V gates: `uv run ruff check src/`, `uv run pytest -v`, paridad HTTP/CLI
- Skill hexagonal: `.opencode/skills/hexagonal-architecture` base normativa (cited above)

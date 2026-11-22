# Tasks: Hito 003 — Creación de incidentes, detección de duplicados y auditoría de SLA

**Input**: Design documents from `/specs/003-save-incidents-sla/`

**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/

**Tests**: `tests/test_spec_003_lifecycle_sla.py` (5 escenarios BDD con `TestClient` y `CliRunner`) — escenarios del spec.md: Registro inicial sin duplicados, detección de duplicado abierto al crear, auditoría deterministica de SLA en horario hábil, consulta de SLA para ID inexistente y tiempo anterior a creación, operación equivalente mediante los comandos CLI `create` y `sla`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions; constrainted fields cite `data-model.md` (Entity.field)

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths are project-relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, environment verification

- [X] T001 [P] Verificar entorno de desarrollo con `uv sync` (plan.md; root `package = false`, puertas vía `uv run`).
- [X] T002 [P] Verificar estructura de la feature: `specs/003-save-incidents-sla/` (plan.md; ya existe).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Extend `Incident` — añadir `recommended_team: Optional[RecommendedTeam] = None` y `duplicate_group_key: Optional[str] = None` en `src/domain/models.py` (data-model.md — Incident; data-model.md — Incident.recommended_team).
- [X] T004 [P] Añadir `to_naive_utc` y aplicarlo en `evaluate_sla_status` en `src/domain/sla_calculator.py` — normalización consistente de marcas temporales naive/aware (data-model.md — Incident.created_at; data-model.md — to_naive_utc).

---

## Phase 3: User Story 1 — Almacenar los incidentes al llegar (Priority: P1) 🎯

**Goal**: persistir el incidente recibido al llegar, conservando su identificador, título, severidad, estado e instante de creación (spec.md US1).

**Independent Test**: escenario 1 de `tests/test_spec_003_lifecycle_sla.py` — `TestClient` POST → 201 sin duplicados previos (`is_duplicate=false`, `duplicate_of=[]`).

- [X] T005 [P] [US1] Implementar `IncidentService.create_incident` en `src/application/services.py` — validación (`EMPTY_TITLE`/`EMPTY_RAW_TEXT`), generación de `incident_id` si se omite (`INC-<HEX8>`), `status` default `"OPEN"`, clasificación via `classify_incident_report` y persistencia via `save_incident` (data-model.md — IncidentCreationResult; data-model.md — IncidentCreationResult.incident_id, IncidentCreationResult.severity, IncidentCreationResult.component, IncidentCreationResult.recommended_team, IncidentCreationResult.duplicate_group_key, IncidentCreationResult.rationale; data-model.md — Incident.duplicate_group_key; contracts/incident_creation_contract.md).
- [X] T006 [US1] Añadir `CreateIncidentRequest` + `IncidentCreatedResponse` en `src/adapters/inbound/api/schemas.py` (contratos: title, raw_text, incident_id, created_at, status, is_duplicate, duplicate_of; data-model.md — CreateIncidentRequest.title, CreateIncidentRequest.raw_text, CreateIncidentRequest.incident_id, CreateIncidentRequest.created_at, CreateIncidentRequest.status, IncidentCreatedResponse.incident_id, IncidentCreatedResponse.severity, IncidentCreatedResponse.component, IncidentCreatedResponse.recommended_team, IncidentCreatedResponse.duplicate_group_key, IncidentCreatedResponse.rationale, IncidentCreatedResponse.is_duplicate, IncidentCreatedResponse.duplicate_of; data-model.md — CreateIncidentRequest, IncidentCreatedResponse).
- [X] T007 [US1] Añadir ruta `POST /api/v1/incidents` en `src/adapters/inbound/api/app.py` — 201 `IncidentCreatedResponse`, errores 422 (EMPTY_TITLE/EMPTY_RAW_TEXT) + 500 INTERNAL_ERROR (contracts/incident_creation_contract.md).
- [X] T008 [US1] Añadir comando `create` en `src/adapters/inbound/cli.py` — stdout JSON de `IncidentCreatedResponse`, código de salida 1 por `ValidationError` (contracts/incident_creation_contract.md).
- [X] T009 [US1] Escenario 1 de tests: `TestClient.post("/api/v1/incidents")` → 201 sin duplicados previos (`is_duplicate=false`, `duplicate_of=[]`) en `tests/test_spec_003_lifecycle_sla.py` (spec.md US1 — Escenario 1).

---

## Phase 4: User Story 2 — Detección de incidentes equivalentes abiertos al crear un incidente nuevo (Priority: P1)

**Goal**: al crear un incidente nuevo equivalente, `is_duplicate=true` y `duplicate_of` con el ID del incidente equivalente abierto existente (spec.md US2).

**Independent Test**: escenario 2 de `tests/test_spec_003_lifecycle_sla.py` — POST → 201, `is_duplicate=true`, `duplicate_of` incluye ID del equivalente abierto, incidentes `RESOLVED` excluidos.

- [X] T010 [P] [US2] `SqliteIncidentRepository._init_schema` en `src/adapters/outbound/sqlite_repository.py` — añadir índice `idx_incidents_dup_key` sobre `(duplicate_group_key, status)`; actualizar `contracts/sqlite_incident_repository.md` (data-model.md — idx_incidents_dup_key).
- [X] T011 [P] [US2] `SqliteIncidentRepository.find_open_duplicates` — filtrar `status IN (OPEN_DUPLICATE_STATUSES)` — constante de dominio en `src/domain/models.py` + actualizar docstrings (`src/adapters/outbound/sqlite_repository.py`; data-model.md — find_open_duplicates; models.py — OPEN_DUPLICATE_STATUSES).
- [X] T012 [P] [US2] `SqliteIncidentRepository.save_incident` — persistir `incident.duplicate_group_key` con fallback al parámetro heredado (`src/adapters/outbound/sqlite_repository.py`; data-model.md — SqliteIncidentRepository).
- [X] T013 [US2] `SqliteIncidentRepository.get_incident` + `_row_to_incident` — poblar `Incident.duplicate_group_key` desde la fila (`src/adapters/outbound/sqlite_repository.py`; data-model.md — Incident.duplicate_group_key).
- [X] T014 [US2] `IncidentService.create_incident` — calcular `is_duplicate`/`duplicate_of` via `find_open_duplicates` excluyendo `RESOLVED` y el propio ID (`src/application/services.py`; data-model.md — IncidentCreationResult.is_duplicate, IncidentCreationResult.duplicate_of).
- [X] T015 [US2] Escenario 2 de tests: `TestClient.post("/api/v1/incidents")` → 201 con `is_duplicate=true`, `duplicate_of` incluye el incident_id del equivalente abierto, sin incidentes `RESOLVED` en `duplicate_of` (`tests/test_spec_003_lifecycle_sla.py`; spec.md US2 — Escenario 2).

---

## Phase 5: User Story 3 — Consultar cómo va el SLA por interfaz HTTP y herramienta CLI (Priority: P1)

**Goal**: `GET /api/v1/incidents/{incident_id}/sla` y CLI `sla` devuelven `SLAEvaluationResponse` del incidente auditado (spec.md US3).

**Independent Test**: escenarios 3–5 de `tests/test_spec_003_lifecycle_sla.py` — SLA deterministica P2 horario hábil; 404 para ID inexistente + 422 para tiempo anterior a creación; paridad CLI `create`/`sla` vs HTTP.

- [X] T016 [P] [US3] Añadir `SLAEvaluationResponse` en `src/adapters/inbound/api/schemas.py` (contracts/sla_audit_contract.md; data-model.md — SLAEvaluationResponse; data-model.md — SLAEvaluationResponse.incident_id, SLAEvaluationResponse.severity, SLAEvaluationResponse.elapsed_minutes, SLAEvaluationResponse.allowed_minutes, SLAEvaluationResponse.remaining_minutes, SLAEvaluationResponse.is_breached, SLAEvaluationResponse.requires_escalation).
- [X] T017 [US3] Añadir `IncidentService.evaluate_incident_sla` en `src/application/services.py` — `get_incident` + delegar en `evaluate_sla_status` (data-model.md — IncidentService).
- [X] T018 [US3] Añadir `IncidentNotFoundError` en `src/application/services.py` (data-model.md — IncidentNotFoundError).
- [X] T019 [US3] Añadir ruta `GET /api/v1/incidents/{incident_id}/sla` en `src/adapters/inbound/api/app.py` — 200 `SLAEvaluationResponse`; 404 `INCIDENT_NOT_FOUND`; 422 `REFERENCE_TIME_BEFORE_CREATION`/`INVALID_REFERENCE_TIME` (contracts/sla_audit_contract.md).
- [X] T020 [US3] Añadir comando `sla` en `src/adapters/inbound/cli.py` — stdout JSON de `SLAEvaluationResponse`; exit 2 `INCIDENT_NOT_FOUND`, exit 1 por `REFERENCE_TIME_BEFORE_CREATION` (contracts/sla_audit_contract.md).
- [X] T021 [US3] Escenario 3: `TestClient.get("/api/v1/incidents/<INC-XXXXXXXX>/sla?reference_time=2026-11-09T09:00:00")` → `elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`, `requires_escalation=false` (P2 creado viernes 2026-11-06T17:00:00) (`tests/test_spec_003_lifecycle_sla.py`; spec.md US3 — Escenario 3; quickstart.md Escenario 3).
- [X] T022 [US3] Escenario 4: `TestClient.get("/api/v1/incidents/INC-NONE/sla")` → 404; `reference_time < created_at` → 422 (`tests/test_spec_003_lifecycle_sla.py`; spec.md US3 — Escenario 4).
- [X] T023 [US3] Escenario 5: paridad — `CliRunner` ejecuta `create` y `sla`, stdout JSON del CLI equivale al body HTTP (`tests/test_spec_003_lifecycle_sla.py`; spec.md US3 — Escenario 5; quickstart.md Escenario 5).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Coverage of quality gates, docs sync

- [X] T024 [P] Verificar en `tasks.md` que cada campo restringido de `data-model.md` esté citado por al menos una tarea implementadora: `Incident.recommended_team`, `Incident.duplicate_group_key`, `IncidentCreationResult.incident_id`, `IncidentCreationResult.severity`, `IncidentCreationResult.component`, `IncidentCreationResult.recommended_team`, `IncidentCreationResult.duplicate_group_key`, `IncidentCreationResult.rationale`, `IncidentCreationResult.is_duplicate`, `IncidentCreationResult.duplicate_of`, `IncidentNotFoundError`, `SqliteIncidentRepository.idx_incidents_dup_key`, `SLAEvaluationResponse.incident_id`, `SLAEvaluationResponse.severity`, `SLAEvaluationResponse.elapsed_minutes`, `SLAEvaluationResponse.allowed_minutes`, `SLAEvaluationResponse.remaining_minutes`, `SLAEvaluationResponse.is_breached`, `SLAEvaluationResponse.requires_escalation`, `CreateIncidentRequest.title`, `CreateIncidentRequest.raw_text`, `CreateIncidentRequest.incident_id`, `CreateIncidentRequest.created_at`, `CreateIncidentRequest.status`, `IncidentCreatedResponse.incident_id`, `IncidentCreatedResponse.severity`, `IncidentCreatedResponse.component`, `IncidentCreatedResponse.recommended_team`, `IncidentCreatedResponse.duplicate_group_key`, `IncidentCreatedResponse.rationale`, `IncidentCreatedResponse.is_duplicate`, `IncidentCreatedResponse.duplicate_of`, `models.py — OPEN_DUPLICATE_STATUSES`.
- [X] T025 [P] Ejecutar puertas de quickstart: `uv run ruff check src/` (0 errores) + `uv run pytest -v` (quickstart.md; plan.md).
- [X] T026 [P] Actualizar `AGENTS.md` Commands: añadir invocaciones `create` y `sla` de `src/adapters/inbound/cli.py` en el formato documentado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — starts immediately
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: depends on Foundational (Phase 2)
- **User Story 2 (Phase 4)**: depends on Foundational (Phase 2) and on T005 (`create_incident` base)
- **User Story 3 (Phase 5)**: depends on Foundational (Phase 2) and on US2 (T013 `get_incident` + T014 `is_duplicate`/`duplicate_of`); independent of US1 beyond the shared `save_incident`
- **Polish (Phase 6)**: depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Foundational — no dependencies on other stories
- **US2 (P1)**: after Foundational and after US1's T005 (`create_incident`)
- **US3 (P1)**: after Foundational and after US2 (repo `get_incident` + duplicate flags wired)

### Within Each User Story

- T005 → T014 (base `create_incident` → duplicate detection)
- T006 → T007 (`IncidentCreatedResponse` → `POST /api/v1/incidents`)
- T012 → T013 (persist column → row mapping)
- T016/T017/T018 → T019/T020 (service methods → HTTP/CLI surfaces)
- Tests T009 → after T007; T015 → after T014; T021–T023 → after their US3 tasks

### Parallel Opportunities

- Setup: T001, T002 (different concerns)
- Foundational: T003, T004 (different files: `models.py`, `sla_calculator.py`)
- US1: T006 → T007 → T008 → T009 (T009 depends on the whole US1 chain)
- US2: T010, T011, T012 (different files); T013 after T012; T014 after T005
- US3: T016, T017, T018 (different files, after US2); T019 after T017; T020 after T017
- Polish: T024, T025, T026 (different files)

### Parallel Example: User Story 2

```bash
# Launch repository tasks for US2 in parallel (different files):
Task: "T010 [P] _init_schema + idx_incidents_dup_key (src/adapters/outbound/sqlite_repository.py)"
Task: "T011 [P] find_open_duplicates filter (src/adapters/outbound/sqlite_repository.py)"
Task: "T012 [P] save_incident duplicate_group_key (src/adapters/outbound/sqlite_repository.py)"
```

### Parallel Example: User Story 3

```bash
# Launch schema/service/error tasks for US3 in parallel (different files):
Task: "T016 [P] SLAEvaluationResponse (src/adapters/inbound/api/schemas.py)"
Task: "T017 [US3] evaluate_incident_sla (src/application/services.py)"
Task: "T018 [US3] IncidentNotFoundError (src/application/services.py)"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — `Incident` + `to_naive_utc`
3. Complete Phase 3: US1 — persistir al llegar (`POST /api/v1/incidents`, `create` CLI); validar escenario 1
4. Complete Phase 4: US2 — detección de duplicados (índice, filtro, flags de respuesta); validar escenario 2
5. Complete Phase 5: US3 — auditoría de SLA (`GET /api/v1/incidents/{id}/sla`, `sla` CLI); validar escenarios 3–5
6. Complete Phase 6: Polish — puertas quickstart + sync AGENTS.md
7. **STOP and VALIDATE**: quickstart gates (T025), citas verificadas (T024)

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Deliver (registro al llegar)
3. Add US2 → Test independently → Deliver (detección de duplicados)
4. Add US3 → Test independently → Deliver (auditoría de SLA)
5. Polish — tests, gates, AGENTS.md sync

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (service + routes + CLI)
   - Developer B: US2 (repo + flags) — after T005 lands
   - Developer C: US3 (service + surfaces) — after US2
3. Stories complete and integrate independently

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests written per user request (5 BDD scenarios with TestClient + CliRunner)
- Verify tests fail before implementing when possible (e.g., scenario 3 expectations vs. unevaluated code)
- Commit after each task or logical group
- Avoid: same-file conflicts between parallel tasks, cross-story dependencies that break independence

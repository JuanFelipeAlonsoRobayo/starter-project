# Implementation Plan — Hito 003: Creación de incidentes, detección de duplicados y auditoría de SLA

**Branch**: `003-save-incidents-sla` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Acuerdos del equipo para H003:
1. **Creación**: persistir incidentes al llegar; respuesta de creación (`201 Created` en `POST /api/v1/incidents`, JSON en CLI `create`) con clasificación completa (`severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`) + `is_duplicate` (bool) + `duplicate_of` (`list[str]` de `incident_id` equivalentes abiertos, sin `RESOLVED` y sin el propio ID recién creado).
2. **Detección de duplicados**: equivalencia por coincidencia exacta de `duplicate_group_key`; estados abiertos `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`; excluye `RESOLVED`.
3. **Auditoría de SLA**: `GET /api/v1/incidents/{incident_id}/sla` + CLI `sla`; resultado = `SLAEvaluation` (`incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached`, `requires_escalation`); `404 Not Found` si el ID no existe; `422 Unprocessable Entity` si `reference_time < created_at` (CLI: exit 1).

Contratos definidos por el feature: [contracts/incident_creation_contract.md](contracts/incident_creation_contract.md), [contracts/sla_audit_contract.md](contracts/sla_audit_contract.md).

## Summary

Hito H003 extiende el ciclo de vida de los incidentes: casos de uso `IncidentService.create_incident` y `IncidentService.evaluate_incident_sla` en `src/application/services.py`; puerto `IncidentRepositoryPort` existente; adaptante saliente `SqliteIncidentRepository` con nuevo índice `idx_incidents_dup_key`; adaptantes primarios delgados (`POST /api/v1/incidents`, `GET /api/v1/incidents/{incident_id}/sla`, CLI `create`/`sla`); `Incident` extendido con `recommended_team` + `duplicate_group_key`; normalización naive/aware en `src/domain/sla_calculator.py`; 5 escenarios BDD en `tests/test_spec_003_lifecycle_sla.py`.

## Technical Context

**Language/Version**: Python 3.10+ (gestionado con `uv`).

**Primary Dependencies**: FastAPI (adaptante HTTP), Pydantic v2 (contratos HTTP/CLI), Typer (adaptante CLI), SQLite3 estándar (adaptante saliente; sin ORM), pytest + httpx + fastapi.testclient + typer.testing (tests).

**Storage**: SQLite embebido stdlib; tabla `incidents` (columna `duplicate_group_key` ya existente — forward-looking H002) + nuevo índice compuesto `idx_incidents_dup_key ON incidents (duplicate_group_key, status)`; `sla_policies` poblada desde `SLA_POLICY_TABLE` (ADR-002).

**Testing**: pytest -v; 5 escenarios BDD H003 (`tests/test_spec_003_lifecycle_sla.py` con `TestClient` y `CliRunner`) + verificación de puerto sobre `SqliteIncidentRepository(":memory:")`.

**Target Platform**: Linux/macOS/Windows; adaptantes FastAPI y Typer en proceso; adaptante saliente sobre SQLite/`DATABASE_URL`.

**Project Type**: web-service (FastAPI) con superficie CLI (Typer).

**Performance Goals**: `find_open_duplicates` sobre el índice compuesto `(duplicate_group_key, status)`; `get_incident` sobre PK.

**Constraints**: Constitución v1.0.0 (principios I–V); ADR-002 (política SLA); ADR-003 (hexagonal); sin nuevas dependencias de ejecución; cálculo del SLA solo en `src/domain/sla_calculator.py`.

## Constitution Check

| Principio | Verificación (fase 1) |
| --- | --- |
| I. Núcleo Determinista Único | `Incident`, `to_naive_utc`, `evaluate_sla_status` y `IncidentService.create_incident` son puros (sin imports prohibidos, sin I/O). |
| II. Arquitectura Hexagonal | Puertos en `application` (sin cambios); ningún puerto nuevo; `app.py`/`cli.py` delegando en `IncidentService`. |
| III. Gobernanza del Stack | Sin nuevas dependencias. |
| IV. Verificación Estática de Fronteras | `uv run ruff check src/` limpio; TID251/TID252 cumplidos. |
| V. Pruebas BDD Obligatorias | `tests/test_spec_003_lifecycle_sla.py`: 5 escenarios BDD + paridad HTTP/CLI. |

Re-verificación post-diseño: sin violaciones introducidas por el diseño.

## Project Structure

### Documentation (this feature)

```text
specs/003-save-incidents-sla/
├── plan.md                # This file (/speckit.plan command output)
├── research.md            # Phase 0 output (/speckit.plan command)
├── data-model.md          # Phase 1 output (/speckit.plan command)
├── quickstart.md          # Phase 1 output (/speckit.plan command)
├── contracts/             # Phase 1 output (/speckit.plan command)
│   ├── incident_creation_contract.md
│   └── sla_audit_contract.md
└── tasks.md               # Phase 2 output (/speckit.tasks - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── domain/
│   ├── models.py                 # MOD: Incident + recommended_team + duplicate_group_key
│   └── sla_calculator.py         # MOD: to_naive_utc + normalización en evaluate_sla_status
├── application/
│   └── services.py               # MOD: create_incident, evaluate_incident_sla, IncidentNotFoundError, IncidentCreationResult
├── adapters/
│   ├── inbound/
│   │   ├── api/
│   │   │   ├── schemas.py        # MOD: CreateIncidentRequest, IncidentCreatedResponse, SLAEvaluationResponse
│   │   │   └── app.py            # MOD: POST /api/v1/incidents, GET /api/v1/incidents/{incident_id}/sla
│   │   └── cli.py                # MOD: create, sla
│   └── outbound/
│       └── sqlite_repository.py  # MOD: idx_incidents_dup_key, ajustes de save/get/find_open_duplicates
tests/
├── test_spec_003_lifecycle_sla.py  # NUEVO: 5 escenarios BDD (TestClient + CliRunner)
```

### Structure Decision

Opción B — Arquitectura Hexagonal adoptada (ADR-003). Este hito extiende la arquitectura al ciclo de vida de los incidentes: casos de uso en `application`, adaptante saliente en `outbound`, adaptantes primarios en `inbound`. El motor de persistencia se sigue seleccionando exclusivamente en `factory.py` (no hay knowledge de SQL fuera de adaptantes).

## Complexity Tracking

No se esperan violaciones complejas: los nuevos endpoints/CLI siguen el patrón ya establecido (H002: `POST /api/v1/incidents` ↔ `POST /triage`; `GET /api/v1/incidents/{id}/sla` ↔ `GET /api/v1/incidents/summary`; `cli create`/`cli sla` ↔ `cli triage`/`cli summary`). La frontera "reglas solo en el dominio" se respeta: la equivalencia queda en `triage_rules` y el estado-límite en `sla_calculator`.

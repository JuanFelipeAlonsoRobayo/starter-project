# Implementation Plan — Hito 002: Puertos y adaptadores para el resumen de incidentes activos

**Branch**: `002-active-incident-summary` | **Date**: 2026-11-22 | **Spec**: `specs/002-active-incident-summary/spec.md`

**Input**: Hito 002 del roadmap: amplía el resumen de incidentes activos con el modelo
de arquitectura hexagonal de la Constitución (puertos, adaptantes y verificación estática).

## Summary

Hito 002 define el modelo de Arquitectura Hexagonal para el resumen de incidentes
activos: el puerto `IncidentRepositoryPort` en `src/application/ports.py`; el adaptante
saliente `SqliteIncidentRepository` optimizado (extracción de Semana 1: `INNER JOIN
sla_policies`, índice compuesto `(component, status)`, lectura única de activos); el
caso de uso `IncidentService.get_active_incidents_summary` (SLA vía `src/domain/sla_calculator.py`);
las superficies entrantes `GET /api/v1/incidents/summary` (FastAPI, `ActiveIncidentItem`) y
el comando `summary` (Typer); la configuración estática con Ruff (`[tool.ruff.lint]`
`select = ["E4", "E7", "E9", "F", "TID"]` en `pyproject.toml` + archivos jerárquicos
`src/domain/ruff.toml`, `src/application/ruff.toml`, `src/adapters/inbound/ruff.toml`
con `extend` y TID251/TID252); y la extensión de `tests/test_spec_002_summary.py` con
verificación de cumplimiento de puerto sobre `SQLiteIncidentRepository`.

## Technical Context

**Language/Version**: Python 3.10+ (gestionado con `uv`; `requires-python = ">=3.10"`).

**Primary Dependencies**: FastAPI (adaptante HTTP `GET /api/v1/incidents/summary`), Pydantic v2
(contrato HTTP/CLI de salida), Typer (adaptante CLI `summary`), SQLite3 estándar (adaptante
saliente; sin ORM), pytest + httpx/fastapi.testclient + typer.testing (BDN BDD REST/CLI).

**Storage**: SQLite embebido stdlib; tablas `incidents` (+ índice compuesto `(component, status)`
y `duplicate_group_key` forward-looking) y `sla_policies` poblada desde `SLA_POLICY_TABLE`.
`DATABASE_URL`: ruta, `sqlite:///ruta`, `sqlite:///:memory:`; default `sqlite:///:memory:`.

**Testing**: pytest -v; BDN BDD 4 escenarios H002 (sin regresión) + verificación de puerto
(`isinstance` con `IncidentRepositoryPort` @runtime_checkable) + casos BDD del adaptante
(status/filter/EXPLAIN) + caso de servicio REFERENCE_TIME_BEFORE_CREATION.

**Target Platform**: Linux/macOS/Windows; adaptantes FastAPI y Typer desplegados en proceso;
adaptante saliente sobre archivos SQLite (o ruta `DATABASE_URL`).

**Project Type**: web-service (FastAPI) con superficie CLI (Typer).

**Performance Goals**: una lectura única optimizada del resumen (`INNER JOIN sla_policies`,
índice compuesto `(component, status)`); el escaneo completo y N+1 del script legacy
`src/incident_repository.py` se mantiene intacto (fase propia).

**Constraints**: sin nuevas dependencias de ejecución; fronteras hexagonales verificables
por `uv run ruff check src/`; cálculo SLA y orden del resumen solo en `src/domain/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución v1.0.0 — verificación inicial:

| Principio | Verificación (fase 1) |
| --- | --- |
| I. Núcleo Determinista Único | Sin cambios en `src/domain/`; SLA y active-summary sin I/O ni imports distintos. |
| II. Arquitectura Hexagonal Estricta (ADR-003) | Nuevo puerto en `application`; adaptante saliente en `outbound`; ninguna regla en adaptantes. |
| III. Gobernanza del Stack | Sin nuevas dependencias; SQLite stdlib ya en uso; nueva puerta ruff documentada. |
| IV. Verificación Estática de Fronteras | `[tool.ruff.lint] select = ["E4","E7","E9","F","TID"]`; hijos `src/domain/ruff.toml`, `src/application/ruff.toml`, `src/adapters/inbound/ruff.toml` con `extend` + `ban-relative-imports = "parents"` + TID251 baneados por capa. |
| V. Pruebas BDD Obligatorias | `tests/test_spec_002_summary.py` extiende H002 sin romper los 4 escenarios; paridad HTTP/CLI preservada. |

Re-verificación post-diseño: todos los puertos cumplen; gates asumidos verificables en quickstart.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
src/
├── domain/                       # Puro: models, sla_calculator, active_summary (sin cambios en este hito)
├── application/
│   ├── ports.py                  # NUEVO: IncidentRepositoryPort (@runtime_checkable)
│   └── services.py               # NUEVO: IncidentService.get_active_incidents_summary
├── adapters/
│   ├── inbound/
│   │   ├── api/
│   │   │   ├── schemas.py        # NUEVO: ActiveIncidentItem
│   │   │   └── app.py            # GET /api/v1/incidents/summary (caso de uso nuevo)
│   │   └── cli.py                # summary (caso de uso nuevo)
│   └── outbound/
│       ├── sqlite_repository.py  # NUEVO (optimizado): sla_policies, índice (component, status), list_active_incidents
│       └── factory.py            # NUEVO: create_incident_repository() -> IncidentRepositoryPort, default sqlite:///:memory:
pyproject.toml                    # NUEVO: [tool.ruff.lint] select = ["E4", "E7", "E9", "F", "TID"]
src/domain/ruff.toml              # NUEVO: extend ../../pyproject.toml + TID251/TID252
src/application/ruff.toml         # NUEVO: extend ../../pyproject.toml + TID251/TID252
src/adapters/inbound/ruff.toml    # NUEVO: extend ../../../pyproject.toml + TID251/TID252
tests/
├── test_spec_001_triage.py       #existente (sin cambio)
├── test_spec_002_summary.py      #existente H002 + NUEVOS: port compliance, repo optimizado, servicio
└── conftest.py
```

**Structure Decision**: Opción B — Arquitectura Hexagonal adoptada (ADR-003). Este hito
extiende la arquitectura al resumen de incidentes activos: puertos secundarios en
`application`, adaptantes salientes en `outbound` y adaptantes primarios en `inbound`.
Selector de motor de persistencia exclusivo en `factory.py` (no hay knowledge de SQL
fuera de los adaptantes).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| H002 scan optimization (INNER JOIN + índice compuesto) | El hito lo establece para H002 ("extracción SQLite optimizada"); marca la fase de optimización del adaptante saliente | Escaneo completo + N+1 — deuda docente sin respaldo en el hito del usuario; Postgres/H004 — Constitución III (exige ADR) |
| `IncidentRepositoryPort` con `list_incidents` | `IncidentService.summarize_active_incidents` del H002 actual lo usa; el puerto de repositorio amplia a los 5 métodos del hito | Versión del puerto sin `list_incidents` — cuelga la ruta de triaje de un puerto de solo lectura |
| `runtime_checkable` en puertos | Verificación de cumplimiento (`isinstance`) exigida por el hito | Protocol sin runtime_checkable — no verificable estáticamente sobre instancias |
| Renombre `ActiveIncidentDetailResponse` → `ActiveIncidentItem` | Clares de superficie del hito; usuario lo pide ("agregar ActiveIncidentItem") | Mantener ambos nombres — duplicación constante |
| `sqlite:///:memory:` como default en factory | Hito estandariza la forma aceptada; AGENTS.md lo registra | Default `":memory:"` legacy — inconsistente con el resto de formas aceptadas del hito |
| TID251 por capa (banned-api) | Constitución IV y skill hexagonal codifican fronteras; se verifica con `uv run ruff check src/` | Solo TID252 (ban-parents) — no cubre la inversión de dependencias HTML/DB salvo en outbound |

Artifacts de este hito:

- `research.md` — Decisiones R1–R7 (puerto, factory, extracción optimizada, servicio,
  superficies entrantes, configuración Ruff, inventario de tests).
- `data-model.md` — `IncidentRepositoryPort`, `SqliteIncidentRepository`,
  `IncidentService.get_active_incidents_summary`, `ActiveIncidentItem`, inventario de tests.
- `contracts/incident_repository_port.md`, `contracts/sqlite_incident_repository.md`.
- `quickstart.md` — Escenarios de validación (gates, DATABASE_URL, endpoint, CLI, puerto, índice).
- `plan.md` — Este documento (plan actualizado).

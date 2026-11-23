# Implementation Plan — Servicio en contenedores con base de datos dedicada y chequeo de salud de conectividad

**Branch**: `004-postgres-container-runtime` | **Date**: 2026-11-22 | **Spec**: [specs/004-postgres-container-runtime/spec.md](spec.md)

**Input**: Hito 004 de ADR-004: Preparar la ejecución del servicio desplegada en contenedores con una base de datos relacional dedicada, exponiendo un chequeo real de salud de conectividad.

## Summary

Hito 004 prepara el runtime desplegable del servicio: un contenedor `api` (FastAPI) y un contenedor `db` dedicado PostgreSQL (`postgres:16-alpine`, per ADR-004); selección dual del motor de persistencia vía `DATABASE_URL` (`postgresql://` → `PostgresIncidentRepository`; `sqlite:///`/ruta/absenta → `SqliteIncidentRepository`; default `sqlite:///:memory:`); chequeo de salud real y sin caché (`SELECT 1` real sobre la base configurada) expuesto por `GET /health` (200 `{"status":"ok","database":"connected"}` / 503 `{"status":"error","database":"unavailable"}`, per spec RNF-002 + contrato) y comando CLI `health` con el mismo contrato; reproducibilidad del entorno vía `Dockerfile` (`python:3.12-slim` + `uv`), `.dockerignore` y `docker-compose.yml` (`api` sincronizado por `depends_on: db service_healthy`, healthcheck sobre `db` con `pg_isready`).

## Technical Context

**Language/Version**: Python 3.10+ (gestionado con `uv`; `requires-python = ">=3.10"`). Imagen del contenedor `api`: `python:3.12-slim` (per R4).

**Primary Dependencies**: FastAPI, Pydantic v2, Typer, uvicorn (adaptantes existentes); `psycopg[binary]>=3.3.9` (nuevo: adaptante PostgreSQL sin ORM, per ADR-004; `uv.lock` refrescado).

**Storage**: Dual — `SqliteIncidentRepository` (SQLite estándar stdlib, default sin cambios) y `PostgresIncidentRepository` (`psycopg[binary]`, sin ORM; tablas `incidents` + `sla_policies` y índices compuestos; timestamps ISO 8601 en `TEXT` para paridad temporal entre motores, per ADR-004).

**Testing**: pytest (`uv run pytest -q`); dev deps sin cambios (httpx, fastapi.testclient, typer.testing); nueva suite `tests/test_spec_004_runtime_health.py`.

**Target Platform**: Docker Compose (`api` + `db`) en producción; HTTP/CLI local sobre SQLite embebido en desarrollo sin Docker.

**Project Type**: web-service (FastAPI) + CLI (Typer) + runtime de despliegue (Docker Compose).

**Performance Goals**: Chequeo real: `SELECT 1` sobre la base configurada en cada petición de `GET /health`; sin caché (RNF-002); SC-002/SC-003 medibles como ejecución real en SC — sin objetivo de latencia duro en esta fase.

**Constraints**: Sin ORM (per ADR-004); `uv run ruff check src/` sin errores (Constitución IV); fronteras hexagonales (`src/domain/` sin cambios; `src/application/` sin cambios — `IncidentService.check_health()` añade un wrapper al puerto existente); `docker-compose.yml` con `depends_on: condition: service_healthy` sobre `db` (per ADR-004).

**Scale/Scope**: 2 contenedores; `api` con 1 réplica inicial (escalado horizontal opcional posterior); producción = motor PostgreSQL dedicado; desarrollo sin Docker = SQLite embebido default.

## Constitution Check

Constitución v1.0.0 — verificación inicial:

| Principio | Verificación (fase 1) |
| --- | --- |
| I. Núcleo Determinista Único | Sin cambios en `src/domain/`. |
| II. Arquitectura Hexagonal Estricta (ADR-003) | `PostgresIncidentRepository` implementa `IncidentRepositoryPort` (adaptante saliente); `HealthResponse`/`GET /health` y `health` son adaptantes entrantes delgados (api/cli). |
| III. Gobernanza del Stack | Nueva dependencia `psycopg[binary]` justificada por ADR-004; sin ORM; fronteras verificables por `uv run ruff check src/`. |
| IV. Verificación Estática de Fronteras | Puerta: `uv run ruff check src/` sin errores (Constitución IV); no se añaden violates de Tier TID251 (`.opencode/skills/hexagonal-architecture`). |
| V. Pruebas BDD Obligatorias | `tests/test_spec_004_runtime_health.py` cubre BDD RNF-001–RNF-003 y escenarios BDD 1–4 del spec. |

Re-check post-diseño: Todo los cambios pasan; ninguna violación justificada (Complexity Tracking vacío).

## Project Structure

### Documentation (this feature)

```text
specs/004-postgres-container-runtime/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── health_endpoint_contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
Dockerfile                  # NEW: imagen del contenedor `api` (python:3.12-slim + uv)
.dockerignore               # NEW: exclusiones del contexto de build (venv, cache, tests, docs)
docker-compose.yml          # NEW: `db` (postgres:16-alpine) + `api` (build: .)
pyproject.toml              # MOD: + `psycopg[binary]>=3.3.9` (runtime; per ADR-004)
uv.lock                     # MOD: refrescado (cambio del primer punto)

src/
├── adapters/inbound/
│   ├── api/
│   │   ├── app.py         # MOD: + `GET /health` (HealthResponse; 200/503)
│   │   ├── schemas.py     # MOD: + `HealthResponse`
│   │   └── __init__.py    # sin cambios
│   └── cli.py             # MOD: + comando `health`
├── adapters/outbound/
│   ├── postgres_repository.py   # NEW: PostgresIncidentRepository (psycopg, sin ORM)
│   ├── sqlite_repository.py     # sin cambios (check_health() existente)
│   └── factory.py               # MOD: + `create_repository(database_url)`; `create_incident_repository()` compat
├── application/
│   ├── ports.py                 # sin cambios (check_health() en el puerto)
│   └── services.py              # MOD: + `IncidentService.check_health()`
├── domain/                      # sin cambios (Constitución I)
└── incident_repository.py       # sin cambios (deuda docente, phase 2)

tests/
├── conftest.py                  # sin cambios
├── test_spec_001_triage.py      # sin cambios
├── test_spec_002_summary.py     # sin cambios
├── test_spec_003_lifecycle_sla.py  # sin cambios
└── test_spec_004_runtime_health.py  # NEW
```

### Structure Decision

**Web-service + runtime de contenedores**: árbol bilingüe — `src/` de aplicación; raíz del repositorio de despliegue (`Dockerfile`, `.dockerignore`, `docker-compose.yml`). Los archivos de despliegue nuevos en la raíz; `tests/test_spec_004_runtime_health.py` nuevo en la suite existente; `pyproject.toml` + `uv.lock` modificados (dependencia justificada por ADR-004).

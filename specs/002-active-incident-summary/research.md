# Research — Hito 002: Puertos y adaptadores para el resumen de incidentes activos

## Decisiones de Phase 0

### R1 — `IncidentRepositoryPort` (puerto de repositorio en la aplicación)

- **Decisión**: `src/application/ports.py` define el Protocolo `IncidentRepositoryPort` con:
  - `save_incident(incident: Incident) -> None`
  - `get_incident(incident_id: str) -> Incident | None`
  - `find_open_duplicates(duplicate_group_key: str, created_at: datetime, exclude_incident_id: str | None = None) -> list[Incident]`
  - `list_active_incidents(reference_time: datetime, component: str | None = None) -> list[Incident]`
  - `check_health() -> bool`
  - `list_incidents() -> list[Incident]` (incorpora a `IncidentReadPort`)
- **Racional**: el puerto lo define la aplicación; el repositorio concreto lo implementa en el adaptante saliente y lo provee `factory.py`. El puerto se marca `@runtime_checkable` para la verificación de cumplimiento que exige el hito.
- **Alternativas**:
  - Solo ampliar `IncidentReadPort` con métodos de escritura — rechazado: cuelga todo el ciclo de vida futuro (H003: duplicados, salvamento, latido) de un puerto de solo lectura.
  - Puerto por caso de uso (`IncidentDuplicatesPort`, `IncidentHealthPort`, ...) — rechazado: se fragmentaría la superficie de un solo repositorio; ADR-003 facilita un `IncidentRepositoryPort` coherente.
  - Implementar `list_incidents` en vez de usar `list_active_incidents` para la ruta de triaje — rechazado: el filtro de estado es regla de negocio; `list_incidents` sigue siendo la lectura-toda del adaptante y `IncidentReadPort` lo conserva.
- **Señal de verificación**: `isinstance(SqliteIncidentRepository(":memory:"), IncidentRepositoryPort)` devuelve `True`.

### R2 — `factory.py`: selección desde `DATABASE_URL`

- **Decisión**: `create_incident_repository() -> IncidentRepositoryPort`; `DEFAULT_DATABASE_URL = "sqlite:///:memory:"` (forma estandarizada aceptada por AGENTS.md). Formas aceptadas: ruta directa (`/ruta/incidentops.db`), `sqlite:///ruta/incidentops.db` y `sqlite:///:memory:` (default).
- **Racional**: el factory es el único lector de variables de entorno; el dominio y la aplicación no saben del motor.
- **Alternativas**: default `":memory:"` sin normalización — rechazado por el cambio a la forma explícita alineada al hito; Postgres (H004) — rechazado por la Constitución III (requiere ADR previo).
- **Señal de verificación**: `_resolve_sqlite_path` preserva `:memory:` y cualquier ruta; `create_incident_repository()` sin `DATABASE_URL` produce `SqliteIncidentRepository` sobre `:memory:`.

### R3 — Extracción optimizada de la persistencia (SQLite)

- **Decisión**: el adaptante saliente extrae de Semana 1 (`src/incident_repository.py`) la persistencia optimizada:
  - Esquema nuevo en `src/adapters/outbound/sqlite_repository.py`: tabla `sla_policies` (`severity` PK, `max_resolution_minutes`, `operates_24x7`) poblada desde `SLA_POLICY_TABLE` (per ADR-002), tabla `incidents`, índice compuesto `idx_incidents_component_status ON incidents (component, status)` y índice parcial `idx_incidents_duplicate_group_key ... WHERE duplicate_group_key IS NOT NULL` (forward-looking al H003).
  - `list_active_incidents`: una sola consulta con `INNER JOIN sla_policies ON p.severity = i.severity` y filtro `status IN ('OPEN','IN_PROGRESS') [AND lower(TRIM(i.component)) = lower(TRIM(?))]`. El INNER JOIN justifica que una severidad sin política no aparezca en el resumen (dato inconsistente, excluido por diseño).
  - `find_open_duplicates`: consulta sobre `duplicate_group_key` + estado activo + `created_at <= ?`.
- **Racional**: el hito establece la fase de optimización del H002; el escaneo completo + N+1 del script legacy se mantiene a la espera de su fase propia, y `src/incident_repository.py` se deja intacto como artefacto docente.
- **Alternativas**: mantener el escaneo completo y N+1 — rechazado por el hito; filtrar componente en Python (dentro de SQL sin índice) — rechazado por perder el uso del índice compuesto; otra dependencia (H004) — rechazada por Constitución III.
- **Señal de verificación**: `PRAGMA index_list(incidents)` sobre `SqliteIncidentRepository(":memory:")` incluye `idx_incidents_component_status` y `PRAGMA index_info` reporta `(component, status)`.

### R4 — `IncidentService.get_active_incidents_summary`

- **Decisión**: orquestación en `src/application/services.py`:
  - Resolver `reference_time` con el método existente `_resolve_reference_time` (ISO-8601 sin zona; inválido → `INVALID_REFERENCE_TIME`).
  - Llamar `self._incident_repository.list_active_incidents(reference_time=resolved, component=normalize_component_filter(component_filter))`.
  - Delegar la construcción del resumen en `src/domain/active_summary.build_active_incident_summary`: filtrado/ordenación por severidad-antigüedad-ID y evaluación SLA con `src/domain/sla_calculator.evaluate_sla_status`.
  - Mapear `ReferenceTimeBeforeCreationError` a `ValidationError("REFERENCE_TIME_BEFORE_CREATION", ...)`.
- **Racional**: la puerta SLA del dominio (Constitución I) evalúa el SLA; el repositorio optimizado devuelve activos; el caso de uso puro orquesta sin IO.
- **Alternativas**: reusar `summarize_active_incidents` — rechazado; `list_incidents` + filtro de activos en el caso de uso — rechazado por el hito (ver R3).

### R5 — Superficies entrantes (`src/adapters/inbound/`)

- **Decisión**:
  - `schemas.py`: introducir `ActiveIncidentItem` (campos: incident_id, title, component, severity, status, elapsed_minutes, is_breached, requires_escalation) y usar `List[ActiveIncidentItem]` en `ActiveIncidentSummaryResponse` (reemplazo de `ActiveIncidentDetailResponse`).
  - `app.py`: `GET /api/v1/incidents/summary` delega en `IncidentService.get_active_incidents_summary`.
  - `cli.py`: el comando `summary` usa el nuevo método del servicio.
- **Racional**: ambos adaptadores primarios deben usar el mismo caso de uso (Constitución II — paridad REST/CLI).
- **Alternativas**: mantener `ActiveIncidentDetailResponse` — rechazado (duplicación); cambiar el nombre a `ActiveIncidentItem` — acepetado por claridad del hito.

### R6 — Configuración estática con Ruff (Constitución IV)

- **Decisión**:
  - `pyproject.toml`: `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "TID"]`.
  - `src/domain/ruff.toml` y `src/application/ruff.toml`: `extend = "../../pyproject.toml"`; mismo `select`; `[lint.flake8-tidy-imports] ban-relative-imports = "parents"`; `[lint.flake8-tidy-imports.extend-banned-api]` con: fastapi, pydantic, typer, uvicorn, requests, httpx, sqlite3, psycopg, sqlalchemy, `src.application` (solo en el fichero de dominio) / `src.adapters` (solo en el fichero de aplicación).
  - `src/adapters/inbound/ruff.toml`: `extend = "../../../pyproject.toml"`; `ban-relative-imports = "parents"`; `extend-banned-api`: sqlite3, psycopg, sqlalchemy, `src.adapters.outbound.sqlite_repository` (el factory debe seguir importable).
- **Racional**: los sets baneados codifican la tabla de fronteras de la skill hexagonal (base normativa Constitución IV: dominio sin src/application ni src/adapters ni frameworks ni IO; aplicación sin src/adapters; inbound sin drivers ni repositorios concretos).
- **Alternativas**: usar `banned-api` en hijo — rechazado (sustituye la tabla heredada, usar `extend-banned-api`); banear `src.adapters.outbound` completo — rechazado (el factory debe seguir importable).
- **Señal de verificación**: `uv run ruff check src/` termina sin errores (quickstart.md).

### R7 — `tests/` (Hito 002)

- **Decisión**: extender `tests/test_spec_002_summary.py` sin romper las 4 escenarios H002; añadir:
  - Verificación de cumplimiento de puerto: `isinstance(SqliteIncidentRepository(":memory:"), IncidentRepositoryPort)`, `check_health() is True`, round-trip `save_incident`/`get_incident` y `find_open_duplicates == []`.
  - Casos BDD del adaptante: `list_active_incidents` por estado (`OPEN`/`IN_PROGRESS` excluye `ESCALATION_REQUIRED`/`RESOLVED`), filtro por componente normalizado, y `EXPLAIN QUERY PLAN` que use `idx_incidents_component_status`.
  - Caso de servicio: `get_active_incidents_summary` con `REFERENCE_TIME_BEFORE_CREATION` propagado como `ValidationError`.
- **Racional**: cumplimiento verificable del puerto desde el primer usuario del adaptante; todo el hito se cubre en un solo archivo de aceptación.
- **Alternativas**: archivo nuevo `tests/test_spec_003_repository.py` — rechazado por trazabilidad; usar solo BDD HTTP — rechazado (el puerto es del adaptante, no del observable HTTP).

## Artefactos generados

- `research.md` (este archivo — decisiones R1–R7).
- `data-model.md` — entidades y contratos.
- `contracts/incident_repository_port.md` — contrato del puerto.
- `contracts/sqlite_incident_repository.md` — esquema y SQL del adaptante saliente.
- `quickstart.md` — escenarios de validación ejecutables.
- `plan.md` — plan actualizado.

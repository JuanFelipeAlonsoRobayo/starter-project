# Research — Servicio en contenedores con base de datos relacional dedicada y chequeo de salud

## Decisiones de Phase 0

### R1 — Dependencia PostgreSQL: `psycopg[binary]` (sin ORM)

- **Decisión**: Nueva dependencia de ejecución `psycopg[binary]>=3.3.9`; sin ORM (mapeo de filas con `psycopg.rows.dict_row`; SQL parametrizada con `%s`; upsert con `INSERT ... ON CONFLICT DO UPDATE`).
- **Racional**: ADR-004 decide el motor relacional dedicado en contenedores; `psycopg[binary]` minimiza el costo de build (driver binario) sin añadir una capa de ORM que aligeraría el control táctico de SQL, coherente con el estilo "sin ORM" de `SqliteIncidentRepository` (Constitución III y ADR-004).
- **Alternativas**: `psycopg2`/`asyncpg` — rechazados: `asyncpg` es asíncrona (requiere reescribir el repositorio sinmétrico), `psycopg2` está desactualizada; ORM (SQLAlchemy) — rechazado por Constitución III ("sin ORMs pesados") y ADR-004.
- **Señal de verificación**: Importación de `psycopg` solo en `src/adapters/outbound/postgres_repository.py` (fronteras hexagonales); `uv.lock` incluye `psycopg[binary]`.

### R2 — Topología de contenedores (per ADR-004)

- **Decisión**: `db` = `postgres:16-alpine` con volumen `incidentops_pgdata` y healthcheck `pg_isready`; `api` sincronizado por `depends_on: db (condition: service_healthy)`; `DATABASE_URL=postgresql://incidentops:incidentops@db:5432/incidentops`.
- **Racional**: Reproducible (`docker compose up -d --wait`), aislado y con base de datos dedicada (objetivo H004); el chequeo `pg_isready` mejora la robustez del arranque sobre `depends_on` genérico.
- **Alternativas**: servidor PostgreSQL sin contenedores (rechazado por ADR-004 y por perder reproducibilidad y aislamiento); `Dockerfile` único con PostgreSQL embebido — rechazado: PostgreSQL embebido no es la norma de operabilidad y la decisión del ADR es contenedorizado.
- **Señal de verificación**: `docker-compose.yml` con servicios `api` y `db`; `api.healthcheck` GET `/health` sobre `localhost:8000`.

### R3 — Chequeo de salud real y sin caché

- **Decisión**: `GET /health` (adaptante HTTP) y `health` (adaptante CLI) ejecutan `SELECT 1` real contra la base configurada en cada petición; contrato 200/503 según RNF-002.
- **Racional**: "Chequeo real" — un `SELECT 1` sobre la conexión oculta caída de la conexión y valida la disponibilidad real del motor, a diferencia de un chequeo de proceso vivo o de un resultado cacheado; `IncidentService.check_health()` delega al puertoexistente y ambos adaptantes comparten el mismo contrato.
- **Alternativas**: `ping` del socket del driver — rechazado: no valida paridad temporal/tablas; chequeo a partir de un endpoint HTTP externo — rechazado por problemas de autenticación/privacidad de la infraestructura; `check_health` con timeout — se implementa en el driver (psycopg/sqlite connections aplican timeouts de conexión).
- **Señal de verificación**: `tests/test_spec_004_runtime_health.py` BDD: 200 `{"status":"ok","database":"connected"}` y 503 `{"status":"error","database":"unavailable"}` con doble de prueba (`check_health()` False).

### R4 — Imagen `api`: `python:3.12-slim` + `uv`

- **Decisión**: `FROM python:3.12-slim`; bootstrap de `uv` (`ghcr.io/astral-sh/uv:latest` → `/uv`); `uv sync --frozen --no-dev`; `CMD ["uv", "run", "--no-sync", "uvicorn", "src.adapters.inbound.api.app:app", "--host", "0.0.0.0", "--port", "8000"]`.
- **Racional**: `python:3.12-slim` es la base estándar (ligera) para servicios; `uv sync --frozen --no-dev` evita dev-deps en imagen de producción y garantiza reproducibilidad con `uv.lock`; `--no-sync` evita reinstalación en cada start.
- **Alternativas**: imagen base con `pip install -e` — rechazada (`[tool.uv] package = false` y Constitución II); usar `pg_ctl`/PostgreSQL embebido en la imagen — rechazado por ADR-004.
- **Señal de verificación**: `docker compose build api` produce imagen con dependencias de ejecución (`uv run --no-sync python -c "import psycopg, fastapi, uvicorn, typer"`).

## Artefactos generados

- `research.md` (este archivo — decisiones R1–R4).
- `data-model.md` — entidades: contrato `HealthResponse` y semántica del chequeo; `PostgresIncidentRepository` (esquema, índices, paridad temporal TEXT ISO 8601).
- `contracts/health_endpoint_contract.md` — contrato HTTP/CLI del chequeo de salud.
- `quickstart.md` — escenarios de validación ejecutables.
- `plan.md` — plan de implementación ( este archivo).

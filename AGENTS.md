# AGENTS.md

## Setup and execution

- Work from the repo root; the README's `cd week-1/starter-project` is stale. Use `uv sync`, then `uv run python -m src.<module>`.
- `[tool.uv] package = false`: this is not an installed package. Do not add `pip install -e .` or package metadata.
- Runtime dependencies include `fastapi`, `uvicorn`, `pydantic`, `typer`, and `tiktoken`; development dependencies include `pytest`, `httpx`, and `ruff`.
- Always use `uv run` for `src/context_audit.py`: without `tiktoken`, it silently switches to an approximate BPE estimator, making token counts incomparable with the documented `o200k_base` results.
- Acceptance tests are automated with `pytest` (`tests/test_spec_001_triage.py` and `tests/test_spec_002_summary.py`). There is no typechecker or CI config; `uv run ruff check src/` is the boundary gate, now with `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "TID"]` at root and per-layer `ruff.toml` files (`src/domain/`, `src/application/`, `src/adapters/inbound/`) with `extend` + `ban-relative-imports = "parents"` and per-layer `TID251` bans.
- `DATABASE_URL` selects the repository through `src/adapters/outbound/factory.py`; `create_incident_repository() -> IncidentRepositoryPort`. Accepted forms: a path (`/ruta/incidentops.db`), `sqlite:///ruta/incidentops.db`, or `sqlite:///:memory:` (default). The summary is read-only; it does not create or modify incidents.

## Commands

- `uv run pytest -q` — runs the BDD acceptance test suites for HTTP and CLI triage (`specs/001-triage-endpoint-manual.md`) and the active-incident summary (`specs/002-active-incident-summary/spec.md`).
- `uv run python -m src.adapters.inbound.cli triage --incident-id <id> --raw-text "<text>" [--human]` — invokes the CLI triage adapter in-process (default output is JSON).
- `uv run python -m src.adapters.inbound.cli summary [--component <componente>] [--reference-time <ISO-8601>]` — emits the active-incident summary as JSON; the same object is returned by `GET /api/v1/incidents/summary`.
- `uv run uvicorn src.adapters.inbound.api.app:app --reload` — starts the FastAPI HTTP adapter (`POST /triage` and `GET /api/v1/incidents/summary`).
- `uv run python -m src.domain.sla_calculator` — asserted SLA cases; run after changes to `src/domain/models.py` or `src/domain/sla_calculator.py`.
- `uv run python -m src.domain.triage_rules` — classifies the 10 records in `data/sample_incidents.json` and reports duplicate groups.
- `uv run python -m src.incident_repository --records 100 --iterations 2` — fast smoke run; defaults are 10,000 rows × 20 iterations.
- `uv run python -m src.context_audit --symbol <name>` — token audit for one symbol; `--compare-formats` instead compares JSON/YAML/CSV and overrides `--symbol`.

## Architecture and pitfalls

- Hexagonal Architecture (`docs/adr/003-arquitectura-hexagonal.md`, `docs/constitution.md`): dependencies point inward (`adapters/inbound` → `application` → `domain`).
  - `src/domain/`: pure deterministic models (`models.py`), triage rules (`triage_rules.py`), SLA calculation (`sla_calculator.py`), and the active-summary builder (`active_summary.py`) with no frameworks or runtime I/O. Paths to data/docs in `__main__` demos resolve relative to the repo root via `Path(__file__).resolve().parents[2]`.
  - `src/application/`: shared use case `IncidentService`, `ValidationError` (`services.py`), and the read ports `IncidentReadPort` (`ports.py`) and the repository port `IncidentRepositoryPort` (also in `ports.py`), free of FastAPI, Pydantic, Typer, and SQL.
  - `src/adapters/inbound/`: thin primary adapters for HTTP (`api/app.py`, `api/schemas.py`) and CLI (`cli.py`). Both delegate to `IncidentService` (`summarize_active_incidents`, `get_active_incidents_summary`).
  - `src/adapters/outbound/`: `SqliteIncidentRepository` (`sqlite_repository.py`) implements `IncidentRepositoryPort` and maps rows to domain `Incident` objects; `factory.py` selects it from `DATABASE_URL`. Business filtering and SLA evaluation stay in the domain.
- The full-table scan and N+1 queries in `src/incident_repository.py` are intentional teaching debt. Do not optimize them unless the task is the Phase 2 refactor. The H002 read adapter is now the optimized `SqliteIncidentRepository`: `INNER JOIN sla_policies` + índice compuesto `(component, status)` for the summary of active incidents.
- `reference_time` for the summary is optional, ISO-8601 without timezone; invalid values return `INVALID_REFERENCE_TIME` (422/CLI 2), and values before an active incident's creation return `REFERENCE_TIME_BEFORE_CREATION` (400/CLI 2). Empty results are 200/CLI 0 with zero totals and `incidents: []`.
- The detail exposes `is_breached` and `requires_escalation`, but not `allowed_minutes`; the limit is derived from the severity policy.
- SLA policy is `SLA_POLICY_TABLE` in `src/domain/sla_calculator.py`: P0/P1 are 24/7; P2/P3 count Mon–Fri 08:00–18:00; escalation triggers at 75% only while unresolved. `docs/adr/002-calculo-sla-horario-habil.md` records this decision — update the ADR and the asserted demo cases together if behavior changes.
- `src/context_audit.py` scans `src/**/*.py`, `data/*.json`, and `docs/adr/*.md`; `CONTEXT_LOG.md` and screenshots are excluded. Its "LSP" mode is an AST approximation with a hardcoded `related_types` set, and it special-cases `evaluate_sla_status` to include `get_sla_rule_for_severity`.
- `CONTEXT_LOG.md` is the Week-1 assignment record (blank template: `CONTEXT_LOG_TEMPLATE.md`); evidence images live in `Imagenes-Evidencias/`. New ADRs should follow `docs/adr/000-template.md`.

# AGENTS.md

## Setup and execution

- Work from the repo root; the README's `cd week-1/starter-project` is stale. Use `uv sync`, then `uv run python -m src.<module>`.
- `[tool.uv] package = false`: this is not an installed package. Do not add `pip install -e .` or package metadata.
- Runtime dependencies include `fastapi`, `uvicorn`, `pydantic`, `typer`, and `tiktoken`; development dependencies include `pytest` and `httpx`.
- Always use `uv run` for `src/context_audit.py`: without `tiktoken`, it silently switches to an approximate BPE estimator, making token counts incomparable with the documented `o200k_base` results.
- Acceptance tests are automated with `pytest` (`tests/test_spec_001_triage.py`). No linter, typechecker, or CI config exists; verification includes running `uv run pytest` and the module CLIs.

## Commands

- `uv run pytest -q` — runs the BDD acceptance test suite for HTTP and CLI triage (`specs/001-triage-endpoint-manual.md`).
- `uv run python -m src.adapters.inbound.cli triage --incident-id <id> --raw-text "<text>" [--human]` — invokes the CLI triage adapter in-process (default output is JSON).
- `uv run uvicorn src.adapters.inbound.api.app:app --reload` — starts the FastAPI HTTP adapter (`POST /triage`).
- `uv run python -m src.domain.sla_calculator` — asserted SLA cases; run after changes to `src/domain/models.py` or `src/domain/sla_calculator.py`.
- `uv run python -m src.domain.triage_rules` — classifies the 10 records in `data/sample_incidents.json` and reports duplicate groups.
- `uv run python -m src.incident_repository --records 100 --iterations 2` — fast smoke run; defaults are 10,000 rows × 20 iterations.
- `uv run python -m src.context_audit --symbol <name>` — token audit for one symbol; `--compare-formats` instead compares JSON/YAML/CSV and overrides `--symbol`.

## Architecture and pitfalls

- Hexagonal Architecture (`docs/adr/003-arquitectura-hexagonal.md`, `docs/constitution.md`): dependencies point inward (`adapters/inbound` → `application` → `domain`).
  - `src/domain/`: pure deterministic models (`models.py`), triage rules (`triage_rules.py`), and SLA calculation (`sla_calculator.py`) with no frameworks or runtime I/O. Paths to data/docs in `__main__` demos resolve relative to the repo root via `Path(__file__).resolve().parents[2]`.
  - `src/application/`: shared use case `IncidentService` and `ValidationError` (`services.py`), free of FastAPI, Pydantic, or Typer.
  - `src/adapters/inbound/`: thin primary adapters for HTTP (`api/app.py`, `api/schemas.py`) and CLI (`cli.py`).
- The full-table scan and N+1 queries in `src/incident_repository.py` are intentional teaching debt. Do not optimize them unless the task is the Phase 2 refactor.
- SLA policy is `SLA_POLICY_TABLE` in `src/domain/sla_calculator.py`: P0/P1 are 24/7; P2/P3 count Mon–Fri 08:00–18:00; escalation triggers at 75% only while unresolved. `docs/adr/002-calculo-sla-horario-habil.md` records this decision — update the ADR and the asserted demo cases together if behavior changes.
- `src/context_audit.py` scans `src/**/*.py`, `data/*.json`, and `docs/adr/*.md`; `CONTEXT_LOG.md` and screenshots are excluded. Its "LSP" mode is an AST approximation with a hardcoded `related_types` set, and it special-cases `evaluate_sla_status` to include `get_sla_rule_for_severity`.
- `CONTEXT_LOG.md` is the Week-1 assignment record (blank template: `CONTEXT_LOG_TEMPLATE.md`); evidence images live in `Imagenes-Evidencias/`. New ADRs should follow `docs/adr/000-template.md`.

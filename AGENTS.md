# AGENTS.md

## Setup and execution

- Work from the repo root; the README's `cd week-1/starter-project` is stale. Use `uv sync`, then `uv run python -m src.<module>`.
- `[tool.uv] package = false`: this is not an installed package. Do not add `pip install -e .` or package metadata.
- Always use `uv run` for `src/context_audit.py`: without `tiktoken`, it silently switches to an approximate BPE estimator, making token counts incomparable with the documented `o200k_base` results.
- No test runner, linter, typechecker, or CI config exists. Verification means running the module CLIs; `src/sla_calculator.py` is the only one with assertions.

## Commands

- `uv run python -m src.sla_calculator` — asserted SLA cases; run after changes to `src/models.py` or `src/sla_calculator.py`.
- `uv run python -m src.triage_rules` — classifies the 10 records in `data/sample_incidents.json` and reports duplicate groups.
- `uv run python -m src.incident_repository --records 100 --iterations 2` — fast smoke run; defaults are 10,000 rows × 20 iterations.
- `uv run python -m src.context_audit --symbol <name>` — token audit for one symbol; `--compare-formats` instead compares JSON/YAML/CSV and overrides `--symbol`.

## Architecture and pitfalls

- `src/*.py` are both importable modules and CLI scripts; shared dataclasses/Literals live in `src/models.py`. Paths to data/docs are resolved relative to the repo root via `Path(__file__).resolve().parent.parent`.
- The full-table scan and N+1 queries in `src/incident_repository.py` are intentional teaching debt. Do not optimize them unless the task is the Phase 2 refactor.
- SLA policy is `SLA_POLICY_TABLE` in `src/sla_calculator.py`: P0/P1 are 24/7; P2/P3 count Mon–Fri 08:00–18:00; escalation triggers at 75% only while unresolved. `docs/adr/002-calculo-sla-horario-habil.md` records this decision — update the ADR and the asserted demo cases together if behavior changes.
- `src/context_audit.py` scans only `src/*.py`, `data/*.json`, and `docs/adr/*.md`; `CONTEXT_LOG.md` and screenshots are excluded. Its "LSP" mode is an AST approximation with a hardcoded `related_types` set, and it special-cases `evaluate_sla_status` to include `get_sla_rule_for_severity`.
- `CONTEXT_LOG.md` is the Week-1 assignment record (blank template: `CONTEXT_LOG_TEMPLATE.md`); evidence images live in `Imagenes-Evidencias/`. New ADRs should follow `docs/adr/000-template.md`.

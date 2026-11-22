# Bitácora de Desarrollo Guiado por Especificaciones — Semana 2 (`SDD_LOG.md`)

**Estudiante**: `Juan Felipe Alonso Robayo`

**Fecha**: `2026-11-22`

**Modelos Utilizados en OpenCode (Plan/Razonamiento vs. Build/Implementación)**: `[Ej. Modelo de Razonamiento para Clarify, Plan y Analyze / Modelo rápido para Implement]`

---

## 1. Elicitación con `/speckit.clarify` y Auditoría con `/speckit.analyze`

### 1.1 Feature `003-incident-lifecycle-sla`
- **Ambigüedades y casos borde detectados con `/speckit.clarify`**:
  1. **Criterio de equivalencia / duplicado (`Q1 — Domain & Data Model`)**: El requerimiento crudo hablaba de "otro incidente equivalente abierto" sin definir la métrica (el borrador inicial asumió similitud textual del 80% por título, cuando en el dominio de IncidentOps la equivalencia determinista se evalúa por coincidencia exacta de `duplicate_group_key` únicamente en estados abiertos `OPEN`, `IN_PROGRESS` y `ESCALATION_REQUIRED`, excluyendo `RESOLVED` y el propio `incident_id` recién creado).
  2. **Integración del aviso de duplicados en la respuesta de creación (`Q2 — Interaction/UX & Edge`)**: Se aclaró que el aviso no es una alerta externa separada, sino que se integra directamente en la respuesta de creación (`201 Created` en `POST /api/v1/incidents` y JSON en CLI `create`) mediante los campos `is_duplicate` (`bool`) y `duplicate_of` (`list[str]` con los IDs equivalentes abiertos).
  3. **Semántica de incumplimiento (`is_breached`) frente a incidentes resueltos (`Q3 — Edge Cases`)**: Se precisó que `is_breached` refleja si `elapsed_minutes > allowed_minutes` para cualquier estado almacenado (incluido `RESOLVED`), mientras que `requires_escalation` solo puede ser `true` para incidentes aún no resueltos (coherente con `ADR-002`).
  4. **Contrato completo de auditoría de SLA y errores (`Q4 — Domain & Contract`)**: Se definió que `GET /api/v1/incidents/{incident_id}/sla` (y CLI `sla`) retorna los campos de `SLAEvaluation` (`incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached`, `requires_escalation`), respondiendo `404 Not Found` cuando el ID no existe y `422 Unprocessable Entity` (código `1` en CLI) cuando `reference_time < created_at`.
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**:
  - **Cobertura y métricas**: `100 %` de cobertura (`16/16` requisitos: `FR-001` a `FR-010` y `SC-001` a `SC-006`) mapeados sobre `26` tareas (`T001`–`T026`), con `0` tareas huérfanas, `0` duplicaciones y **`0` hallazgos `CRITICAL`** frente a la Constitución.
  - **Hallazgos detectados (`A1`–`A4`)**:
    - **`A1` (`Coverage — HIGH`)**: Varios campos restringidos de `data-model.md` (`Incident.recommended_team`, `IncidentCreationResult.*`, `CreateIncidentRequest.*`, `IncidentCreatedResponse.*` y `SLAEvaluationResponse.*`) estaban cubiertos a nivel de entidad en `T003`, `T005`, `T006` y `T016`, pero sin cita literal `Entity.field` campo por campo (mientras que `Incident.duplicate_group_key`, `is_duplicate`, `duplicate_of` e `idx_incidents_dup_key` sí tenían cita explícita).
    - **`A2` (`Constitution — MEDIUM`, no bloqueante)**: Señaló que el conjunto de estados abiertos (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`) usado por `find_open_duplicates` en `SqliteIncidentRepository` (`T011`) conviene mantenerlo alineado con una constante del dominio (`src/domain/`) como única fuente de verdad (Principio I de la Constitución).
    - **`A3` y `A4` (`Ambiguity / Terminology — LOW`)**: Sugirió uniformar en `spec.md` la palabra narrativa *"aviso"* con los nombres contractuales `is_duplicate` / `duplicate_of` y la redacción de la historia de usuario `US3`.

### 1.2 Feature `004-postgres-container-runtime`
- **Ambigüedades y RNF aclarados antes de diseñar PostgreSQL/Compose**:
  1. `[Pendiente al ejecutar /speckit.clarify en Reto 2: ej. contrato exacto de GET /health y CLI health (200 OK con {"status":"ok","database":"connected"} vs. 503 Service Unavailable con {"status":"error","database":"unavailable"})]`
  2. `[Pendiente: ej. selección transparente del adaptador por DATABASE_URL (postgresql://... vs. sqlite:///... o :memory: por defecto para pruebas locales sin Docker)]`
  3. `[Pendiente: ej. orden de arranque en Docker Compose mediante depends_on con condition: service_healthy sobre pg_isready y paridad de timestamps ISO-8601 en TEXT]`

---

## 2. Comparación Crítica: SDD Manual (Iteración 1) vs. GitHub Spec Kit (Iteración 2 y Retos)

| Dimensión Comparada | SDD Manual (Iteración 1: `001`) | GitHub Spec Kit (Iteración 2 y Retos: `002`–`004`) |
| :--- | :--- | :--- |
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** | Se redactó el contrato manual en `specs/001-triage-endpoint-manual.md` y el plan técnico separado en `docs/plan.md`, dependiendo de la disciplina manual para no mezclar reglas de negocio con rutas de archivos. | Estructura estandarizada por feature (`specs/00X-.../spec.md`, `plan.md`, `tasks.md`), donde `spec.md` se restringe al *QUÉ* y *POR QUÉ* en vocabulario de negocio, `plan.md` define el diseño hexagonal y `tasks.md` secuencia los pasos verificables. |
| **Gestión de ambigüedades (`/speckit.clarify`)** | Las dudas (recorte con `strip`, códigos `EMPTY_RAW_TEXT` vs. `RAW_TEXT_TOO_LONG`) se resolvieron de forma ad-hoc antes o durante la codificación. | Fase explícita e interactiva (`/speckit.clarify`) que obliga a identificar y registrar decisiones sobre casos borde (estados activos, `reference_time`, duplicados abiertos, `/health` 503) en la sección `Clarifications` antes de planificar. |
| **Consistencia contra la Constitución (`/speckit.analyze`)** | Verificación manual revisando `docs/constitution.md` y `ADR-003` para comprobar que los adaptadores no duplicaran `triage_rules.py`. | Compuerta automatizada (`/speckit.analyze`) que cruza `spec.md`, `plan.md` y `tasks.md` contra `.specify/memory/constitution.md`, detectando violaciones de fronteras o requisitos huérfanos antes de escribir código. |
| **Riesgo de verbosidad / exceso de Markdown** | Bajo volumen de texto (documentos cortos y directos), pero con mayor riesgo de omitir casos borde o criterios no funcionales. | Alto riesgo de generar documentos extensos y repetitivos si no se acota al agente, requiriendo curaduría humana activa para mantener `plan.md` y `tasks.md` concisos. |

- **Análisis basado en MartinFowler.com (Birgitta Böckeler)**:
  1. **De los tres niveles descritos por Böckeler (*Spec-first*, *Spec-anchored*, *Spec-as-source*), ¿en cuál ubicas este proyecto de *IncidentOps* y por qué?**
     - Se ubica en **Spec-anchored** (evolucionando desde *Spec-first*). No es *Spec-as-source* porque el humano sigue editando y manteniendo directamente el código Python (`src/`) como artefacto ejecutable junto con las especificaciones; sin embargo, supera el simple *Spec-first* de un solo uso porque las especificaciones (`specs/001` a `004`), la Constitución (`.specify/memory/constitution.md`) y los ADRs (`ADR-002`, `ADR-003`, `ADR-004`) permanecen vivas en el repositorio, ancladas a pruebas de aceptación BDD ejecutables (`tests/test_spec_00*.py`) y reglas estáticas (`ruff.toml`) que impiden que el código derive respecto de la especificación en los siguientes hitos.
  2. **Böckeler advierte que los *toolkits* SDD pueden generar "montañas de Markdown" difíciles de revisar para un humano. ¿Qué técnicas aplicaste (concisión en `docs/ROADMAP.md`, curaduría en `clarify`/`plan`/`tasks` y pruebas deterministas en `pytest`) para evitar aprobar especificaciones verbosas a ciegas?**
     - Primero, mantener `docs/ROADMAP.md` y `docs/constitution.md` breves y normativos para no inflar el contexto base. Segundo, acotar `/speckit.clarify` a decisiones concretas de frontera (tablas de códigos de error y 4–5 escenarios BDD estilo Dan North) y exigir desgloses cortos en `/speckit.plan` y `/speckit.tasks`. Tercero, no confiar en el Markdown por inspección visual únicamente, sino traducir cada escenario BDD 1:1 a pruebas deterministas en `pytest` (`TestClient` y `CliRunner`) y validar las fronteras hexagonales con `uv run ruff check src/`.

---

## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning*

- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-architecture`, `bdd-acceptance`, `adr-writer`)**:
  - Los **Commands** (`.opencode/commands/speckit.*.md`) son flujos de trabajo invocados explícitamente por el usuario en un momento puntual de la tubería (especificar, clarificar, planificar, desglosar tareas, analizar o implementar). En cambio, las **Agent Skills** (`.opencode/skills/<nombre>/SKILL.md`) son capacidades modulares especializadas que OpenCode descubre por su frontmatter (`name` y `description`) y carga **bajo demanda** (*progressive disclosure*) solo cuando la tarea activa lo requiere, ahorrando ventana de contexto.
  - Seguir el orden causal **ADR $\rightarrow$ Constitución $\rightarrow$ Hito** fue indispensable porque el ADR (`ADR-003` para Arquitectura Hexagonal y `ADR-004` para PostgreSQL + Docker Compose) evalúa las opciones y toma una decisión estructural inmutable; luego la Constitución (`docs/constitution.md` y `.specify/memory/constitution.md`) convierte esa decisión en regla normativa; y solo entonces `/speckit.specify`, `/speckit.plan` y `/speckit.analyze` pueden diseñar y auditar el Hito `004` sin entrar en contradicción con la regla previa de "solo SQLite estándar".
- **Valor de la Arquitectura Hexagonal**:
  - Centralizar la lógica de aplicación en `IncidentService` (`src/application/services.py`) y abstraer la persistencia detrás de `IncidentRepositoryPort` (`src/application/ports.py`) permitió que tanto FastAPI (`src/adapters/inbound/api/app.py`) como Typer (`src/adapters/inbound/cli.py`) compartieran exactamente los mismos casos de uso (`triage`, `summary`, `create`, `sla`, `health`) con paridad total de contratos, y que en el Hito `004` se incorporara `PostgresIncidentRepository` junto a `SqliteIncidentRepository` (seleccionados por `factory.py` vía `DATABASE_URL`) sin modificar una sola línea de `src/domain/`. Esto deja el núcleo listo para agregar futuros adaptadores primarios (como un servidor MCP) o secundarios sin riesgo de regresión en las reglas de negocio.
- **Uso intencional de *Reasoning / Extended Thinking* en OpenCode**:
  - El razonamiento extendido aportó mayor valor en **`/speckit.clarify`**, **`/speckit.plan`** y **`/speckit.analyze`**, donde el modelo debía anticipar casos borde (intersección de horario hábil con zonas horarias, criterio de duplicados abiertos excluyendo `RESOLVED`, fallos `503` de conectividad) y verificar invariantes entre múltiples documentos y capas. En cambio, para **`/speckit.implement`**, una vez que las decisiones ya estaban cerradas y desglosadas en tareas atómicas dentro de `tasks.md`, un modelo más rápido resultó más eficiente en latencia y costo para traducir el plan a código y validarlo con `pytest` y `ruff`.

---

## 4. Evidencia de Verificación Determinista

> **Nota**: A continuación se registra la evidencia base inicial verificada (Hitos `001` y `002`). Al completar los Retos 1 (`003`) y 2 (`004`), actualiza estos tres bloques con la salida final que incluya también `test_spec_003_lifecycle_sla.py`, `test_spec_004_runtime_health.py`, los comandos CLI `create`/`sla`/`health` y `docker compose config`.

- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**:
```text
All checks passed!
```

- **Salida completa de `uv run pytest -v` (Línea base inicial Hitos `001` y `002`)**:
```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0 -- /home/sexdeg/Proyectos/starter-project/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/sexdeg/Proyectos/starter-project
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 24 items

tests/test_spec_001_triage.py::test_scenario_1_http_502_payments_outage_classified_as_p0 PASSED [  4%]
tests/test_spec_001_triage.py::test_scenario_2_http_locked_account_mentioning_hoy_is_p2_not_p0 PASSED [  8%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[INC-1003- -EMPTY_RAW_TEXT] PASSED [ 12%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[-La pasarela de pagos devuelve 502-EMPTY_INCIDENT_ID] PASSED [ 16%]
tests/test_spec_001_triage.py::test_scenario_4_cli_parity_with_http PASSED [ 20%]
tests/test_spec_002_summary.py::test_bdd_global_summary_excludes_resolved PASSED [ 25%]
tests/test_spec_002_summary.py::test_bdd_summary_filtered_by_component PASSED [ 29%]
tests/test_spec_002_summary.py::test_bdd_empty_summary_is_successful[incidents0-params0] PASSED [ 33%]
tests/test_spec_002_summary.py::test_bdd_empty_summary_is_successful[incidents1-params1] PASSED [ 37%]
tests/test_spec_002_summary.py::test_bdd_cli_parity_with_http PASSED     [ 41%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[no-es-fecha] PASSED [ 45%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[2026-02-30T10:00:00] PASSED [ 50%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[2026-11-20T12:00:00Z] PASSED [ 54%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[2026-11-20T12:00:00+00:00] PASSED [ 58%]
tests/test_spec_002_summary.py::test_contract_reference_time_before_creation_returns_400 PASSED [ 62%]
tests/test_spec_002_summary.py::test_contract_cli_invalid_reference_time_exits_2 PASSED [ 66%]
tests/test_spec_002_summary.py::test_contract_blank_component_means_no_filter PASSED [ 70%]
tests/test_spec_002_summary.py::test_contract_escalation_required_status_is_not_active PASSED [ 75%]
tests/test_spec_002_summary.py::test_contract_breach_and_escalation_boundaries PASSED [ 79%]
tests/test_spec_002_summary.py::test_contract_cli_empty_summary_exits_0 PASSED [ 83%]
tests/test_spec_002_summary.py::test_port_compliance_over_sqlite_repository PASSED [ 87%]
tests/test_spec_002_summary.py::test_repository_save_get_and_find_open_duplicates PASSED [ 91%]
tests/test_spec_002_summary.py::test_list_active_incidents_status_and_component_filter PASSED [ 95%]
tests/test_spec_002_summary.py::test_service_get_active_incidents_summary_uses_port_and_maps_errors PASSED [100%]

======================== 24 passed, 1 warning in 0.34s =========================
```

- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose up --build`)**:
```text
$ uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "La pasarela de pagos devuelve 502 al intentar cobrar con tarjeta"
{"incident_id": "INC-1001", "severity": "P0", "component": "payments-gateway", "recommended_team": "Backend-Core", "duplicate_group_key": "payments-gateway:http-502-outage", "rationale": "Indisponibilidad global en pasarela de pagos (HTTP 502 Bad Gateway) que impide procesar transacciones."}

$ uv run python -m src.adapters.inbound.cli summary --reference-time "2026-11-20T12:00:00"
{"reference_time": "2026-11-20T12:00:00", "component": null, "total_active": 0, "breached_count": 0, "incidents": []}

[Pendiente al finalizar el Reto 2: pega aquí la salida de `cli health` y `docker compose config -q && echo "Compose OK"`]
```

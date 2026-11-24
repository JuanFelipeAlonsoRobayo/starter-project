# Bitácora de Desarrollo Guiado por Especificaciones — Semana 2 (`SDD_LOG.md`)

**Fecha**: `2026-11-22`

**Estudiante(s)**: `Juan Felipe Alonso Robayo`

**Link al repositorio**: `https://github.com/JuanFelipeAlonsoRobayo/starter-project.git`

**Modelos Utilizados en OpenCode (Plan/Razonamiento vs. Build/Implementación)**: `Tidepool Alpha Free en OpenCode (Modo Plan / Reasoning para specify, clarify, plan y analyze; Modo Build para implement)`

---

## 1. Elicitación con `/speckit.clarify` y Auditoría con `/speckit.analyze`

### 1.1 Feature `003-incident-lifecycle-sla`
- **Ambigüedades y casos borde detectados con `/speckit.clarify`**:
  1. **Cómo definir que dos incidentes son "equivalentes"**: El requerimiento inicial solo indicaba *"avisar si ya había otro equivalente abierto"*. Al ejecutar `/speckit.clarify`, el asistente asumió inicialmente comparar los títulos mediante una similitud de texto del 80% (Levenshtein/Jaccard). Con la aclaración se definió que en el proyecto la equivalencia se evalúa por coincidencia exacta de `duplicate_group_key`, filtrando únicamente estados abiertos (`OPEN`, `IN_PROGRESS` y `ESCALATION_REQUIRED`) y dejando por fuera los `RESOLVED` y el propio `incident_id` recién creado.
  2. **Dónde mostrar el aviso de duplicados**: Faltaba definir si el aviso debía ser una notificación independiente o parte de la respuesta al crear el ticket. Durante la primera pasada interactiva se seleccionó por error la opción de alerta separada, por lo que antes de pasar al plan se corrigió la especificación para que el aviso quedara integrado en el mismo `201 Created` de `POST /api/v1/incidents` (y en el JSON de `cli create`) mediante los campos `is_duplicate` (`bool`) y `duplicate_of` (`list[str]`).
  3. **Comportamiento de `is_breached` cuando el incidente ya está resuelto**: Se aclaró que `is_breached` debe seguir marcando `true` si los minutos transcurridos superaron el límite de la severidad sin importar si el estado almacenado es `RESOLVED`, mientras que `requires_escalation` solo se activa cuando el ticket sigue sin resolverse (tal como se había definido en el `ADR-002`).
  4. **Campos exactos al consultar "¿cómo va su SLA?" y casos de error**: Dado que el enunciado original era muy abierto, se acotó la respuesta a los campos de `SLAEvaluation` (`incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached`, `requires_escalation`) y se definieron dos errores concretos: `404 Not Found` cuando el ID no existe en la base de datos, y `422 Unprocessable Entity` (código de salida `1` en CLI) cuando `reference_time < created_at`.
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**:
  - La auditoría cruzó `spec.md`, `plan.md`, `tasks.md` y `data-model.md` contra la Constitución, arrojando **100 % de cobertura** (`16/16` requisitos cubiertos en `26` tareas, `T001`–`T026`) y **0 errores críticos (`CRITICAL`)**.
  - Reportó cuatro puntos de mejora (`A1` a `A4`): el principal (`A1 — HIGH`) fue que varias tareas de `tasks.md` (`T003`, `T005`, `T006`, `T016`) mencionaban las entidades de `data-model.md` de forma general sin citar cada atributo con el formato `Entity.field`. También dejó una observación media (`A2`) recordando que los estados abiertos usados en la consulta SQL de `find_open_duplicates` deben mantenerse alineados con el dominio como única fuente de verdad, y dos ajustes menores (`A3`, `A4`) para reemplazar la palabra *"aviso"* por los nombres reales de los campos `is_duplicate` y `duplicate_of`.

### 1.2 Feature `004-postgres-container-runtime`
- **Ambigüedades y RNF aclarados antes de diseñar PostgreSQL/Compose**:
  1. **Por dónde exponer el chequeo de salud (`HTTP`, `CLI` o ambos)**: Al ejecutar `/speckit.clarify`, la única duda funcional abierta fue el canal de exposición del healthcheck, dado que el resto de decisiones ya venían acotadas desde el `ADR-004` y la Constitución actualizada. Se seleccionó la opción `C` para exponerlo tanto en `GET /health` como en el subcomando `cli health` con el mismo JSON de salida.
  2. **Chequeo real en vivo sin caché y respuestas `200` / `503`**: Se dejó explícito como requisito no funcional de observabilidad que `/health` no puede limitarse a confirmar que el proceso web está activo ni guardar resultados en caché; debe ejecutar `SELECT 1` contra la base configurada en cada petición y responder `200 OK` (`{"status": "ok", "database": "connected"}`) o `503 Service Unavailable` (`{"status": "error", "database": "unavailable"}`) si el motor no responde.
  3. **Selección transparente SQLite/PostgreSQL por `DATABASE_URL` y orden de arranque en Docker Compose**: Se fijaron los RNF de portabilidad para que `postgresql://...` active `PostgresIncidentRepository` (`psycopg[binary]` sin ORM) y `sqlite:///...` (o `:memory:` por defecto cuando no existe la variable) utilice `SqliteIncidentRepository`, permitiendo ejecutar toda la suite de `pytest` en local sin depender del daemon de Docker. Para la ejecución en contenedores se definió sincronizar `api` con `db` (`postgres:16-alpine`) mediante `depends_on` con `condition: service_healthy` sobre `pg_isready`.
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**:
  - Se validó el **100 % de cobertura** (`11/11` requisitos repartidos en `16` tareas, `T001`–`T016`) y **0 incumplimientos críticos** frente a la Constitución actualizada con el `ADR-004`.
  - Se detectaron detalles puntuales de trazabilidad (`B3`, `C1`, `C2` de severidad media): agregar en `T008` la verificación explícita `isinstance(create_repository("postgresql://..."), PostgresIncidentRepository)`, referenciar `IncidentService.check_health` en `T010` e `incidents.created_at` (almacenado como `TEXT` ISO 8601 para mantener paridad temporal entre SQLite y PostgreSQL) en `T006`, además de eliminar una sección vacía que había quedado en `data-model.md`.

---

## 2. Comparación Crítica: SDD Manual (Iteración 1) vs. GitHub Spec Kit (Iteración 2 y Retos)

| Dimensión Comparada | SDD Manual (Iteración 1: `001`) | GitHub Spec Kit (Iteración 2 y Retos: `002`–`004`) |
| :--- | :--- | :--- |
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** | En el hito `001` se redactó el contrato en `specs/001-triage-endpoint-manual.md` y el plan en `docs/plan.md` de forma manual, dependiendo de la revisión propia para no mezclar reglas de negocio con nombres de archivos o librerías. | Cada feature cuenta con su carpeta (`specs/002-...`, `003-...`, `004-...`) y plantillas separadas: `spec.md` se enfoca solo en el problema y escenarios BDD, `plan.md` aterriza la arquitectura hexagonal y `tasks.md` secuencia los pasos de código. |
| **Gestión de ambigüedades (`/speckit.clarify`)** | Las dudas sobre validaciones o casos borde (como aplicar `strip` a `raw_text` o diferenciar `400` de `422`) se resolvieron sobre la marcha al escribir el plan o la implementación. | `/speckit.clarify` detiene el flujo antes de diseñar y formula preguntas puntuales de opción múltiple, registrando lo acordado en `## Clarifications` dentro de `spec.md` para no programar sobre supuestos del modelo. |
| **Consistencia contra la Constitución (`/speckit.analyze`)** | Se revisó manualmente `docs/constitution.md` y el `ADR-003` para confirmar que FastAPI o Typer no incluyeran lógica perteneciente a `src/domain/`. | `/speckit.analyze` verifica en modo solo lectura que todos los `FR` y `SC` tengan tareas asignadas en `tasks.md` y que el plan no contradiga `.specify/memory/constitution.md` antes de ejecutar `/speckit.implement`. |
| **Riesgo de verbosidad / exceso de Markdown** | Documentos más cortos y directos de revisar, aunque con mayor riesgo de pasar por alto algún caso borde en la especificación inicial. | Genera múltiples archivos Markdown (`spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`), por lo que si no se revisan y acotan las salidas se acumula bastante texto repetido. |

- **Análisis basado en Birgitta Böckeler**:
  1. **De los tres niveles descritos por Böckeler (*Spec-first*, *Spec-anchored*, *Spec-as-source*), ¿en cuál ubicas este proyecto de *IncidentOps* y por qué?**
     - El proyecto se ubica en **Spec-anchored**. No corresponde a *Spec-as-source* porque las especificaciones Markdown no se compilan por sí solas ni reemplazan al código fuente: los módulos Python en `src/` se siguen manteniendo y versionando directamente. Sin embargo, supera el nivel *Spec-first* (donde el documento se descarta tras generar el código inicial), ya que las especificaciones (`001` a `004`), la Constitución y los ADRs permanecen activos a lo largo de las iteraciones y quedan anclados a pruebas BDD en `pytest` y a reglas estáticas en `ruff.toml` que obligan a que el código siga cumpliendo lo especificado al incorporar nuevas funcionalidades.
  2. **Böckeler advierte que los *toolkits* SDD pueden generar "montañas de Markdown" difíciles de revisar para un humano. ¿Qué técnicas aplicaste (concisión en `docs/ROADMAP.md`, curaduría en `clarify`/`plan`/`tasks` y pruebas deterministas en `pytest`) para evitar aprobar especificaciones verbosas a ciegas?**
     - Durante el desarrollo se evidenció lo que advierte Böckeler: por cada feature Spec Kit genera hasta 6 o 7 archivos Markdown. Para evitar aprobar texto a ciegas se aplicaron tres prácticas: primero, mantener `docs/ROADMAP.md` y `docs/constitution.md` cortos y puntuales para no arrastrar ruido desde el contexto base. Segundo, intervenir durante `/speckit.clarify` y `/speckit.plan` definiendo contratos concretos (campos exactos, códigos HTTP y escenarios `Given/When/Then` acotados) y corrigiendo la especificación cuando se marcó una opción equivocada en la pregunta `Q2` del Reto 1. Tercero, apoyarse en `uv run pytest -v` y `uv run ruff check src/` como validación real: más allá de la extensión del Markdown, lo que confirma que el comportamiento es correcto son las pruebas BDD ejecutándose sobre `TestClient` y `CliRunner`.

---

## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning*

- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-architecture`, `bdd-acceptance`, `adr-writer`)**:
  - Los **Commands** (`.opencode/commands/speckit.*.md`) son pasos del flujo de trabajo que se invocan explícitamente con `/speckit.specify`, `/speckit.clarify`, `/speckit.plan`, etc., actuando como etapas secuenciales de una tubería. En cambio, las **Agent Skills** (`.opencode/skills/<skill>/SKILL.md`) encapsulan reglas y criterios específicos del proyecto que OpenCode solo carga en contexto bajo demanda cuando identifica por su `description` que la tarea actual los necesita (por ejemplo, al redactar un ADR activa `adr-writer`, o al modificar capas de `src/` activa `hexagonal-architecture`).
  - Respetar el orden causal **ADR $\rightarrow$ Constitución $\rightarrow$ Hito** fue determinante porque Spec Kit toma la Constitución como regla innegociable. En el Reto 2, la Constitución original restringía la persistencia a `sqlite3` estándar; si se hubiera ejecutado `/speckit.specify` para PostgreSQL sin antes redactar el `ADR-004` y actualizar `.specify/memory/constitution.md` mediante `/speckit.constitution`, `/speckit.analyze` lo habría rechazado como conflicto `CRITICAL`. Además, realizar esa actualización primero permitió que en el `/speckit.clarify` del Hito `004` el agente ya contara con casi todo el contexto arquitectónico resuelto y solo formulara una pregunta.
- **Valor de la Arquitectura Hexagonal**:
  - Centralizar los casos de uso en `IncidentService` (`src/application/services.py`) y abstraer la persistencia mediante `IncidentRepositoryPort` (`src/application/ports.py`) evitó duplicar lógica entre los hitos `001` y `004`. Tanto FastAPI como Typer operan como adaptadores delgados que invocan exactamente los mismos métodos (`triage_incident`, `summarize_active_incidents`, `create_incident`, `evaluate_incident_sla`, `check_health`), garantizando paridad en las respuestas JSON entre API y CLI. Asimismo, en el Hito `004`, incorporar `PostgresIncidentRepository` y seleccionarlo en `factory.py` a partir de `DATABASE_URL` no requirió modificar ninguna línea de `src/domain/`. Si en el futuro se requiere un adaptador MCP, bastará con agregarlo en `src/adapters/inbound/` reutilizando `IncidentService`.
- **Uso intencional de *Reasoning / Extended Thinking* en OpenCode**:
  - El modo de razonamiento aportó mayor valor en **`/speckit.clarify`**, **`/speckit.plan`** y **`/speckit.analyze`**, donde el modelo debe contrastar varios artefactos simultáneamente, identificar casos borde (cruces de horario hábil con fines de semana, estados excluidos al buscar duplicados abiertos o sincronización de arranque entre los contenedores `api` y `db`) y verificar que ninguna capa incumpla las reglas de `ruff.toml`. Por el contrario, durante **`/speckit.implement`**, al estar las decisiones ya cerradas y desglosadas en tareas concretas dentro de `tasks.md`, un flujo directo en Modo Build resultó más ágil para escribir el código y validarlo con `pytest`.

---

## 4. Evidencia de Verificación Determinista

- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**:
```text
All checks passed!
```

- **Salida completa de `uv run pytest -v`**:
```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0 -- /home/sexdeg/Proyectos/starter-project/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/sexdeg/Proyectos/starter-project
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 34 items

tests/test_spec_001_triage.py::test_scenario_1_http_502_payments_outage_classified_as_p0 PASSED [  2%]
tests/test_spec_001_triage.py::test_scenario_2_http_locked_account_mentioning_hoy_is_p2_not_p0 PASSED [  5%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[INC-1003- -EMPTY_RAW_TEXT] PASSED [  8%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[-La pasarela de pagos devuelve 502-EMPTY_INCIDENT_ID] PASSED [ 11%]
tests/test_spec_001_triage.py::test_scenario_4_cli_parity_with_http PASSED [ 14%]
tests/test_spec_002_summary.py::test_bdd_global_summary_excludes_resolved PASSED [ 17%]
tests/test_spec_002_summary.py::test_bdd_summary_filtered_by_component PASSED [ 20%]
tests/test_spec_002_summary.py::test_bdd_empty_summary_is_successful[incidents0-params0] PASSED [ 23%]
tests/test_spec_002_summary.py::test_bdd_empty_summary_is_successful[incidents1-params1] PASSED [ 26%]
tests/test_spec_002_summary.py::test_bdd_cli_parity_with_http PASSED     [ 29%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[no-es-fecha] PASSED [ 32%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[2026-02-30T10:00:00] PASSED [ 35%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[2026-11-20T12:00:00Z] PASSED [ 38%]
tests/test_spec_002_summary.py::test_contract_invalid_reference_time_returns_422[2026-11-20T12:00:00+00:00] PASSED [ 41%]
tests/test_spec_002_summary.py::test_contract_reference_time_before_creation_returns_400 PASSED [ 44%]
tests/test_spec_002_summary.py::test_contract_cli_invalid_reference_time_exits_2 PASSED [ 47%]
tests/test_spec_002_summary.py::test_contract_blank_component_means_no_filter PASSED [ 50%]
tests/test_spec_002_summary.py::test_contract_escalation_required_status_is_not_active PASSED [ 52%]
tests/test_spec_002_summary.py::test_contract_breach_and_escalation_boundaries PASSED [ 55%]
tests/test_spec_002_summary.py::test_contract_cli_empty_summary_exits_0 PASSED [ 58%]
tests/test_spec_002_summary.py::test_port_compliance_over_sqlite_repository PASSED [ 61%]
tests/test_spec_002_summary.py::test_repository_save_get_and_find_open_duplicates PASSED [ 64%]
tests/test_spec_002_summary.py::test_list_active_incidents_status_and_component_filter PASSED [ 67%]
tests/test_spec_002_summary.py::test_service_get_active_incidents_summary_uses_port_and_maps_errors PASSED [ 70%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_creation_without_previous_duplicates PASSED [ 73%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_creation_detects_open_duplicate PASSED [ 76%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_sla_audit_business_hours_deterministic PASSED [ 79%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_sla_audit_not_found_and_before_creation PASSED [ 82%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_cli_create_and_sla_equivalent PASSED [ 85%]
tests/test_spec_004_runtime_health.py::test_health_ok_http_and_cli PASSED [ 88%]
tests/test_spec_004_runtime_health.py::test_health_unavailable_http PASSED [ 91%]
tests/test_spec_004_runtime_health.py::test_health_unavailable_cli PASSED [ 94%]
tests/test_spec_004_runtime_health.py::test_create_repository_dual_selection PASSED [ 97%]
tests/test_spec_004_runtime_health.py::test_docker_compose_structure PASSED [100%]

============================== 34 passed in 1.13s ==============================
```

- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose up --build`)**:
```text
$ uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "La pasarela de pagos devuelve 502 al intentar cobrar con tarjeta"
{"incident_id": "INC-1001", "severity": "P0", "component": "payments-gateway", "recommended_team": "Backend-Core", "duplicate_group_key": "payments-gateway:http-502-outage", "rationale": "Indisponibilidad global en pasarela de pagos (HTTP 502 Bad Gateway) que impide procesar transacciones."}

$ uv run python -m src.adapters.inbound.cli summary --reference-time "2026-11-20T12:00:00"
{"reference_time": "2026-11-20T12:00:00", "component": null, "total_active": 0, "breached_count": 0, "incidents": []}

$ uv run python -m src.adapters.inbound.cli create --incident-id INC-3999 --title "Caída pagos 502" --raw-text "La pasarela de pagos devuelve 502 al cobrar con tarjeta" --created-at "2026-11-06T17:00:00"
{"incident_id": "INC-3999", "severity": "P0", "component": "payments-gateway", "recommended_team": "Backend-Core", "duplicate_group_key": "payments-gateway:http-502-outage", "rationale": "Indisponibilidad global en pasarela de pagos (HTTP 502 Bad Gateway) que impide procesar transacciones.", "is_duplicate": false, "duplicate_of": []}

$ uv run python -m src.adapters.inbound.cli health
{"status": "ok", "database": "connected"}

$ docker compose config -q && echo "Compose OK"
Compose OK

$ docker compose config
name: starter-project
services:
  api:
    environment:
      DATABASE_URL: postgresql://incidentops:incidentops@db:5432/incidentops
    networks:
      default: null
    build:
      context: /home/sexdeg/Proyectos/starter-project
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
        required: true
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/health',
          timeout=2)
      timeout: 5s
      interval: 15s
      retries: 5
    ports:
      - mode: ingress
        target: 8000
        published: "8000"
        protocol: tcp
  db:
    environment:
      POSTGRES_DB: incidentops
      POSTGRES_PASSWORD: incidentops
      POSTGRES_USER: incidentops
    image: postgres:16-alpine
    networks:
      default: null
    volumes:
      - type: volume
        source: incidentops_pgdata
        target: /var/lib/postgresql/data
        volume: {}
    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U incidentops
      timeout: 5s
      interval: 10s
      retries: 10
networks:
  default:
    name: starter-project_default
volumes:
  incidentops_pgdata:
    name: starter-project_incidentops_pgdata
```

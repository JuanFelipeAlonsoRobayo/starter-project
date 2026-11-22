# Research — Hito 003: Creación de incidentes, detección de duplicados y auditoría de SLA

## Decisiones de Phase 0

### R1 — Generación de ID en creación

- **Decisión**: `IncidentService.create_incident` autogenera `incident_id` con formato `INC-<HEX8>` (`uuid4().hex[:8]`) si se omite; si se proporciona, se usa el valor dado.
- **Racional**: el contrato del feature (acuerdos del equipo) fija el formato `INC-<HEX8>`; el repo legacy (`src/incident_repository.py`) sigue usando `INC-{idx:05d}` para otros flujos (semilla H002) — no se modifica.
- **Alternativas**: `INC-{idx:05d}` legacy — rechazada (el contrato del feature lo anula para identificadores nuevos).
- **Señal de verificación**: una creación sin `incident_id` produce un ID que coincide con `^INC-[0-9a-f]{8}$`; una creación con `incident_id="INC-CUSTOM"` lo persiste verbatim.

### R2 — Exit codes CLI (contrato del equipo)

- **Decisión**:
  - `cli create`: `ValidationError` (EMPTY_TITLE/EMPTY_RAW_TEXT/INVALID_*) → exit 1 (acuerdo del equipo: 422 ↔ exit 1).
  - `cli sla`: `IncidentNotFoundError` → exit 2 + `INCIDENT_NOT_FOUND`; `REFERENCE_TIME_BEFORE_CREATION` → exit 1 (acuerdo: 422 ↔ exit 1).
- **Racional**: coherente con la figura del feature en H003 (vacíos/inválidos → 1; ID desconocido → 2 como caso esperado).
- **Alternativas**: exit 2 para not-found en sla — rechazada (decisión documentada).
- **Señal de verificación**: test BDD de CLI aserta códigos de salida (1 para create, 2 para not-found en sla).

### R3 — Normalización naive/aware de marcas temporales

- **Decisión**: `src/domain/sla_calculator.py` añade `to_naive_utc(value) -> datetime`: aware → `astimezone(timezone.utc).replace(tzinfo=None)`; naive → as-is (convención existente: naive = UTC).
- **Aplicación**: `evaluate_sla_status` normaliza `created_at`, `resolved_at` y `reference_time` antes de comparar; `IncidentService.evaluate_incident_sla` normaliza `reference_time` recibido (str/datetime, tolerante a sufijo `Z`) antes de llamar al dominio.
- **Racional**: el dominio ya trabaja con naive (`services.py` usa `datetime.now()` sin zona; el repo persiste `isoformat()` de naive); normalizar en la frontera evita comparaciones aware-vs-naive.
- **Alternativas**: rechazar aware (como H002) — rechazada (acuerdo del equipo: normalización).
- **Señal de verificación**: test: `evaluate_incident_sla(id, reference_time="2026-11-09T11:00:00+02:00")` ≡ `reference_time="2026-11-09T09:00:00"`.

### R4 — Estados "abiertos" para duplicados

- **Decisión**: `find_open_duplicates` filtra `status IN ('OPEN', 'IN_PROGRESS', 'ESCALATION_REQUIRED')` (acuerdo del equipo, Q1 del clarify); `RESOLVED` queda excluido.
- **Racional**: `ESCALATION_REQUIRED` es estado almacenado del dominio (`IncidentStatus`) y el usuario lo incluye en el acuerdo; el SQL actual del repo usa solo `('OPEN', 'IN_PROGRESS')`.
- **Alternativas**: filtrar solo OPEN/IN_PROGRESS — rechazada.
- **Señal de verificación**: test BDD: duplicado con status `ESCALATION_REQUIRED` → `is_duplicate=true`; con `RESOLVED` → `is_duplicate=false`, `duplicate_of=[]`.

### R5 — `save_incident` y la clave de duplicados

- **Decisión**: `SqliteIncidentRepository.save_incident` persiste `incident.duplicate_group_key`; si el Incident llega sin clave (None), recae en el parámetro heredado (compatibilidad con tests de H002).
- **Racional**: la fuente de la clave es el dominio (`classify_incident_report`); evitar divergencia doble de sistema.
- **Alternativas**: ignorar el campo del dominio — rechazada (el Incident tiene `duplicate_group_key` desde H003a; persistirlo hace coherente el modelo).

### R6 — `recommended_team` en `Incident`

- **Decisión**: `Incident.recommended_team: Optional[RecommendedTeam] = None` — transiente (expuesto en la respuesta de creación); sin columna nueva en `incidents`.
- **Racional**: el contrato de salida del feature no incluye `recommended_team` como campo del Incident creado; el usuario no pidió columna nueva para él (solo `duplicate_group_key` + índice).

### R7 — `IncidentNotFoundError`

- **Decisión**: define-se `IncidentNotFoundError` en `src/application/services.py`; el adaptante HTTP lo mapea a 404 y el CLI a exit 2.
- **Racional**: error de aplicación (negocio), no de transporte; adaptantes solo traducen (paridad REST/CLI).

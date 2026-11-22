# Feature Specification: Guardar incidentes y consultar SLA

**Feature Branch**: `003-save-incidents-sla`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Necesitamos guardar los incidentes cuando llegan, avisar si ya había otro equivalente abierto, y consultar cómo va su SLA tanto por API como desde nuestra herramienta CLI."

**Alcance**: Este feature incluye almacenar los incidentes al llegar, indicar duplicado en incidentes equivalentes abiertos y consultar el SLA de los incidentes almacenados por interfaz HTTP y por la herramienta CLI. Queda fuera de alcance: la fusión o eliminación de incidentes equivalentes, la modificación de los estados almacenados por esta funcionalidad y el control de acceso.

## Clarifications

### Session 2026-11-22

- Q: ¿Cómo debería definirse "equivalente" entre dos incidentes para el aviso? → A: coincidencia exacta por `duplicate_group_key` únicamente en incidentes con estado abierto (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`), excluyendo `RESOLVED` y el propio `incident_id` recién creado.
- Q: ¿Cómo se integra el aviso de duplicados en la respuesta de creación? → A: integrado directamente en la respuesta de creación (`201 Created` en `POST /api/v1/incidents` y JSON en CLI `create`) mediante los campos `is_duplicate` (bool) y `duplicate_of` (`list[str]` con los `incident_id` equivalentes abiertos, excluyendo `RESOLVED` y el propio ID recién creado).
- Q: ¿Debería "incumplido" reflejar la violación de SLA en incidentes ya resueltos? → A: Sí; "incumplido" refleja la violación del límite independientemente del estado almacenado (incluidos `RESOLVED`), mientras "requiere_escalamiento" solo es verdadero para incidentes sin resolver (consistente con ADR-002).
- Q: ¿Debería incluirse en el resultado de la consulta de SLA "elapsed_minutes", "allowed_minutes", "remaining_minutes", "is_breached" y "requires_escalation" (junto con "incident_id" y "severity")? → A: Sí; el resultado incluye esos campos: incident_id y severity del incidente almacenado; elapsed_minutes, allowed_minutes y remaining_minutes según la política vigente; is_breached según la violación del límite (a cualquier estado almacenado); requires_escalation según la regla vigente.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Almacenar los incidentes al llegar (Priority: P1)

Como responsable del sistema de incidentes, necesito que cada incidente que llega se almacene, para que no se pierda información y se pueda consultar a posteriori.

**Why this priority**: El almacenamiento es la base de la funcionalidad: sin él, ni la detección de equivalentes abiertos ni la consulta de SLA pueden operar sobre datos reales.

**Independent Test**: Con un incidente enviado al sistema, se verifica que se almacena: se consulta el registro almacenado y se obtiene su identificador, título, severidad, estado e instante de creación.

**Acceptance Scenarios**:

1. **Given** que no hay incidentes almacenados, **When** llega un incidente con identificador, título, severidad y estado, **Then** el sistema MUST almacenar un registro con esos datos.
2. **Given** que ya hay incidentes almacenados, **When** llega un nuevo incidente diferente, **Then** el sistema MUST almacenar un nuevo registro del incidente nuevo.

---

### User Story 2 - Detección de incidentes equivalentes abiertos al crear un incidente nuevo (Priority: P1)

Como responsable del sistema de incidentes, necesito que el sistema detecte si, al llegar un incidente nuevo, ya existe otro incidente equivalente abierto, para evitar atender dos veces lo mismo.

**Why this priority**: La detección de duplicados evita trabajo duplicado y mantiene a los responsables enfocados en lo pendiente real.

**Independent Test**: Con un incidente abierto registrado, se verifica que al crear un incidente nuevo equivalente, la respuesta de creación MUST incluir is_duplicate=true y duplicate_of con el ID del incidente equivalente abierto.

**Acceptance Scenarios**:

1. **Given** que hay un incidente abierto equivalente al incidente nuevo, **When** se crea el incidente nuevo, **Then** la respuesta de creación incluye is_duplicate verdadero y duplicate_of con el incident_id del incidente equivalente abierto existente.
2. **Given** que hay incidentes abiertos que no son equivalentes al incidente nuevo, **When** se crea el incidente nuevo, **Then** la respuesta de creación incluye is_duplicate falso y duplicate_of vacío.
3. **Given** que el incidente equivalente no está en estado abierto (está resuelta o cerrada), **When** se crea un incidente equivalente, **Then** la respuesta de creación incluye is_duplicate falso y duplicate_of vacío; el incidente nuevo se almacena.

---

### User Story 3 - Consultar cómo va el SLA por interfaz HTTP y herramienta CLI (Priority: P1)

Como responsable del sistema de incidentes, necesito consultar el estado del SLA de un incidente almacenado tanto por la interfaz HTTP como por la herramienta CLI, para saber si está dentro del límite, si está incumplido, si requiere escalamiento y cuánto tiempo lleva transcurrido desde su creación.

**Why this priority**: La consulta de SLA brinda visibilidad operativa inmediata sobre los incidentes almacenados; sin ella, la información no puede usarse para priorización.

**Independent Test**: Con incidentes almacenados, se consulta el SLA de uno por la interfaz HTTP y por la herramienta CLI: ambas interfaces MUST devolver la misma información del SLA del mismo incidente.

**Acceptance Scenarios**:

1. **Given** que hay incidentes almacenados, **When** se consulta el SLA de un incidente por la interfaz HTTP, **Then** responde exitosamente con el estado del SLA: incident_id, severity, elapsed_minutes, allowed_minutes, remaining_minutes, is_breached y requires_escalation.
2. **Given** que hay incidentes almacenados, **When** se consulta el SLA del mismo incidente por la herramienta CLI, **Then** devuelve el mismo estado del SLA que la interfaz HTTP.

### Edge Cases

- La creación de un incidente nuevo equivalente a un incidente abierto: la respuesta de creación incluye is_duplicate=true y duplicate_of con el incident_id del incidente equivalente abierto.
- El incidente equivalente abierto tiene estado `RESOLVED`: la respuesta de creación incluye is_duplicate falso y duplicate_of vacío; el incidente nuevo se almacena.
- Incidentes sin clave de duplicados (ausente o vacía): no se produce indicación de duplicado; la equivalencia requiere clave de duplicados no vacía en ambos incidentes.
- Varios incidentes equivalentes abiertos: la indicación de duplicado identifica al equivalente abierto existente detectado; el resto de equivalentes queda accesible por el mismo `duplicate_group_key`.
- Incidentes con títulos idénticos pero distintos `duplicate_group_key`: no son equivalentes; la equivalencia es la coincidencia exacta de la clave de duplicados.
- Consulta de SLA de un incidente que no está almacenado: MUST NOT devolver un estado de SLA inventado; indica que el incidente no existe.
- Incidente almacenado sin incumplido: MUST devolver `is_breached = false` y `remaining_minutes >= 0`.

## Requirements *(mandatory)*

### Functional Requirements

**Almacenamiento al llegar**

- **FR-001**: El sistema MUST almacenar un registro por cada incidente que llega, conservando su identificador, título, severidad, estado e instante de creación.
- **FR-002**: La llegada del incidente MUST ser registrada en el sistema en el mismo flujo en que el incidente se recibe (los canales de ingesta existentes).

**Detección de incidentes equivalentes abiertos**

- **FR-003**: Al llegar un incidente nuevo, el sistema MUST identificar si existe algún incidente equivalente abierto: otro incidente almacenado con el mismo `duplicate_group_key` en un estado abierto (`OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`), excluyendo el incidente nuevo mismo y los estados `RESOLVED`.
- **FR-004**: Cuando se detecta un equivalente abierto al crear un incidente nuevo, el sistema MUST integrar la indicación de duplicado en la respuesta de creación del incidente nuevo mediante is_duplicate=true y duplicate_of con el incident_id del incidente equivalente abierto existente.
- **FR-005**: Si no hay incidente equivalente abierto, el sistema MUST almacenar el nuevo incidente sin producir indicación de duplicado.

**Consulta de SLA**

- **FR-006**: El sistema MUST permitir consultar, para cualquier incidente almacenado, el estado del SLA según el contrato de [Contrato de salida](#contrato-de-salida): `incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached` y `requires_escalation`.
- **FR-007**: La información del SLA MUST calcularse conforme a la política vigente de SLA para la severidad del incidente (según la funcionalidad anterior).
- **FR-008**: El resultado de la consulta de SLA MUST incluir `incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached` y `requires_escalation` según la política vigente: `is_breached` MUST ser verdadero solo cuando el tiempo transcurrido supera `allowed_minutes` (a cualquier estado almacenado), y `requires_escalation` MUST ser verdadero según la regla vigente de la funcionalidad anterior.

**Paridad entre interfaces**

- **FR-009**: La consulta de SLA por la interfaz HTTP y la consulta por la herramienta CLI MUST entregar la misma información para el mismo incidente.
- **FR-010**: Si la consulta no puede completarse, la interfaz MUST informar un error comprensible y MUST NOT presentar información del SLA parcial como si estuviera completa.

### Key Entities *(include if feature involves data)*

- **Registro del incidente**: el dato almacenado por esta funcionalidad. Atributos: identificador, título, severidad, estado e instante de creación.
- **Información de duplicados en la creación**: la respuesta de creación de un incidente nuevo equivalente a uno abierto. Contiene is_duplicate (bool) y duplicate_of (list[str] con los incident_id de incidentes equivalentes abiertos, sin RESOLVED ni el propio ID del incidente nuevo).
- **Estado del SLA de un incidente**: los factos del SLA de un incidente almacenado: incident_id, severity, elapsed_minutes, allowed_minutes, remaining_minutes, is_breached y requires_escalation, conforme a la política vigente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los incidentes recibidos se almacenan conservando su identificador, título, severidad, estado e instante de creación.
- **SC-002**: Al crear un incidente nuevo equivalente a un incidente abierto, la respuesta de creación incluye is_duplicate=true y duplicate_of con el incident_id del incidente equivalente abierto en el 100 % de los casos de aceptación.
- **SC-003**: Cuando no hay incidente abierto equivalente, el sistema no produce ninguna indicación de duplicado en el 0 % de los casos de aceptación.
- **SC-004**: La consulta de SLA refleja: `incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached` y `requires_escalation` coherentes con la política vigente para la severidad del incidente; `is_breached = false` y `remaining_minutes >= 0` para un incidente almacenado sin incumplido; el resultado es coherente con la política vigente en el 100 % de las consultas de aceptación.
- **SC-005**: Para el mismo incidente, la consulta de SLA por la interfaz HTTP y la consulta por la herramienta CLI devuelven el mismo estado del SLA en el 100 % de los casos de aceptación comparados.
- **SC-006**: La consulta de SLA de un incidente no almacenado devuelve indicación de que el incidente no existe, sin devolver un estado de SLA inventado.

## Assumptions

- **Definición de equivalencia**: dos incidentes son equivalentes cuando coinciden exactamente en `duplicate_group_key` (clave de duplicados del sistema). La indicación de duplicado MUST producirse cuando el incidente nuevo, recién creado, tiene una clave de duplicados no vacía y existe otro incidente almacenado con la misma clave en un estado abierto (`OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`); el propio incidente nuevo se excluye de la búsqueda y los incidentes en estado `RESOLVED` no producen indicación de duplicado.
- **Llegada del incidente**: se define como el momento en que el incidente se recibe y se almacena en el sistema (vía los canales de ingesta existentes).
- **La indicación de duplicados se integra en la respuesta de creación del incidente nuevo**: al detectar un incidente equivalente abierto al crear un incidente nuevo, la respuesta de creación (201 Created en POST /api/v1/incidents y JSON en CLI create) MUST incluir is_duplicate (bool) y duplicate_of (list[str] con los incident_id de incidentes equivalentes abiertos, sin RESOLVED ni el propio ID del incidente nuevo).
- **Consistencia con la política vigente**: "incumplido" y "requiere escalamiento" MUST reflejar la política vigente de SLA para la severidad del incidente según ADR-002 (igual que la funcionalidad anterior).
- **Cálculo en el instante de consulta**: el estado del SLA MUST reflejar el instante en que se realiza la consulta.
- **Alcance**: incluye almacenar los incidentes al llegar, indicar duplicado en incidentes equivalentes abiertos y consultar el SLA por interfaz HTTP y herramienta CLI. Excluye la fusión o eliminación de incidentes equivalentes, la modificación de los estados almacenados por esta funcionalidad y el control de acceso.

## Contrato de salida

### Contrato de Creación (`POST /api/v1/incidents` y CLI `create`)

| Campo | Regla |
| --- | --- |
| `title` | **Obligatorio**. Cadena no vacía ni de solo espacios. Vacío o solo espacios → 422 (API) / código de salida 1 (CLI). |
| `raw_text` | **Obligatorio**. Cadena no vacía ni de solo espacios, con el texto del reporte original. Vacío o solo espacios → 422 (API) / código de salida 1 (CLI). |
| `incident_id` | Opcional. Autogenerado (`INC-<HEX8>`) si se omite. |
| `created_at` | Opcional. Instante actual si se omite. |
| `status` | Opcional. Default `"OPEN"`. |

Respuesta exitosa: `201 Created` (API) o JSON (CLI) que incluye la clasificación completa (`severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`), `is_duplicate` (bool) y `duplicate_of` (list[str] con los `incident_id` de incidentes equivalentes abiertos; [] si no hay equivalentes).

### Contrato de Auditoría de SLA (`GET /api/v1/incidents/{incident_id}/sla` y CLI `sla`)

- Parámetro opcional `reference_time` (ISO 8601) para evaluaciones deterministicas.
- Respuesta `404 Not Found` si no existe el incidente, y `422 Unprocessable Entity` si `reference_time < created_at` (CLI: código de salida 1).
- Respuesta exitosa: el estado del SLA según el contrato [Estado del SLA de un incidente](#estado-del-sla-de-un-incidente).

### Estado del SLA de un incidente

| Campo | Regla |
| --- | --- |
| `incident_id` | Identificador del incidente almacenado. |
| `severity` | Severidad registrada del incidente. |
| `elapsed_minutes` | Minutos transcurridos del SLA, según la política vigente para la severidad: tiempo continuo para P0/P1 y horario hábil (Lunes a Viernes, 08:00–18:00) para P2/P3, de acuerdo con ADR-002. |
| `allowed_minutes` | Límite de minutos de SLA de la severidad (de acuerdo con ADR-002). |
| `remaining_minutes` | Diferencia entre el límite de SLA y los minutos transcurridos según la política vigente; puede ser negativo si el SLA está vencido. |
| `is_breached` | Verdadero solo si `elapsed_minutes` supera `allowed_minutes`; reflejado a cualquier estado almacenado (incluidos `RESOLVED`). |
| `requires_escalation` | Verdadero si el incidente, sin estar resuelto, alcanza o supera el 75 % de `allowed_minutes` (regla vigente de la funcionalidad anterior). |

## Escenarios BDD de aceptación

```gherkin
Feature: Almacenamiento de incidentes y consulta de SLA

Scenario: Registro inicial sin duplicados previos
  Given que no hay incidentes almacenados
  When se crea un incidente con title, raw_text y status "OPEN"
  Then responde 201
  And la respuesta de creación incluye la clasificación completa (severity, component, recommended_team, duplicate_group_key, rationale)
  And is_duplicate es false
  And duplicate_of es []

Scenario: Detección de duplicado abierto en la creación
  Given que hay un incidente abierto equivalente registrado
  And que existe un incidente equivalente con status RESOLVED
  When se crea un incidente nuevo equivalente
  Then responde 201
  And la respuesta de creación incluye is_duplicate true
  And duplicate_of incluye el incident_id del incidente equivalente abierto
  And duplicate_of no incluye incidentes RESOLVED

Scenario: Auditoría deterministica de SLA en horario hábil
  Given un incidente registrado con severity P2 creado viernes 2026-11-06T17:00:00
  When se consulta su SLA con reference_time lunes 2026-11-09T09:00:00
  Then responde 200
  And elapsed_minutes es 120
  And allowed_minutes es 480
  And remaining_minutes es 360
  And is_breached es false
  And requires_escalation es false

Scenario: Consulta de SLA para ID inexistente y tiempo anterior a creación
  Given que no existe un incidente con ID "INC-NONE"
  When se consulta el SLA del incidente "INC-NONE"
  Then responde 404
  And dado que existe un incidente creado 2026-11-09T10:00:00
  And cuando se consulta su SLA con reference_time 2026-11-09T09:00:00
  Then responde 422

Scenario: Operación equivalente mediante los comandos CLI create y sla
  When se ejecuta el comando CLI create (title, raw_text, status)
  Then responde JSON con la clasificación completa (severity, component, recommended_team, duplicate_group_key, rationale), is_duplicate y duplicate_of
  And el CLI sla del incidente entrega el mismo estado del SLA (incident_id, severity, elapsed_minutes, allowed_minutes, remaining_minutes, is_breached, requires_escalation) que la interfaz HTTP para el mismo instante
```

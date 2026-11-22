# Feature Specification: Resumen de Incidentes Activos

**Feature Branch**: `002-active-incident-summary`

**Created**: 2026-11-22

**Status**: Aceptada

**Input**: User description: "Necesitamos consultar el resumen de incidentes actualmente activos (OPEN e IN_PROGRESS) tanto por API HTTP como por CLI, indicando el total activo, cuántos incumplieron su SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), permitiendo filtrar opcionalmente por componente y fijar el instante de referencia para evaluaciones deterministas."

## Clarifications

### Session 2026-11-22

- Q: ¿Qué deben representar los «minutos transcurridos» del detalle: el tiempo efectivo de SLA o el tiempo de reloj desde la creación? → A: Tiempo efectivo de SLA (continuo para P0/P1 y hábil para P2/P3, coherente con ADR-002).
- Q: ¿Qué estados cuentan como activos? → A: `OPEN` e `IN_PROGRESS`. `ESCALATION_REQUIRED` no es un estado almacenado en esta funcionalidad: el escalamiento se representa con el booleano calculado `requires_escalation`. `RESOLVED` y cualquier otro estado quedan excluidos.
- Q: ¿Cómo se fija el instante de evaluación? → A: `reference_time` opcional en ISO-8601 sin zona horaria; si se omite, se usa el instante actual. Una fecha inválida produce `INVALID_REFERENCE_TIME` (HTTP 422, CLI 2); un instante anterior a la creación de un incidente activo del conjunto produce `REFERENCE_TIME_BEFORE_CREATION` (HTTP 400, CLI 2).
- Q: ¿Qué ocurre si no hay incidentes activos o ninguno coincide con el filtro? → A: La consulta es exitosa con HTTP 200, `total_active = 0`, `breached_count = 0` e `incidents = []`; el CLI termina con código 0 y el mismo JSON.
- Q: ¿Se expone el límite de minutos por incidente? → A: No. El detalle no incluye `allowed_minutes`; el límite se deriva de la severidad según ADR-002.
- Q: ¿Cómo se normaliza el filtro por componente? → A: Se recortan los espacios y se compara sin distinguir mayúsculas/minúsculas. El campo `component` de la respuesta es el filtro normalizado en minúsculas, o `null` si no hay filtro.
- Q: ¿Qué pasa con el criterio de rendimiento de 10 000 incidentes? → A: Se retira de los criterios de aceptación de H002. La deuda de escaneo completo y N+1 del repositorio es intencional y se aborda en su fase propia.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar el estado operativo por HTTP (Priority: P1)

Un responsable de soporte necesita ver, en una sola consulta, cuántos incidentes
están activos, cuántos ya incumplieron su SLA y el detalle de cada uno, para
priorizar el trabajo del turno sin revisar registros uno por uno.

**Why this priority**: es el valor central del hito: visibilidad inmediata del
estado operativo. Sin esta historia no hay resumen que compartir con el equipo.

**Independent Test**: con un conjunto conocido de incidentes activos y resueltos,
se consulta el resumen desde la interfaz HTTP y se verifica el total, el recuento
de incumplimientos y el detalle. No requiere la interfaz de terminal ni el filtro.

**Acceptance Scenarios**: los escenarios normativos son los cuatro de la sección
[Escenarios BDD de aceptación](#escenarios-bdd-de-aceptación).

---

### User Story 2 - Obtener el mismo resumen desde la terminal (Priority: P2)

Un ingeniero de guardia prefiere trabajar desde la terminal y necesita la misma
información que la interfaz HTTP, con los mismos valores, para diagnosticar sin
cambiar de herramienta.

**Why this priority**: la paridad entre interfaces es un requisito permanente del
producto; sin ella, el mismo incidente se describiría distinto según la puerta de
entrada.

**Independent Test**: con el mismo conjunto de datos de la historia 1, se ejecuta
la consulta desde la terminal y se comparan totales, recuento de incumplimientos
y detalle con la respuesta HTTP.

**Acceptance Scenarios**: el escenario 4 de la sección
[Escenarios BDD de aceptación](#escenarios-bdd-de-aceptación) verifica la paridad.

---

### User Story 3 - Acotar el resumen a un componente (Priority: P3)

Una persona responsable de un servicio quiere ver solo los incidentes activos de
su componente para concentrarse en lo que puede resolver.

**Why this priority**: mejora la utilidad operativa, pero el resumen completo ya
entrega valor sin el filtro.

**Independent Test**: con incidentes activos en dos componentes distintos, se
consulta con el filtro de uno de ellos y se verifica que el detalle y ambos
totales correspondan solo a ese componente.

**Acceptance Scenarios**: el escenario 2 de la sección
[Escenarios BDD de aceptación](#escenarios-bdd-de-aceptación) verifica el filtro.

---

### Edge Cases

- No hay incidentes activos: el resumen es válido con ceros y detalle vacío.
- Todos los incidentes activos están incumplidos: el recuento de incumplimientos
  iguala el total activo y cada entrada lo refleja.
- Un incidente está exactamente en el límite de su SLA: no se cuenta como
  incumplido; uno exactamente en el umbral de escalamiento sí requiere
  escalamiento.
- El filtro corresponde a un componente que existe pero no tiene incidentes
  activos: el resultado es un resumen vacío, no un error.
- El filtro tiene un valor en blanco: se comporta como ausencia de filtro.
- Un incidente P2 o P3 abierto durante el fin de semana muestra minutos efectivos
  de SLA (cero si no transcurrió tiempo hábil), no el tiempo de reloj.
- El conjunto mezcla estados activos e inactivos: los inactivos nunca aparecen en
  el detalle ni en los totales.
- Un incidente activo tiene una fecha de creación posterior al instante de
  consulta: la consulta responde `REFERENCE_TIME_BEFORE_CREATION` y no devuelve
  valores inventados ni un resumen parcial.
- `reference_time` no es una fecha ISO-8601 válida, incluye `Z` o un offset de
  zona: la consulta responde `INVALID_REFERENCE_TIME`.
- El volumen de incidentes activos es alto: el resumen sigue siendo una sola
  consulta de lectura, sin pasos manuales de exportación.
- Dos componentes difieren solo en mayúsculas o espacios: se tratan como el mismo
  componente para el filtro.

## Requirements *(mandatory)*

### Functional Requirements

**Alcance de los datos**

- **FR-001**: El sistema MUST incluir en el resumen únicamente incidentes cuyo estado sea `OPEN` o `IN_PROGRESS`, y MUST excluir `RESOLVED` y cualquier otro estado. `ESCALATION_REQUIRED` no se almacena como estado en esta funcionalidad; el escalamiento se expone como el booleano `requires_escalation`.
- **FR-002**: El sistema MUST tratar `OPEN` e `IN_PROGRESS` como "activo" sin distinción para los totales, conservando el estado real de cada incidente en el detalle.
- **FR-003**: La consulta MUST ser de solo lectura: no crea, modifica ni elimina incidentes.

**Métricas del resumen**

- **FR-004**: El sistema MUST informar el total de incidentes activos del conjunto consultado.
- **FR-005**: El sistema MUST informar cuántos de esos incidentes activos tienen su SLA incumplido en el instante de la consulta, según la política de SLA vigente.
- **FR-006**: El total activo MUST ser igual al número de entradas del detalle, y el recuento de incumplimientos MUST ser igual al número de entradas con `is_breached = true`.
- **FR-007**: Un incidente MUST contarse como incumplido solo cuando su tiempo transcurrido supera el límite de su severidad; estar exactamente en el límite no cuenta como incumplimiento.

**Detalle por incidente**

- **FR-008**: El detalle MUST incluir una entrada por cada incidente activo con: identificador del incidente, título, componente, severidad, estado, minutos transcurridos, si está incumplido y si requiere escalamiento.
- **FR-009**: Los minutos transcurridos mostrados MUST ser los minutos efectivos de SLA: se miden desde la creación del incidente hasta el instante de la consulta aplicando la política de su severidad (tiempo continuo para P0/P1 y tiempo hábil de lunes a viernes, 08:00–18:00, para P2/P3). MUST NOT ser negativos ni sustituirse por tiempo de reloj.
- **FR-010**: "Requiere escalamiento" MUST ser verdadero cuando el incidente, sin resolverse, alcanza o supera el 75 % de su tiempo límite, incluidos los ya incumplidos.
- **FR-011**: El detalle MUST limitarse a los campos acordados; MUST NOT incluir `allowed_minutes`, el texto libre del reporte original, datos de contacto ni otros datos personales.
- **FR-012**: El detalle MUST presentarse en un orden estable: primero la severidad más crítica (`P0`, `P1`, `P2`, `P3`) y, a igual severidad, el incidente más antiguo primero; a igual antigüedad, el identificador ascendente.

**Filtro por componente**

- **FR-013**: El sistema MUST permitir un filtro opcional por componente.
- **FR-014**: Cuando se indique un filtro, MUST aplicarse tanto al detalle como a los dos totales, de modo que el resumen describa solo ese subconjunto.
- **FR-015**: El filtro MUST compararse con el identificador del componente ignorando mayúsculas, minúsculas y espacios alrededor; un filtro vacío o ausente MUST equivaler a no filtrar. El campo `component` de la respuesta MUST ser el filtro normalizado en minúsculas o `null`.
- **FR-016**: Un filtro sin coincidencias MUST producir un resumen exitoso con total cero, cero incumplimientos y detalle vacío.

**Instante de referencia**

- **FR-017**: El sistema MUST aceptar un `reference_time` opcional en ISO-8601 sin zona horaria. Si se omite o está en blanco, MUST usar el instante actual del servidor.
- **FR-018**: Con la misma información, el mismo filtro y el mismo `reference_time`, el resumen MUST ser idéntico entre ejecuciones e interfaces.
- **FR-019**: Una fecha inválida, imposible o con zona horaria (`Z` u offset) MUST rechazarse con `INVALID_REFERENCE_TIME`: HTTP 422 y CLI código 2.
- **FR-020**: Si `reference_time` es anterior a la creación de algún incidente activo que entra en el resumen, la consulta MUST fallar con `REFERENCE_TIME_BEFORE_CREATION`: HTTP 400 y CLI código 2. MUST NOT devolver un resumen parcial.
- **FR-021**: La respuesta MUST ecoar el instante resuelto en `reference_time`, en ISO-8601 sin zona horaria.

**Interfaces y paridad**

- **FR-022**: El resumen MUST estar disponible por `GET /api/v1/incidents/summary` y por el subcomando `summary` del CLI.
- **FR-023**: Ambas interfaces MUST compartir el mismo significado para el total activo, el recuento de incumplimientos y cada campo del detalle; para la misma información, el mismo filtro y el mismo instante, MUST devolver el mismo objeto JSON.
- **FR-024**: Si la consulta no puede completarse, la interfaz MUST informar un error comprensible y MUST NOT presentar un resumen parcial como si estuviera completo.

### Key Entities *(include if feature involves data)*

- **Incidente activo**: incidente registrado cuyo estado es `OPEN` o `IN_PROGRESS`. Atributos relevantes: identificador, título, componente, severidad, estado, instante de creación y evaluación de SLA en el instante de la consulta.
- **Resumen de incidentes activos**: resultado de una consulta. Contiene el instante de referencia resuelto, el filtro aplicado (normalizado o `null`), el total activo, el recuento de incumplimientos y la lista ordenada de incidentes activos.
- **Evaluación de SLA**: para cada incidente activo, minutos transcurridos (efectivos de SLA), si está incumplido y si requiere escalamiento. El límite aplicable se deriva de la severidad según ADR-002 y no se expone en el detalle.
- **Filtro de componente**: identificador opcional de componente que acota el resumen; su ausencia o valor vacío significa "todos los componentes".

## Contrato de interfaces y salida

### HTTP

- Método y ruta: `GET /api/v1/incidents/summary`.
- Parámetros de consulta, ambos opcionales:

| Parámetro | Tipo | Regla |
| --- | --- | --- |
| `component` | string | Filtro exacto por identificador, ignorando mayúsculas/minúsculas y espacios alrededor. Vacío o ausente significa "todos". |
| `reference_time` | string | Fecha y hora ISO-8601 sin zona horaria. Vacío o ausente significa "ahora". |

- La consulta es de solo lectura y no acepta cuerpo.
- Respuesta exitosa: `200 OK` con el objeto de la sección [JSON de salida](#json-de-salida).
- Sin paginación en esta versión.

### CLI

```text
summary [--component <componente>] [--reference-time <ISO-8601>]
```

- La salida por defecto es un objeto JSON idéntico al cuerpo HTTP.
- Código de salida `0` en éxito, incluido el resumen vacío.
- Código de salida `2` para errores de validación (`INVALID_REFERENCE_TIME`, `REFERENCE_TIME_BEFORE_CREATION`), con el sobre de error en `stderr`.
- Código de salida `1` para fallos inesperados, con `INTERNAL_ERROR` en `stderr`.
- `--human` queda fuera del alcance de esta versión.

### JSON de salida

Ejemplo con `reference_time=2026-11-20T12:00:00` y `component=Payments-Gateway`:

```json
{
  "reference_time": "2026-11-20T12:00:00",
  "component": "payments-gateway",
  "total_active": 2,
  "breached_count": 1,
  "incidents": [
    {
      "incident_id": "INC-3101",
      "title": "La pasarela de pagos devuelve 502 al cobrar",
      "component": "payments-gateway",
      "severity": "P0",
      "status": "OPEN",
      "elapsed_minutes": 90,
      "is_breached": true,
      "requires_escalation": true
    },
    {
      "incident_id": "INC-3102",
      "title": "Confirmación de pagos lenta",
      "component": "payments-gateway",
      "severity": "P2",
      "status": "IN_PROGRESS",
      "elapsed_minutes": 120,
      "is_breached": false,
      "requires_escalation": false
    }
  ]
}
```

| Campo | Tipo | Regla |
| --- | --- | --- |
| `reference_time` | string | Instante resuelto, ISO-8601 sin zona horaria. |
| `component` | string \| null | Filtro normalizado en minúsculas, o `null` si no hay filtro. |
| `total_active` | integer | Número de entradas de `incidents`. |
| `breached_count` | integer | Número de entradas con `is_breached = true`; nunca mayor que `total_active`. |
| `incidents` | array | Lista ordenada; puede ser `[]`. |

Campos de cada entrada de `incidents`:

| Campo | Tipo | Regla |
| --- | --- | --- |
| `incident_id` | string | Identificador del incidente. |
| `title` | string | Título completo; nunca el texto crudo del reporte. |
| `component` | string | Componente almacenado del incidente. |
| `severity` | `P0` \| `P1` \| `P2` \| `P3` | Severidad registrada. |
| `status` | `OPEN` \| `IN_PROGRESS` | Estado real del incidente activo. |
| `elapsed_minutes` | integer ≥ 0 | Minutos efectivos de SLA. |
| `is_breached` | boolean | Verdadero solo si `elapsed_minutes` supera el límite de la severidad. |
| `requires_escalation` | boolean | Verdadero si `elapsed_minutes` alcanza o supera el 75 % del límite. |

### Respuesta vacía

```json
{
  "reference_time": "2026-11-20T12:00:00",
  "component": null,
  "total_active": 0,
  "breached_count": 0,
  "incidents": []
}
```

### Errores

| Situación | HTTP | `error.code` | CLI |
| --- | --- | --- | --- |
| `reference_time` inválido, imposible o con zona horaria | 422 | `INVALID_REFERENCE_TIME` | código 2, sobre en `stderr` |
| `reference_time` anterior a la creación de un incidente activo del conjunto | 400 | `REFERENCE_TIME_BEFORE_CREATION` | código 2, sobre en `stderr` |
| Fallo inesperado | 500 | `INTERNAL_ERROR` | código 1, `stderr` |
| Sin activos o sin coincidencias | 200 | — | código 0, JSON en `stdout` |

Sobre de error, igual que H001:

```json
{
  "error": {
    "code": "INVALID_REFERENCE_TIME",
    "message": "reference_time debe ser una fecha ISO-8601 válida sin zona horaria."
  }
}
```

## Escenarios BDD de aceptación

```gherkin
Feature: Resumen de incidentes activos por HTTP y CLI

  Scenario: El resumen global excluye los incidentes resueltos
    Given los siguientes incidentes registrados:
      | incident_id | título                                      | componente       | severidad | estado      | creado_en           |
      | INC-3001    | La pasarela de pagos devuelve 502 al cobrar | payments-gateway | P0        | OPEN        | 2026-11-20T10:00:00 |
      | INC-3002    | Autenticación intermitente                  | auth-identity    | P1        | IN_PROGRESS | 2026-11-20T09:00:00 |
      | INC-3003    | Exportación de reportes lenta               | reporting-api    | P2        | RESOLVED    | 2026-11-20T08:00:00 |
      | INC-3004    | Conexiones agotadas en base de datos        | database-cluster | P0        | OPEN        | 2026-11-20T11:00:00 |
    And el instante de referencia es "2026-11-20T12:00:00"
    When se consulta el resumen de incidentes activos sin filtro por HTTP
    Then responde 200
    And total_active es 3
    And breached_count es 1
    And incidents contiene exactamente los incidentes "INC-3001", "INC-3004" e "INC-3002", en ese orden
    And la entrada "INC-3001" informa elapsed_minutes 120, is_breached true y requires_escalation true

  Scenario: El resumen se acota al componente solicitado
    Given los siguientes incidentes activos:
      | incident_id | título                                      | componente       | severidad | estado      | creado_en           |
      | INC-3101    | La pasarela de pagos devuelve 502 al cobrar | payments-gateway | P0        | OPEN        | 2026-11-20T10:30:00 |
      | INC-3102    | Confirmación de pagos lenta                 | payments-gateway | P2        | IN_PROGRESS | 2026-11-20T10:00:00 |
      | INC-3103    | Autenticación intermitente                  | auth-identity    | P1        | OPEN        | 2026-11-20T08:00:00 |
    And el instante de referencia es "2026-11-20T12:00:00"
    When se consulta el resumen por HTTP con componente "Payments-Gateway"
    Then responde 200
    And component es "payments-gateway"
    And total_active es 2
    And breached_count es 1
    And incidents contiene exactamente los incidentes "INC-3101" e "INC-3102", en ese orden
    And la entrada "INC-3101" informa elapsed_minutes 90, is_breached true y requires_escalation true
    And la entrada "INC-3102" informa elapsed_minutes 120, is_breached false y requires_escalation false

  Scenario Outline: El resumen vacío es una respuesta exitosa
    Given <situación>
    And el instante de referencia es "2026-11-20T12:00:00"
    When se consulta el resumen por HTTP <consulta>
    Then responde 200
    And total_active es 0
    And breached_count es 0
    And incidents es una lista vacía

    Examples:
      | situación                                                       | consulta                       |
      | un conjunto con incidentes resueltos y ningún incidente activo  | sin filtro por componente      |
      | incidentes activos únicamente en "payments-gateway"             | con componente "auth-identity" |

  Scenario: El CLI devuelve el mismo resumen que HTTP
    Given un conjunto de incidentes activos en "payments-gateway" y "auth-identity"
    And el instante de referencia es "2026-11-20T12:00:00"
    When se ejecuta el comando summary --component "payments-gateway" --reference-time "2026-11-20T12:00:00"
    Then el código de salida es 0
    And stdout es un objeto JSON válido
    And el objeto JSON es idéntico al cuerpo devuelto por GET /api/v1/incidents/summary con el mismo componente y el mismo instante de referencia
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un responsable de soporte obtiene total activo, incumplimientos de SLA y detalle completo en una sola consulta, sin exportar datos ni revisar registros individualmente.
- **SC-002**: En el 100 % de las consultas, el total activo coincide con el número de entradas del detalle y el recuento de incumplimientos coincide con las entradas marcadas como incumplidas.
- **SC-003**: Para la misma información, el mismo filtro y el mismo instante, la interfaz HTTP y la de terminal coinciden en el 100 % de los campos y valores.
- **SC-004**: El 0 % de los incidentes no activos aparece en el resumen, incluso cuando comparten componente con incidentes activos.
- **SC-005**: El resumen se obtiene en una sola operación de lectura, sin modificar datos ni requerir pasos manuales. El tiempo de respuesta con 10 000 registros se medirá en la fase de optimización del repositorio, no en la aceptación de H002.
- **SC-006**: El filtro por componente reduce el resultado al componente indicado en el 100 % de los casos, y un componente sin incidentes activos devuelve un resumen vacío sin error.
- **SC-007**: El 0 % de las consultas modifica el estado de los incidentes.
- **SC-008**: El 100 % de los `reference_time` inválidos se rechaza con `INVALID_REFERENCE_TIME`, y el 100 % de los instantes anteriores a la creación se rechaza con `REFERENCE_TIME_BEFORE_CREATION`, sin resumen parcial.

## Assumptions

- Los incidentes ya están registrados con identificador, título, componente,
  severidad, estado, instante de creación e instante de resolución; esta
  funcionalidad no crea ni actualiza incidentes.
- El instante de consulta es el `reference_time` recibido o, si se omite, el
  momento en que se atiende la solicitud. Las pruebas fijan ese instante para que
  los resultados sean reproducibles.
- Las marcas de tiempo son naive y se interpretan en una única zona horaria
  coherente con los datos almacenados; no hay conversión entre zonas en esta
  versión. Por eso `reference_time` rechaza `Z` y offsets.
- Los incidentes activos no tienen instante de resolución; si lo tuvieran, sería
  una inconsistencia de datos fuera del alcance de esta funcionalidad.
- "Minutos transcurridos" son los minutos efectivos de SLA, según la decisión
  confirmada en la sesión de clarificación: tiempo continuo para P0/P1 y tiempo
  hábil (lunes a viernes, 08:00–18:00) para P2/P3. No se muestra un segundo campo
  de tiempo de reloj en esta versión.
- Los umbrales de ADR-002 se mantienen: incumplimiento cuando se supera el límite
  y escalamiento desde el 75 % mientras el incidente no esté resuelto.
- El filtro por componente es exacto en cuanto a identificador, pero tolera
  diferencias de mayúsculas y espacios; no es una búsqueda parcial ni por texto.
- Los totales describen el conjunto filtrado, no el universo completo: si se
  filtra, el total activo y los incumplimientos corresponden a ese componente.
- Esta versión devuelve todos los incidentes activos que coinciden, sin
  paginación; el volumen esperado es de hasta 10 000 incidentes registrados.
- El detalle no incluye `allowed_minutes`; el límite se deriva de la severidad
  según ADR-002.
- Ambas interfaces comparten los mismos campos y significados; el contrato
  público se documenta en la sección [Contrato de interfaces y salida](#contrato-de-interfaces-y-salida).
- Autenticación, autorización y control de acceso quedan fuera del alcance de
  esta funcionalidad, igual que en el hito anterior.
- La deuda de rendimiento del repositorio (escaneo completo y N+1) es intencional
  y se aborda en su fase propia; no es un criterio de aceptación de H002.

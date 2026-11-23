# Feature Specification: Servicio en contenedores con base de datos relacional dedicada y chequeo de salud de conectividad

**Feature Branch**: `004-postgres-container-runtime`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Necesitamos preparar el servicio para ejecutarse en contenedores junto con una base de datos relacional dedicada en producción y exponer un chequeo real de salud de conectividad."

**Alcance**: Este feature incluye preparar la ejecución del servicio desplegada en contenedores junto con una base de datos relacional dedicada, y exponer un chequeo de salud de conectividad real. Queda fuera de alcance: la migración de datos desde SQLite embebido, la alta disponibilidad y orquestación compleja (Kubernetes u otros orquestadores), herramientas de monitoreo avanzadas y métricas por nivel, e implementaciones detalladas del motor de base de datos o de la topología de contenedores (ADR-004).

## Clarifications

### Session 2026-11-22

- Q: ¿Cómo debe exponerse el chequeo de salud: como endpoint HTTP en el contenedor de servicio, como comando CLI, o ambos? → A: Ambos: endpoint HTTP + comando CLI con el mismo contrato de respuesta.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ejecución del servicio en contenedores (Priority: P1)

Como responsable del servicio de incidentes en producción, necesito que el servicio se ejecute en contenedores junto con una base de datos relacional dedicada, para que el entorno del servicio sea reproducible y aislado de la máquina anfitriona.

**Why this priority**: La ejecución en contenedores es la base de la operabilidad del servicio: sin ella, la base de datos relacional dedicada no se ejecuta como entorno propio, con los trade-offs que eso implica.

**Independent Test**: Con el despliegue activo, se verifica que el servicio y la base de datos relacional dedicada se ejecutan como contenedores (permanecen corriendo e instancias aisladas), y que la API responde con una petición de verificación.

**Acceptance Scenarios**:

1. **Given** que el despliegue en contenedores está activo, **When** se consulta el estado de ejecución, **Then** el servicio MUST responder desde su contenedor y la base de datos relacional dedicada MUST responder desde su contenedor correspondiente.
2. **Given** que el despliegue se levanta desde cero, **When** se ejecuta el servicio desplegado, **Then** la API MUST estar accesible mediante el runtime del contenedor de servicio, con la base de datos dedicada disponible mediante su contenedor.

---

### User Story 2 - Chequeo real de salud de conectividad (Priority: P1)

Como responsable del servicio, necesito exponer un chequeo de salud que verifique conectividad real con la base de datos, para saber operativamente si el servicio está accesible y si su persistencia está disponible.

**Why this priority**: Sin un chequeo de salud real, los operadores no pueden distinguir entre un servicio en marcha y uno con su base de datos caída; un chequeo de proceso vivo insuficiente no detecta la pérdida de conectividad.

**Independent Test**: Con el servicio desplegado, se consulta el chequeo de salud; se verifica que indica salud OK solo cuando la base de datos está accesible y que indica error cuando no.

**Acceptance Scenarios**:

1. **Given** que el servicio y la base de datos están accesibles, **When** se consulta el chequeo de salud, **Then** el chequeo MUST indicar salud OK con conectividad verificada con la base de datos relacional dedicada.
2. **Given** que la base de datos no está accesible, **When** se consulta el chequeo de salud, **Then** el chequeo MUST indicar un estado de salud de fallo con la base de datos marcada como no disponible.
3. **Given** que el servicio en contenedores está arrancando y la base de datos no responde aún, **When** se consulta el chequeo de salud, **Then** el chequeo MUST indicar el estado de salud de fallo.

### Edge Cases

- La base de datos relacional dedicada está fuera de servicio: el chequeo de salud MUST indicar fallo y no salud OK.
- El contenedor de servicio arranca antes de que la base de datos responda: el chequeo de salud MUST indicar fallo hasta que la base de datos esté accesible.
- Reinicio del contenedor de la base de datos: el chequeo de salud debe volver a indicar salud OK cuando la base vuelve a estar accesible.

## Requirements *(mandatory)*

### Functional Requirements

**Ejecución del servicio en contenedores**

- **FR-001**: El sistema MUST ejecutarse desplegada en contenedores: el servicio y la base de datos relacional dedicada se ejecutan como contenedores desplegados mediante el runtime del servicio.
- **FR-002**: El servicio desplegado MUST exponer la API mediante su contenedor (el runtime del contenedor de servicio sirve las peticiones de la interfaz HTTP).

**Chequeo de salud de conectividad**

- **FR-003**: El sistema MUST exponer un chequeo de salud mediante un endpoint HTTP GET en el contenedor de servicio y mediante un comando CLI, ambos con el mismo contrato de respuesta que verifique conectividad real con la base de datos relacional dedicada: no puede considerarse salud verificada sin evidencia de acceso a la base de datos.
- **FR-004**: Cuando la base de datos relacional dedicada está accesible, el chequeo de salud MUST indicar salud OK.
- **FR-005**: Cuando la base de datos relacional dedicada está inaccesible, el chequeo de salud MUST indicar un estado de salud de fallo.
- **FR-006**: El chequeo de salud MUST verificar la conectividad en el mismo flujo de petición: una consulta al endpoint de chequeo MUST reflejar la disponibilidad actual de la base de datos (no un resultado cacheado o anterior).

### Non-Functional Requirements (RNF)

- **RNF-001**: El sistema MUST ser portátil entre motores de persistencia: la selección transparente del motor MUST ocurrir vía `DATABASE_URL`: `postgresql://...` selecciona el adaptador PostgreSQL; `sqlite:///...` o ausencia de variable por defecto `:memory:` selecciona SQLite (alineado con ADR-004).
- **RNF-002**: El chequeo de salud MUST ser real y sin caché: el endpoint `GET /health` MUST ejecutar consultas reales contra la base de datos configurada en cada petición, sin resultados cacheados ni dependencias de entorno fijas.
- **RNF-003**: El despliegue en contenedores MUST ser reproducible: el repositorio estándar incluye `Dockerfile` (imagen base `python:3.12-slim` + gestión con `uv`), `.dockerignore` y `docker-compose.yml` con el servicio `db` (imagen `postgres:16-alpine`, volumen de datos y chequeo `pg_isready`) y el servicio `api` sincronizado por `service_healthy`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las peticiones al API desplegado en contenedores MUST responder exitosamente cuando el servicio y la base de datos están accesibles.
- **SC-002**: El chequeo de salud indica salud OK en el 100 % de los casos de aceptación cuando la base de datos está accesible.
- **SC-003**: El chequeo de salud indica estado de fallo en el 100 % de los casos de aceptación cuando la base de datos está inaccesible.
- **SC-004**: El chequeo de salud NO MUST marcar salud OK mientras la conectividad a la base de datos esté rota.
- **SC-005**: La ejecución desplegada en contenedores MUST permitir que la base de datos relacional dedicada se ejecute como contenedor desplegido mediante el runtime del despliegue.

## Escenarios BDD de aceptación

```gherkin
Scenario: Chequeo de salud real mediante endpoint HTTP y comando CLI
  Given que el sistema está corriendo con la base de datos configurada
  When se consulta GET /health
  Then responde 200 OK con {"status": "ok", "database": "connected"}
  And el comando CLI health ejecuta SELECT 1 real sobre la base configurada devolviendo {"status": "ok", "database": "connected"}

Scenario: Chequeo de salud ante fallo de conectividad
  Given que falla el adaptador de persistencia (check_health() retorna False)
  When se consulta GET /health
  Then responde 503 Service Unavailable con {"status": "error", "database": "unavailable"}

Scenario: Selección transparente del motor SQLite/PostgreSQL vía DATABASE_URL
  Given que DATABASE_URL es postgresql://...
  When se selecciona el adaptador de persistencia
  Then se selecciona el adaptador PostgreSQL
  Given que DATABASE_URL es sqlite:///... o no está definida
  When se selecciona el adaptador de persistencia
  Then se selecciona SQLite por defecto (:memory:)

Scenario: Orquestación reproducible en 2 contenedores (api + db)
  Given que se despliega con Docker Compose
  When el contenedor db levanta con image postgres:16-alpine, volumen y chequeo pg_isready
  Then el contenedor db responde healthy
  And el contenedor api ejecuta con DATABASE_URL y depends_on: db service_healthy
  And el contenedor api tiene healthcheck sobre /health
```

## Assumptions

- La base de datos relacional dedicada es un motor relacional dedicado; la ejecución en contenedores usa Docker Compose con contenedores `api` y `db` (alineado con ADR-004).
- La selección del motor por `DATABASE_URL` (alineado con ADR-004): `postgres://...` o `postgresql://...` → motor relacional dedicado; `sqlite:///...` o ruta → motor embebido; default `sqlite:///:memory:` para pruebas locales sin Docker.
- Contrato del chequeo de salud (endpoint HTTP y comando CLI, con el mismo contrato): `200 OK` con `{"status": "ok", "database": "connected"}` cuando la conectividad está verificada; `503 Service Unavailable` con `{"status": "error", "database": "unavailable"}` cuando la base de datos no está accesible.
- El despliegue expone la API mediante el runtime de los contenedores desplegados.

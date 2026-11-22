<!--
Sync Impact Report
==================
Versión anterior: sin versión (plantilla sin ratificar) → 1.0.0
Tipo de bump: MAJOR (ratificación inicial de la constitución oficial)
  No existía una versión ratificada previa: `.specify/memory/constitution.md`
  seguía siendo la plantilla y `docs/constitution.md` era el documento informal
  de referencia. Se adopta 1.0.0 como línea base formal; no hay principios
  eliminados ni redefinidos de forma incompatible.

Principios (todos nuevos; consolidan `docs/constitution.md` §1–§3):
  - I. Núcleo Determinista Único (antes §1)
  - II. Arquitectura Hexagonal Estricta (ADR-003) (antes §2)
  - III. Gobernanza del Stack Tecnológico (antes §3, parte 1)
  - IV. Verificación Estática de Fronteras (antes §3, parte 2)
  - V. Pruebas BDD Obligatorias (antes §3, parte 3)

Secciones añadidas:
  - Restricciones Adicionales
  - Flujo de Desarrollo y Puertas de Calidad
  - Governance

Secciones eliminadas: ninguna.

Pendientes de seguimiento (no bloquean la ratificación, pero la constitución
los vuelve exigibles):
  - `docs/adr/001-*.md` no existe en el repositorio; la constitución cita
    ADR-001 como decisión de persistencia. Publicar ese ADR.
  - `ruff` no figura en `pyproject.toml` ni en `uv.lock`: la puerta
    `uv run ruff check src/` todavía no puede ejecutarse. Añadir la dependencia
    de desarrollo y la configuración de fronteras.
  - `src/application/ports.py` y `src/adapters/outbound/` aún no existen y
    `DATABASE_URL` no se consume en el código: son estado objetivo, no estado
    actual.
-->

# Constitución de IncidentOps

Principios normativos que rigen la evolución del sistema. `AGENTS.md` registra el
estado operativo y los comandos disponibles; esta constitución fija las decisiones
que deben guiar los cambios. Ante un conflicto, prevalece esta constitución y se
actualiza `AGENTS.md`.

## Core Principles

### I. Núcleo Determinista Único

- `src/domain/` es la única fuente de verdad para triaje y enrutamiento,
  severidades P0–P3, política de SLA, escalamiento, equipos válidos, estados y
  clave de duplicados. Sus módulos canónicos son `models.py`, `triage_rules.py` y
  `sla_calculator.py`.
- Las reglas del dominio DEBEN ser funciones puras y deterministas: la misma
  entrada y el mismo instante de referencia producen siempre el mismo resultado,
  con independencia del reloj del host, la configuración regional, las variables
  de entorno, la red o la base de datos. El instante de referencia se recibe como
  argumento explícito.
- `src/domain/` NO DEBE importar frameworks ni IO: quedan prohibidos FastAPI,
  Pydantic, Typer, `sqlite3`, `uvicorn`, clientes HTTP, `os.environ`, acceso a
  archivos, red o reloj.
- Los adaptadores solo traducen entradas, presentan salidas y orquestan casos de
  uso: NO DEBEN reimplementar, ajustar ni saltarse estas reglas.
- La política de SLA vigente (ADR-002) es P0/P1 24/7; P2/P3 de lunes a viernes
  08:00–18:00; el escalamiento se activa al 75 % del tiempo límite y solo sobre
  incidentes no resueltos.
- Toda modificación de la política de SLA o de las reglas de triaje DEBE
  actualizar, en el mismo cambio, sus criterios BDD y sus casos de verificación
  asertados.

**Rationale**: un único núcleo determinista permite que web, terminal y el futuro
MCP compartan exactamente el mismo criterio operativo, y que las reglas se
verifiquen sin levantar infraestructura.

### II. Arquitectura Hexagonal Estricta (ADR-003)

- Las dependencias apuntan hacia el centro: `adapters/inbound` → `application` →
  `domain`. El dominio no conoce a nadie; los adaptadores salientes implementan
  puertos definidos por la aplicación.
- `src/application/` contiene `services.py` con los casos de uso compartidos
  (`IncidentService`) y `ports.py` con los puertos secundarios expresados como
  `typing.Protocol`. NO DEBE contener FastAPI, Pydantic, Typer ni SQL.
- `src/adapters/inbound/` aloja los adaptadores primarios: HTTP con FastAPI
  (`api/`) y CLI con Typer (`cli.py`). Un futuro adaptador MCP se incorpora en
  este mismo directorio, reutilizando los casos de uso, sin duplicar lógica ni
  tocar el núcleo.
- `src/adapters/outbound/` aloja los adaptadores secundarios intercambiables. La
  implementación concreta se selecciona en el punto de composición a partir de
  `DATABASE_URL`; el dominio y la aplicación NO DEBEN leer variables de entorno
  ni conocer el motor de persistencia.
- Ningún adaptador define reglas de negocio ni filtra detalles de transporte o
  persistencia hacia el centro. El mapeo entre el modelo de dominio y su
  representación persistida vive en el adaptador saliente.
- La deuda de rendimiento de `src/incident_repository.py` (escaneo completo y
  N+1) es una preocupación del adaptador saliente y se aborda únicamente en su
  fase propia, según ADR-003.

**Rationale**: la inversión de dependencias es el límite permanente que permite
cambiar interfaces y motores de datos (H001–H004) sin reescribir las reglas.

### III. Gobernanza del Stack Tecnológico

- Python >= 3.10 gestionado con `uv`: `uv sync` para el entorno y `uv run` para
  toda ejecución. El repositorio NO es un paquete instalable
  (`[tool.uv] package = false`); NO DEBE añadirse `pip install -e .` ni metadatos
  de empaquetado.
- HTTP se implementa con FastAPI y validación con Pydantic v2; CLI con Typer.
  Ambos son adaptadores delgados sobre los casos de uso. Sustituir o añadir otro
  framework web, de validación o de CLI requiere un ADR previo.
- La persistencia usa SQLite3 de la biblioteca estándar, sin ORMs pesados,
  conforme a ADR-001. Cualquier otro motor u ORM —incluido el motor relacional
  dedicado de H004— exige un ADR específico antes de escribir código.
- Una nueva dependencia de ejecución DEBE justificarse en el cambio; si cruza una
  frontera hexagonal o reemplaza una decisión gobernada, requiere ADR.

**Rationale**: un stack pequeño y explícito mantiene el núcleo portable y evita
que una elección de herramienta se convierta en una regla de negocio implícita.

### IV. Verificación Estática de Fronteras

- `uv run ruff check src/` DEBE pasar sin errores. Es la puerta estática que hace
  verificable el Principio II, no una recomendación de estilo.
- La configuración de Ruff DEBE codificar al menos estas fronteras: `src/domain/`
  no importa `src/application/`, `src/adapters/`, frameworks ni módulos de IO; y
  `src/application/` no importa `src/adapters/`. Una violación DEBE fallar el
  chequeo.
- Las reglas de frontera viven en configuración versionada del repositorio. Una
  supresión local (`noqa`) DEBE justificarse con un comentario que explique por qué
  la excepción no rompe la frontera.
- Debilitar o desactivar una regla de frontera constituye un cambio de
  gobernanza y requiere enmienda de esta constitución.

**Rationale**: una frontera que solo está documentada se erosiona; expresada como
regla ejecutable, cualquier desvío se detecta antes de la revisión.

### V. Pruebas BDD Obligatorias

- Los criterios de aceptación se escriben en BDD (`Given / When / Then`) y se
  automatizan con `pytest`. `uv run pytest -v` DEBE pasar completo.
- NO DEBE usarse `skip`, `xfail` ni relajación de aserciones para dejar la suite
  en verde; una prueba que ya no aplica se elimina o se reescribe de forma
  explícita en el mismo cambio.
- Todo cambio de comportamiento DEBE incluir o actualizar sus pruebas en el mismo
  cambio, con trazabilidad al escenario de la spec correspondiente.
- Las pruebas NO DEBEN depender de red ni de servicios externos: el dominio se
  prueba de forma pura y los adaptadores en proceso. La paridad HTTP/CLI es
  obligatoria para los casos acordados.

**Rationale**: las pruebas BDD son el contrato observable del sistema y la única
evidencia aceptada de que un cambio preserva el comportamiento determinista.

## Restricciones Adicionales

- Fronteras de importación permitidas por capa:

  | Capa | Puede importar | No puede importar |
  | --- | --- | --- |
  | `src/domain/` | biblioteca estándar pura (`datetime`, `typing`, etc.) | `src/application/`, `src/adapters/`, frameworks, IO |
  | `src/application/` | `src/domain/`, biblioteca estándar | `src/adapters/`, frameworks, SQL |
  | `src/adapters/inbound/` | `src/application/`, `src/domain/`, su framework | reglas de negocio propias |
  | `src/adapters/outbound/` | `src/application/` (puertos), `src/domain/`, su motor | reglas de negocio propias |

- Esta constitución describe el estado objetivo. Cuando el repositorio aún no lo
  alcance, la brecha se registra como deuda explícita; no constituye una
  excepción permanente ni autoriza atajos.
- Las decisiones citadas por esta constitución (ADR-001, ADR-002, ADR-003) DEBEN
  estar publicadas en `docs/adr/`. Mientras un ADR citado no exista, su contenido
  normativo es el de esta constitución.
- No hay CI configurado: la verificación es manual mediante los comandos
  documentados. La ausencia de CI no relaja ninguna puerta de calidad.
- `AGENTS.md` es el registro operativo (comandos, estado, trampas conocidas) y
  DEBE actualizarse cuando cambien los comandos o el estado del repositorio; no
  puede contradecir esta constitución.

## Flujo de Desarrollo y Puertas de Calidad

1. Especificar el comportamiento en BDD antes de implementar; si el cambio altera
   arquitectura, stack o persistencia, emitir o actualizar el ADR primero.
2. Implementar respetando la dirección de dependencias y sin duplicar reglas
   fuera de `src/domain/`.
3. Verificar antes de cerrar el cambio, como mínimo:
   - `uv run ruff check src/`
   - `uv run pytest -v`
   - `uv run python -m src.domain.sla_calculator` y
     `uv run python -m src.domain.triage_rules` cuando se toquen `models.py`,
     `sla_calculator.py` o `triage_rules.py`.
4. Revisar el cambio contra esta constitución: fronteras intactas, reglas solo en
   el dominio, dependencias justificadas, ADR cuando corresponda, pruebas
   trazables y `AGENTS.md` sincronizado.
5. Los artefactos normativos (constitución, ADRs y specs) se redactan en español,
   igual que el resto de la documentación del repositorio.

Una excepción a cualquier puerta SOLO es válida mediante ADR y enmienda de esta
constitución, con alcance y fecha de expiración documentados.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica o documento del
  repositorio. Ante conflicto, se ajusta el documento subordinado; `AGENTS.md` se
  actualiza para reflejar la decisión.
- **Procedimiento de enmienda**: toda enmienda DEBE (1) motivar el cambio y su
  impacto en principios y puertas, (2) incluir el ADR correspondiente si altera
  arquitectura, stack o persistencia, (3) actualizar en el mismo cambio las
  pruebas y documentos afectados, (4) incrementar la versión según la política
  semántica y (5) registrar la fecha de enmienda. El Sync Impact Report es
  material temporal de revisión y se elimina antes de confirmar el cambio.
- **Versionado semántico**: MAJOR por eliminación o redefinición incompatible de
  principios o reglas de gobernanza; MINOR por nuevo principio, sección o
  expansión material de una guía existente; PATCH por aclaraciones, correcciones
  de redacción o refinamientos no semánticos.
- **Revisión de cumplimiento**: cada cambio se revisa contra los cinco
  principios. Un cambio que no cumpla las puertas de calidad no se integra. Al
  cierre de cada hito del roadmap (H001–H004) se revisa la vigencia de esta
  constitución y se enmienda si el estado objetivo ya se alcanzó o cambió.
- Toda infracción detectada se corrige en el cambio que la introdujo; si no es
  posible, se registra como deuda con su ADR y su fecha de resolución.

**Version**: 1.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22

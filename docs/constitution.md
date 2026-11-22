# Constitución del Proyecto — IncidentOps

Principios normativos que rigen la evolución del sistema. `AGENTS.md` registra el estado operativo y los comandos disponibles; esta constitución fija las decisiones que deben guiar los cambios. Ante un conflicto, se actualiza `AGENTS.md`.

## 1. Dominio determinista único

- `src/domain/` es la única fuente de verdad para triaje y enrutamiento, severidades P0–P3, política de SLA (P0/P1 24/7; P2/P3 lunes a viernes 08:00–18:00), escalamiento al 75 % solo sobre incidentes no resueltos, equipos válidos, estados y clave de duplicados.
- Misma entrada y mismo instante de referencia producen siempre el mismo resultado. Los adaptadores solo traducen entradas, presentan salidas y orquestan casos de uso: no reimplementan ni ajustan estas reglas.
- Toda modificación de la política de SLA (ADR-002) o del triaje requiere actualizar en el mismo cambio sus criterios BDD y sus casos de verificación.

## 2. Arquitectura Hexagonal (ADR-003)

- Las dependencias apuntan hacia el centro: el dominio es puro, sin IO ni frameworks.
- `src/application/` concentra los casos de uso compartidos (`IncidentService`) y los puertos secundarios definidos con `typing.Protocol`.
- `src/adapters/inbound/` aloja los adaptadores primarios para API REST y CLI; un futuro adaptador MCP se incorporará aquí sin duplicar lógica ni tocar el núcleo.
- `src/adapters/outbound/` aloja adaptadores secundarios intercambiables. Ningún adaptador define reglas de negocio ni filtra detalles de transporte o persistencia hacia el dominio.

## 3. Gobernanza técnica y calidad

- Python >= 3.10 gestionado con `uv`; el repositorio no se trata como paquete instalable.
- REST con FastAPI + Pydantic v2 y CLI con Typer, siempre como adaptadores delgados sobre los casos de uso.
- Persistencia con SQLite3 estándar y sin ORMs pesados; cualquier cambio de motor de base de datos —incluido el de H004— exige un ADR previo.
- Criterios de aceptación escritos en BDD (`Given / When / Then`) y pruebas de aceptación automatizadas con `pytest`; todo cambio relevante debe conservar su trazabilidad y pasar estas pruebas.

> Esta constitución es normativa y describe el estado objetivo. Las herramientas aún no adoptadas se incorporan con su ADR y su correspondiente actualización de `AGENTS.md`; mientras tanto, rigen los comandos documentados allí.

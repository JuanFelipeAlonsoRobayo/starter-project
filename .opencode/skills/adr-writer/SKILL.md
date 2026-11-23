---
name: adr-writer
description: Redacta y valida ADRs arquitectónicos estrictos para IncidentOps según el registro append-only de docs/adr/. Úsala al crear un ADR nuevo en docs/adr/, al decidir o evaluar una decisión estructural difícil de revertir (puertos, adaptadores, dirección de dependencias, contratos externos o de interfaz, sustitución de motor de datos), al reemplazar un ADR por uno nuevo, y al revisar que un ADR cumpla el estándar: una decisión por archivo, al menos 2 opciones reales con ventajas/desventajas auténticas, diagrama Mermaid exclusivamente estructural y sin duplicar criterios de BDD de docs/spec.md ni listas de archivos/tareas de docs/plan.md y specs/*/plan.md.
---

# ADR Writer — Registro arquitectónico estricto

Norma de referencia: `docs/adr/000-template.md` (plantilla actualizada). Estándar del
registro: **un ADR registra exactamente una decisión arquitectónica estructural y
difícil de revertir; el registro es inmutable y append-only.**

## Cuándo activar esta skill

- Crear un ADR nuevo en `docs/adr/` (el siguiente número disponible de la secuencia).
- Decidir algo que cambie la estructura del sistema y la dureza de su reversión:
  dirección de dependencias/puertos y adaptadores, contratos externos o de interfaz,
  sustitución de motor de datos o de base de datos, despliegue embebido vs externo.
- Evaluar qué cosas "merecen ADR": la decisión debe ser estructural y difícil de
  revertir; lo que se puede revertir tácticamente va en `docs/spec.md`,
  `docs/plan.md`, `specs/*/plan.md` o se queda en código.
- Revisar/validar un ADR antes de presentarlo como registro.

## 1. Formato base obligatorio (plantilla `docs/adr/000-template.md`)

- Metadatos: `Estado` (`Propuesto | Aceptado | Reemplazado por ADR-XXX`), `Fecha`
  (`YYYY-MM-DD`; hoy es 2026-11-22), `Autor(es)`, `Reemplaza a`.
- `Reemplaza a`: "(No aplica)" o vacío en ADR nuevos; número del ADR anterior en el
  que se sustituye.
- **Prohibido incluir `Componentes Afectados`** con enlaces frágiles: la plantilla
  no lo incluye, así que el estándar es no tenerlo en los ADR nuevos.
- **Prohibidas viñetas tácticas de comandos** (`uv run ...`, `npm ...`) como parte
  del texto del ADR.

## 2. Registro inmutable append-only

- **Una decisión por archivo**: no poner dos decisiones independientes en el mismo
  ADR; parte en dos ADRs.
- Decisión no editable: un ADR una vez Aceptado no se reescribe ni se fusiona; su
  contenido queda en el registro de primera mano.
- Superseding: para cambiar una decisión aceptada se crea un ADR nuevo (siguiente
  número de la secuencia) con `Reemplaza a: ADR-XXX` (el anterior), y el ADR anterior
  cambia su `Estado` a `Reemplazado por ADR-XXX`. El registro conserva el historial
  completo; no se reescribe ni se renumeren pasados ADRs.

## 3. Opciones consideradas (mínimo 2 reales)

- Documentar **al menos 2 opciones arquitectónicas reales** en `## 2. Opciones
  Consideradas` (A y B obligatorias de la plantilla).
- Cada opción: **ventajas** y **desventajas** auténticas, con riesgos reales del
  entorno (acoplamiento, curva de aprendizaje, costo, escalabilidad, dependencias
  externas).
- **Prohibido**: opciones de relleno ni strawmen. Cada opción debe ser plausible y
  tener al menos una desventaja con sustancia que haga preferible la otra; no hacer
  dos opciones similares solo para cumplir el número dos.

## 4. Decisión arquitectónica

- Escoger una opción real y explicar **por qué** (desacoplamiento, escalabilidad,
  costos de operación, restricciones de versionamiento).
- Diagrama Mermaid: **opcional**; si aporta, exclusivamente estructural — capas
  (`subgraph`), límites o topología de componentes con flechas de flujo entre
  módulos. **Prohibido**: flujos `if/else` algorítmicos o flujos de ejecución
  detallados de un camino de código. Si no aporta, se omite.

## 5. Consecuencias y trade-offs

- **Positivas**: beneficios estructurales de desacoplamiento, mantenibilidad,
  escalabilidad o portabilidad.
- **Negativas / Trade-offs**: complejidad añadida asumida, restricciones
  operativas o costos de mantenimiento.

## 6. Prohibiciones explícitas (no duplicar `spec.md`/`plan.md`)

- No duplicar **criterios funcionales o de BDD** de `docs/spec.md` y `specs/*.md`
  (escenarios Given/When/Then, estados observables, contratos de salida de la
  API): si un criterio funcional aparece en un ADR, justifica solo una decisión
  estructural que lo determine; lo funcional sigue en spec.
- No duplicar **listas de archivos/tareas** de `docs/plan.md` y `specs/*/plan.md`:
  inventarios de archivos modificados, plan de tareas y fechas de entrega no son
  ADR.

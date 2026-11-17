# ADR-002: Cálculo de SLA en Horario Hábil e Intersección Diaria O(D)

- **Estado**: Aceptado
- **Fecha**: 2026-11-16
- **Autor(es)**: Equipo de Ingeniería / SRE (IncidentOps)
- **Componentes Afectados**: [`src/sla_calculator.py`](../../src/sla_calculator.py)`

---

## 1. Contexto y Problema

El módulo `src/sla_calculator.py` evalúa de forma determinista el cumplimiento de los Acuerdos de Nivel de Servicio (SLA) para los incidentes de la plataforma IncidentOps mediante la función `evaluate_sla_status`.

En su implementación original, el cálculo presentaba dos defectos críticos de negocio:
1. **Cálculo continuo 24/7 indiscriminado**: Se calculaba `elapsed_minutes` restando directamente `end_time - incident.created_at` para todas las severidades. Esto ignoraba la bandera `operates_24x7=False` definida en `SLA_POLICY_TABLE` para las severidades **P2** (480 min) y **P3** (1440 min), descontando noches y fines de semana como tiempo operativo y provocando falsos incumplimientos (`is_breached=True`).
2. **Apagado prematuro de la alerta de escalamiento**: La condición `requires_escalation` incluía la restricción `and not is_breached`. Como consecuencia, cuando un incidente abierto superaba el 100% de su tiempo límite, la bandera de escalamiento pasaba a `False`, desactivando las alertas preventivas/correctivas justo cuando el ticket se encontraba vencido.

**Restricciones del sistema**:
- Uso exclusivo de la librería estándar de Python (`datetime`), manteniendo cero dependencias externas.
- Preservar intacta la firma de `evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation` para no romper los consumidores existentes (`src/incident_repository.py`).
- Mantener alta eficiencia algorítmica al evaluar lotes de incidentes.

---

## 2. Opciones Consideradas

1. **Opción A — Cálculo continuo 24/7 para todas las prioridades (Estado actual)**:
   - *Ventajas*: Complejidad $O(1)$ trivial mediante resta directa de marcas de tiempo.
   - *Desventajas*: Incumple las reglas de negocio para severidades P2 y P3 al penalizar horas nocturnas y fines de semana, generando falsos positivos de SLA vencido.

2. **Opción B — Iteración minuto a minuto ($O(M)$)**:
   - *Ventajas*: Fácil de razonar e implementar avanzando un `timedelta(minutes=1)` desde `created_at` hasta `end_time`.
   - *Desventajas*: Ineficiente y costoso en CPU para incidentes de larga duración (por ejemplo, tickets P3 o incidentes abiertos durante semanas requieren decenas de miles de iteraciones por cada llamada).

3. **Opción C — Uso de librerías externas de calendario (`pandas`, `businesstime`, `workalendar`)**:
   - *Ventajas*: Abstracciones preconstruidas para rangos hábiles.
   - *Desventajas*: Viola la restricción arquitectónica de cero dependencias externas y añade sobrecarga innecesaria al entorno de ejecución.

4. **Opción D — Iteración diaria ($O(D)$) con intersección de ventanas horarias y escalamiento unificado**:
   - *Ventajas*: Utiliza únicamente `datetime` estándar. Escala linealmente con el número de días calendario ($O(D)$), resolviendo semanas o meses en pocas iteraciones. Maneja con exactitud bordes fuera de horario y fines de semana mediante acotación `[max(inicio), min(fin)]`.
   - *Desventajas*: Requiere lógica explícita para construir los límites diarios (`08:00` a `18:00`) e iterar fecha por fecha.

---

## 3. Decisión Arquitectónica

Se elige la **Opción D (Iteración diaria $O(D)$ con intersección de ventanas y escalamiento unificado)** por las siguientes razones:

1. **Precisión en Horario Hábil (P2 y P3)**: Cuando `rule.operates_24x7` es `False`, se recorre día por día desde `created_at.date()` hasta `end_time.date()`. Los sábados y domingos (`weekday() >= 5`) se omiten. Para cada día entre lunes y viernes (`weekday() < 5`), se define la ventana laboral `[08:00, 18:00]` y se calcula su intersección con el intervalo real del incidente mediante `effective_start = max(created_at, window_start)` y `effective_end = min(end_time, window_end)`. Si `effective_end > effective_start`, se acumulan los segundos correspondientes.
2. **Continuidad 24/7 (P0 y P1)**: Cuando `rule.operates_24x7` es `True`, se conserva el cálculo directo en $O(1)$.
3. **Escalamiento Unificado**: Se elimina la cláusula `and not is_breached` en el cálculo de `requires_escalation`. Ahora todo incidente no resuelto (`status != "RESOLVED"`) que alcance o supere el umbral del 75% (`elapsed_minutes >= escalation_limit`) mantendrá activa la bandera `requires_escalation=True`, incluso después de haber vencido su SLA.

```mermaid
flowchart TD
    Start(["Inicio: evaluate_sla_status(incident, reference_time)"]) --> GetRule["Obtener SLARule según incident.severity"]
    GetRule --> DefEnd["end_time = incident.resolved_at o reference_time"]
    DefEnd --> CheckDates{"¿end_time < created_at?"}
    CheckDates -- Sí --> Error(["Lanzar ValueError"])
    CheckDates -- No --> Check24x7{"¿rule.operates_24x7 es True?"}

    Check24x7 -- "Sí (P0, P1)" --> Calc24x7["delta_seconds = (end_time - created_at).total_seconds()\nelapsed_minutes = int(delta_seconds // 60)"]
    Check24x7 -- "No (P2, P3)" --> InitDays["Inicializar total_seconds = 0\ncurrent_date = created_at.date()"]

    InitDays --> LoopCond{"¿current_date <= end_time.date()?"}
    LoopCond -- Sí --> IsWeekday{"¿Es Lunes a Viernes?\n(weekday < 5)"}
    IsWeekday -- No --> NextDay["Avanzar current_date + 1 día"]
    IsWeekday -- Sí --> Intersect["Ventana: 08:00 a 18:00\neff_start = max(created_at, win_start)\neff_end = min(end_time, win_end)"]
    Intersect --> ValidOverlap{"¿eff_end > eff_start?"}
    ValidOverlap -- Sí --> AddSec["total_seconds += (eff_end - eff_start).total_seconds()"]
    ValidOverlap -- No --> NextDay
    AddSec --> NextDay
    NextDay --> LoopCond

    LoopCond -- No --> CalcBizMin["elapsed_minutes = int(total_seconds // 60)"]

    Calc24x7 --> EvalMetrics["remaining_minutes = max_resolution_minutes - elapsed_minutes\nis_breached = elapsed_minutes > max_resolution_minutes\nescalation_limit = int(max_resolution_minutes * 0.75)"]
    CalcBizMin --> EvalMetrics

    EvalMetrics --> CheckEsc{"¿status != 'RESOLVED'\nY elapsed_minutes >= escalation_limit?"}
    CheckEsc -- Sí --> EscTrue["requires_escalation = True"]
    CheckEsc -- No --> EscFalse["requires_escalation = False"]

    EscTrue --> Return(["Retornar SLAEvaluation"])
    EscFalse --> Return
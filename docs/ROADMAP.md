# Roadmap — IncidentOps (Borrador)

Hitos de evolución del producto y su operación, ordenados por valor entregado.

| Hito | Objetivo | Resultado observable |
| --- | --- | --- |
| **H001 — Triaje multi-interfaz** | Clasificar y enrutar reportes de forma determinista, sin persistencia. | Clasificación inmediata disponible desde web y terminal. |
| **H002 — Resumen de incidentes activos** | Consultar el estado operativo actual de los incidentes. | Incidentes activos, incumplimientos de SLA y filtrado por componente visibles desde web y terminal. |
| **H003 — Ciclo de vida, duplicados y SLA** | Registrar incidentes entrantes de forma persistente y auditar su cumplimiento. | Historial consultable, alerta de equivalentes abiertos y SLA auditable en cualquier instante de referencia. |
| **H004 — Persistencia dedicada y runtime en contenedores** | Hacer reproducible la ejecución del servicio y su entorno de datos. | Arranque en contenedores con base de datos relacional dedicada y verificación real de conectividad operativa. |

## Secuencia propuesta

H001 → H002 → H003 → H004: primero la decisión inmediata, luego la visibilidad, después el ciclo de vida y, por último, la reproducibilidad operativa.

> Borrador sujeto a priorización; fechas y alcance detallado pendientes de acordar.

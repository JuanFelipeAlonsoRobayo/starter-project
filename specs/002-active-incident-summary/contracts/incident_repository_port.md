# Contrato — `IncidentRepositoryPort`

Puerto secundario definido por la aplicación (`src/application/ports.py`);
implementado por `SqliteIncidentRepository` (`src/adapters/outbound/sqlite_repository.py`).

| Método | Semántica |
| --- | --- |
| `save_incident(incident: Incident) -> None` | Persiste un incidente (insert-or-replace). No devuelve ID generado. |
| `get_incident(incident_id: str) -> Incident \| None` | Devuelve el incidente por clave PK; `None` si no existe. |
| `find_open_duplicates(duplicate_group_key: str, created_at: datetime, exclude_incident_id: str \| None = None) -> list[Incident]` | Incidentes abiertos (`OPEN`/`IN_PROGRESS`) con el mismo grupo clave de duplicado y `created_at <= given`, ordenados de menor a mayor antigüedad; excluye el ID dado. |
| `list_active_incidents(reference_time: datetime, component: str \| None = None) -> list[Incident]` | Devuelve los incidentes con estado `OPEN`/`IN_PROGRESS` (así entren). Filtro por componente comparado sin mayúsculas ni espacios (normalización: `strip().lower()`, aplicada por el llamador). El dominio refiltra y ordena con `build_active_incident_summary`; la validación de `reference_time` contra `created_at` ocurre en el dominio. |
| `check_health() -> bool` | Verifica el estado de operación del adaptante (implementación de referencia: `SELECT 1` sobre la conexión). |
| `list_incidents() -> list[Incident]` | Lectura-toda del adaptante para la ruta de triaje (`IncidentService.summarize_active_incidents`); conserva `IncidentReadPort` con la misma semántica. |

Notas de diseño:

- El puerto es `@runtime_checkable`; la verificación de cumplimiento
  (`isinstance`) se exige en tests.
- El map de filas a `Incident` vive en el adaptante; ninguna regla de negocio
  se duplica en el puerto ni en la aplicación.
- `list_active_incidents` y `list_incidents` devuelven listas; el cálculo de
  SLA, orden (severidad, antigüedad, ID) y todos los campos del detalle están
  en `src/domain/active_summary.py` y `src/domain/sla_calculator.py`.

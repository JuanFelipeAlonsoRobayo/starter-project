# Contrato — `SqliteIncidentRepository`

Adaptante saliente SQLite del puerto `IncidentRepositoryPort`. Describe el
esquema y la consulta óptima introducida en este hito.

## Esquema

```sql
CREATE TABLE IF NOT EXISTS sla_policies (
    severity TEXT PRIMARY KEY,
    max_resolution_minutes INTEGER NOT NULL,
    operates_24x7 INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    duplicate_group_key TEXT
);

CREATE INDEX IF NOT EXISTS idx_incidents_component_status
    ON incidents (component, status);

CREATE INDEX IF NOT EXISTS idx_incidents_duplicate_group_key
    ON incidents (duplicate_group_key)
    WHERE duplicate_group_key IS NOT NULL;
```

- `sla_policies` se poblada desde `SLA_POLICY_TABLE` (ADR-002) en
  `_init_schema`.
- `seeds`: `seed_incidents` (compatibilidad H002) delega en `save_incident`.

## `list_active_incidents`

Consulta única:

```sql
SELECT i.incident_id, i.title, i.component, i.severity, i.status,
       i.created_at, i.resolved_at
FROM incidents AS i
INNER JOIN sla_policies AS p ON p.severity = i.severity
WHERE i.status IN ('OPEN', 'IN_PROGRESS')
  AND (? IS NULL OR lower(TRIM(i.component)) = lower(TRIM(?)))
```

Donde el parámetro de componente se normaliza en la capa de aplicación
(`normalize_component_filter`) y `? IS NULL` indica "sin filtro".

El `INNER JOIN` excluye severidades sin política persistida: datos
inconsistentes no surgen en el resumen (por diseño). El índice compuesto
`(component, status)` sirve la condición de filtro; `sla_policies` es tabla
pequeña (PK sobre `severity`).

## `find_open_duplicates`

```sql
SELECT * FROM incidents
WHERE duplicate_group_key = ?
  AND status IN ('OPEN', 'IN_PROGRESS')
  AND created_at <= ?
  AND incident_id != ?            -- solo si exclude_incident_id dado
ORDER BY created_at ASC, incident_id ASC
```

Pendiente de H003 (alcance forward-looking): persistir `duplicate_group_key`
vía `save_incident` desde la regla de triaje; el índice parcial cubre la
condición `IS NOT NULL`.

## Verificación de índices

```sql
PRAGMA index_list(incidents);          -- debe incluir idx_incidents_component_status
PRAGMA index_info('idx_incidents_component_status');  -- [(component, status)]
```

(La consulta filtra por expresiones `lower(TRIM(component))`; SQLite no usa
índices sobre expresiones, por lo que el planificador marca filtro y no SCAN.)

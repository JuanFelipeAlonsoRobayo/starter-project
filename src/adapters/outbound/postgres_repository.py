"""Adaptante saliente PostgreSQL sin ORM de incidentes (per ADR-004, Hito 004).

Complemento a `SqliteIncidentRepository`: misma semántica de puerto, motor
`psycopg[binary]` con `dict_row`, SQL parametrizada con `%s`, upsert
`INSERT ... ON CONFLICT DO UPDATE` y paridad temporal de los `datetime`
almacenados como `TEXT` ISO 8601 (per ADR-004).
"""

from datetime import datetime
from typing import List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row

from src.domain.models import OPEN_DUPLICATE_STATUSES, Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE


class PostgresIncidentRepository:
    """Repositorio de incidentes y políticas de SLA en PostgreSQL (psycopg, sin ORM)."""

    def __init__(self, conninfo: str) -> None:
        self._conn = psycopg.connect(conninfo, autocommit=True)
        self._conn.row_factory = dict_row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sla_policies (
                severity TEXT PRIMARY KEY,
                max_resolution_minutes INTEGER NOT NULL,
                operates_24x7 INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                component TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                duplicate_group_key TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_component_status "
            "ON incidents (component, status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_duplicate_group_key "
            "ON incidents (duplicate_group_key) WHERE duplicate_group_key IS NOT NULL"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_incidents_dup_key "
            "ON incidents (duplicate_group_key, status)"
        )
        for rule in SLA_POLICY_TABLE.values():
            self._conn.execute(
                """
                INSERT INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                VALUES (%s, %s, %s)
                ON CONFLICT (severity) DO UPDATE SET
                    max_resolution_minutes = EXCLUDED.max_resolution_minutes,
                    operates_24x7 = EXCLUDED.operates_24x7
                """,
                (
                    rule.severity,
                    rule.max_resolution_minutes,
                    1 if rule.operates_24x7 else 0,
                ),
            )

    def save_incident(self, incident: Incident, duplicate_group_key: Optional[str] = None) -> None:
        """Inserta o reemplaza un incidente (upsert `INSERT ... ON CONFLICT DO UPDATE`)."""
        key = incident.duplicate_group_key if incident.duplicate_group_key is not None else duplicate_group_key
        self._conn.execute(
            """
            INSERT INTO incidents
            (incident_id, title, component, severity, status, created_at, resolved_at, duplicate_group_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (incident_id) DO UPDATE SET
                title = EXCLUDED.title,
                component = EXCLUDED.component,
                severity = EXCLUDED.severity,
                status = EXCLUDED.status,
                created_at = EXCLUDED.created_at,
                resolved_at = EXCLUDED.resolved_at,
                duplicate_group_key = EXCLUDED.duplicate_group_key
            """,
            (
                incident.incident_id,
                incident.title,
                incident.component,
                incident.severity,
                incident.status,
                incident.created_at.isoformat(),
                incident.resolved_at.isoformat() if incident.resolved_at else None,
                key,
            ),
        )

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Devuelve el incidente por ID persistente, o None si no existe."""
        row = self._conn.execute(
            """
            SELECT incident_id, title, component, severity, status, created_at, resolved_at,
                   duplicate_group_key
            FROM incidents
            WHERE incident_id = %s
            """,
            (incident_id,),
        ).fetchone()
        return self._row_to_incident(row) if row is not None else None

    def find_open_duplicates(
        self, duplicate_group_key: str, created_at: datetime, exclude_incident_id: Optional[str] = None
    ) -> List[Incident]:
        """Incidentes con estado en `OPEN_DUPLICATE_STATUSES` con el mismo grupo de duplicados,
        creados antes de `created_at`; excluye el ID dado; ordenados de menor a mayor antigüedad."""
        placeholders = ", ".join(["%s"] * len(OPEN_DUPLICATE_STATUSES))
        sql_text = f"""
            SELECT incident_id, title, component, severity, status, created_at, resolved_at,
                   duplicate_group_key
            FROM incidents
            WHERE duplicate_group_key = %s
              AND status IN ({placeholders})
              AND created_at <= %s
            """
        params: Tuple[object, ...] = (
            duplicate_group_key,
            *OPEN_DUPLICATE_STATUSES,
            created_at.isoformat(),
        )
        if exclude_incident_id:
            sql_text += " AND incident_id != %s"
            params += (exclude_incident_id,)
        sql_text += " ORDER BY created_at ASC, incident_id ASC"
        return [self._row_to_incident(row) for row in self._conn.execute(sql_text, params).fetchall()]

    def list_active_incidents(self, reference_time: datetime, component: Optional[str] = None) -> List[Incident]:
        """Devuelve incidentes activos (OPEN/IN_PROGRESS) con filtro de componente normalizado.

        Una sola consulta con `INNER JOIN sla_policies` sobre severidades sin política
        persistida (dato inconsistente: no aparecen en el resumen). Paridad con
        `SqliteIncidentRepository.list_active_incidents`.
        """
        rows = self._conn.execute(
            """
            SELECT i.incident_id, i.title, i.component, i.severity, i.status,
                   i.created_at, i.resolved_at, i.duplicate_group_key
            FROM incidents AS i
            INNER JOIN sla_policies AS p ON p.severity = i.severity
            WHERE i.status IN ('OPEN', 'IN_PROGRESS')
              AND (%s IS NULL OR lower(TRIM(i.component)) = lower(TRIM(%s)))
            """,
            (component, component),
        ).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def check_health(self) -> bool:
        """Verifica el estado de operación del adaptante saliente: `SELECT 1` real."""
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except psycopg.Error:
            return False

    def list_incidents(self) -> List[Incident]:
        """Devuelve todos los incidentes; el filtrado de negocio ocurre en el dominio."""
        rows = self._conn.execute(
            """
            SELECT incident_id, title, component, severity, status, created_at, resolved_at,
                   duplicate_group_key
            FROM incidents
            """
        ).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def close(self) -> None:
        """Cierra la conexión subyacente."""
        self._conn.close()

    @staticmethod
    def _row_to_incident(row: dict) -> Incident:
        return Incident(
            incident_id=row["incident_id"],
            title=row["title"],
            component=row["component"],
            severity=row["severity"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None
            ),
            duplicate_group_key=row["duplicate_group_key"],
        )

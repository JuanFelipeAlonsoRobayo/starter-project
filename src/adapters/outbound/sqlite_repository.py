"""Adaptante saliente SQLite optimizado de incidentes (Hito 002).

Extración de Semana 1 (`src/incident_repository.py`) con la lectura única
para el resumen de incidentes activos: escaneo + filtro en SQL de activos
(OPEN/IN_PROGRESS) contra `sla_policies` por medio de `INNER JOIN`.
Contrato: `contracts/sqlite_incident_repository.md`.
"""

import sqlite3
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from src.domain.models import OPEN_DUPLICATE_STATUSES, Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE


class SqliteIncidentRepository:
    """Repositorio de incidentes y políticas de SLA en SQLite.

    Antes de H002 era lectura completa y N+1 sobre `sla_policies`; la
    optimización de rendimiento pertenece a esta fase (véase T007).
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        # FastAPI ejecuta los endpoints síncronos en un hilo distinto al de
        # construcción de la aplicación; la conexión debe permitir ese uso.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
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
            CREATE INDEX IF NOT EXISTS idx_incidents_dup_key
                ON incidents (duplicate_group_key, status);
            """
        )
        for rule in SLA_POLICY_TABLE.values():
            self.conn.execute(
                """
                INSERT OR REPLACE INTO sla_policies
                (severity, max_resolution_minutes, operates_24x7)
                VALUES (?, ?, ?)
                """,
                (rule.severity, rule.max_resolution_minutes, 1 if rule.operates_24x7 else 0),
            )
        self.conn.commit()

    def save_incident(self, incident: Incident, duplicate_group_key: Optional[str] = None) -> None:
        """Inserta o reemplaza un incidente."""
        key = incident.duplicate_group_key if incident.duplicate_group_key is not None else duplicate_group_key
        self.conn.execute(
            """
            INSERT OR REPLACE INTO incidents
            (incident_id, title, component, severity, status, created_at, resolved_at, duplicate_group_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        self.conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Devuelve el incidente por ID persistente, o None si no existe."""
        row = self.conn.execute(
            """
            SELECT incident_id, title, component, severity, status, created_at, resolved_at,
                   duplicate_group_key
            FROM incidents
            WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()
        return self._row_to_incident(row) if row is not None else None

    def find_open_duplicates(
        self, duplicate_group_key: str, created_at: datetime, exclude_incident_id: Optional[str] = None
    ) -> List[Incident]:
        """Incidentes con estado en `OPEN_DUPLICATE_STATUSES` (constante de dominio en
        `src/domain/models.py`) con el mismo grupo de duplicados, creados antes de
        `created_at`; excluye el ID dado; ordenados de menor a mayor antigüedad."""
        placeholders = ", ".join("?" for _ in OPEN_DUPLICATE_STATUSES)
        sql = f"""
            SELECT incident_id, title, component, severity, status, created_at, resolved_at,
                   duplicate_group_key
            FROM incidents
            WHERE duplicate_group_key = ?
              AND status IN ({placeholders})
              AND created_at <= ?
            """
        params: Tuple[object, ...] = (
            duplicate_group_key,
            *OPEN_DUPLICATE_STATUSES,
            created_at.isoformat(),
        )
        if exclude_incident_id:
            sql += " AND incident_id != ?"
            params += (exclude_incident_id,)
        sql += " ORDER BY created_at ASC, incident_id ASC"
        return [self._row_to_incident(row) for row in self.conn.execute(sql, params).fetchall()]

    def list_active_incidents(self, reference_time: datetime, component: Optional[str] = None) -> List[Incident]:
        """Devuelve incidentes activos (OPEN/IN_PROGRESS) con filtro de componente normalizado.

        Una sola consulta con `INNER JOIN sla_policies` sobre severidades sin política
        persistida (dato inconsistente: no aparecen en el resumen). El filtro de
        activos por estado es parte del WHERE; el ACK de `reference_time` y el
        filtro/orden de negocio quedan en el dominio.
        """
        cursor = self.conn.execute(
            """
            SELECT i.incident_id, i.title, i.component, i.severity, i.status,
                   i.created_at, i.resolved_at, i.duplicate_group_key
            FROM incidents AS i
            INNER JOIN sla_policies AS p ON p.severity = i.severity
            WHERE i.status IN ('OPEN', 'IN_PROGRESS')
              AND (? IS NULL OR lower(TRIM(i.component)) = lower(TRIM(?)))
            """,
            (component, component),
        )
        return [self._row_to_incident(row) for row in cursor.fetchall()]

    def check_health(self) -> bool:
        """Verifica el estado de operación del adaptante saliente."""
        try:
            self.conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def list_incidents(self) -> List[Incident]:
        """Devuelve todos los incidentes; el filtrado de negocio ocurre en el dominio."""
        cursor = self.conn.execute(
            """
            SELECT incident_id, title, component, severity, status, created_at, resolved_at,
                   duplicate_group_key
            FROM incidents
            """
        )
        return [self._row_to_incident(row) for row in cursor.fetchall()]

    def seed_incidents(self, incidents: Iterable[Incident]) -> None:
        """Inserta o reemplaza incidentes; utilidad de composición y pruebas."""
        for incident in incidents:
            self.save_incident(incident)

    def close(self) -> None:
        """Cierra la conexión subyacente."""
        self.conn.close()

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> Incident:
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

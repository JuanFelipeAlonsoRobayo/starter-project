"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA).

Implementa la decisión arquitectónica ADR-002:
- Cálculo continuo 24/7 para severidades críticas (P0 y P1, `operates_24x7=True`).
- Cálculo acotado a horario hábil (Lunes a Viernes, 08:00 a 18:00) mediante intersección
  diaria O(D) para severidades P2 y P3 (`operates_24x7=False`).
- Regla de escalamiento unificada para incidentes no resueltos que alcanzan el umbral
  del 75% o que ya han incumplido su SLA.
"""

from datetime import datetime, time, timedelta
from typing import Dict

from src.domain.models import Incident, SLAEvaluation, SLARule, SeverityLevel

BUSINESS_START_TIME = time(8, 0, 0)
BUSINESS_END_TIME = time(18, 0, 0)

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def _calculate_business_minutes(start_dt: datetime, end_dt: datetime) -> int:
    """Calcula los minutos transcurridos dentro del horario hábil (L-V, 08:00-18:00).

    Utiliza una iteración día por día O(D) intersectando el intervalo [start_dt, end_dt]
    con la ventana laboral diaria de cada día hábil.
    """
    total_seconds = 0.0
    current_date = start_dt.date()
    end_date = end_dt.date()

    while current_date <= end_date:
        # 0 = Lunes, ..., 4 = Viernes; 5 = Sábado, 6 = Domingo
        if current_date.weekday() < 5:
            window_start = datetime.combine(current_date, BUSINESS_START_TIME)
            window_end = datetime.combine(current_date, BUSINESS_END_TIME)

            effective_start = max(start_dt, window_start)
            effective_end = min(end_dt, window_end)

            if effective_end > effective_start:
                total_seconds += (effective_end - effective_start).total_seconds()

        current_date += timedelta(days=1)

    return int(total_seconds // 60)


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        delta_seconds = (end_time - incident.created_at).total_seconds()
        elapsed_minutes = int(delta_seconds // 60)
    else:
        elapsed_minutes = _calculate_business_minutes(incident.created_at, end_time)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED" and elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )


def _run_demo() -> None:
    """Ejecuta 5 casos de prueba verificando el cálculo de SLA 24/7 y horario hábil."""
    print("=== Demostración y Verificación de Cálculo Determinista de SLA (ADR-002) ===\n")

    # Caso 1: Cruce de fin de semana en horario hábil (P2)
    # Viernes 17:00 a Lunes 09:00 -> Viernes (60 min) + Sáb/Dom (0 min) + Lunes (60 min) = 120 min
    case_1_inc = Incident(
        incident_id="INC-2001",
        title="Latencia elevada en reporte de órdenes",
        component="reporting-api",
        severity="P2",
        status="OPEN",
        created_at=datetime(2026, 11, 6, 17, 0, 0),  # Viernes 17:00
    )
    eval_1 = evaluate_sla_status(case_1_inc, reference_time=datetime(2026, 11, 9, 9, 0, 0))
    assert eval_1.elapsed_minutes == 120, f"Esperado 120, obtenido {eval_1.elapsed_minutes}"
    assert not eval_1.is_breached
    assert not eval_1.requires_escalation
    print(
        f"[Caso 1 - Cruce de fin de semana P2] {eval_1.incident_id}: "
        f"elapsed={eval_1.elapsed_minutes}m / {eval_1.allowed_minutes}m | "
        f"breached={eval_1.is_breached} | escalation={eval_1.requires_escalation}"
    )

    # Caso 2: Creación fuera de horario laboral (madrugada y noche) en P3
    # Martes 05:30 a Martes 20:15 -> Solo cuenta de 08:00 a 18:00 = 600 min
    case_2_inc = Incident(
        incident_id="INC-2002",
        title="Desfase visual en exportación CSV",
        component="ui-portal",
        severity="P3",
        status="OPEN",
        created_at=datetime(2026, 11, 10, 5, 30, 0),  # Martes 05:30
    )
    eval_2 = evaluate_sla_status(case_2_inc, reference_time=datetime(2026, 11, 10, 20, 15, 0))
    assert eval_2.elapsed_minutes == 600, f"Esperado 600, obtenido {eval_2.elapsed_minutes}"
    assert not eval_2.is_breached
    assert not eval_2.requires_escalation
    print(
        f"[Caso 2 - Creación fuera de horario P3] {eval_2.incident_id}: "
        f"elapsed={eval_2.elapsed_minutes}m / {eval_2.allowed_minutes}m | "
        f"breached={eval_2.is_breached} | escalation={eval_2.requires_escalation}"
    )

    # Caso 3: Comparación directa 24/7 (P1) vs. Horario Hábil (P2) en ventana nocturna
    # Miércoles 17:00 a Jueves 09:00 -> 16 horas calendario (960 min) vs. 2 horas hábiles (120 min)
    start_night = datetime(2026, 11, 11, 17, 0, 0)
    end_morning = datetime(2026, 11, 12, 9, 0, 0)

    case_3_p1 = Incident(
        incident_id="INC-2003-P1",
        title="Errores intermitentes en pasarela de pagos",
        component="payment-gateway",
        severity="P1",
        status="OPEN",
        created_at=start_night,
    )
    case_3_p2 = Incident(
        incident_id="INC-2003-P2",
        title="Lentitud en sincronización de catálogo secundario",
        component="catalog-sync",
        severity="P2",
        status="OPEN",
        created_at=start_night,
    )
    eval_3_p1 = evaluate_sla_status(case_3_p1, reference_time=end_morning)
    eval_3_p2 = evaluate_sla_status(case_3_p2, reference_time=end_morning)
    assert eval_3_p1.elapsed_minutes == 960 and eval_3_p1.is_breached
    assert eval_3_p2.elapsed_minutes == 120 and not eval_3_p2.is_breached
    print(
        f"[Caso 3 - Comparación 24/7 vs Hábil] "
        f"P1 (24/7): elapsed={eval_3_p1.elapsed_minutes}m (breached={eval_3_p1.is_breached}) | "
        f"P2 (Hábil): elapsed={eval_3_p2.elapsed_minutes}m (breached={eval_3_p2.is_breached})"
    )

    # Caso 4: Escalamiento preventivo al alcanzar el 75% sin incumplir SLA (P2)
    # SLA P2 = 480 min; umbral 75% = 360 min. Lunes 08:00 a Lunes 14:00 = 360 min.
    case_4_inc = Incident(
        incident_id="INC-2004",
        title="Degradación en generación de facturas PDF",
        component="billing-service",
        severity="P2",
        status="IN_PROGRESS",
        created_at=datetime(2026, 11, 9, 8, 0, 0),
    )
    eval_4 = evaluate_sla_status(case_4_inc, reference_time=datetime(2026, 11, 9, 14, 0, 0))
    assert eval_4.elapsed_minutes == 360
    assert not eval_4.is_breached
    assert eval_4.requires_escalation
    print(
        f"[Caso 4 - Umbral Escalamiento 75% P2] {eval_4.incident_id}: "
        f"elapsed={eval_4.elapsed_minutes}m / {eval_4.allowed_minutes}m | "
        f"breached={eval_4.is_breached} | escalation={eval_4.requires_escalation}"
    )

    # Caso 5: Persistencia de escalamiento cuando el SLA ya está vencido (is_breached=True)
    # SLA P0 = 60 min (24/7). Abierto hace 90 min -> is_breached=True y requires_escalation=True.
    case_5_inc = Incident(
        incident_id="INC-2005",
        title="Caída total del clúster de autenticación",
        component="auth-service",
        severity="P0",
        status="OPEN",
        created_at=datetime(2026, 11, 9, 10, 0, 0),
    )
    eval_5 = evaluate_sla_status(case_5_inc, reference_time=datetime(2026, 11, 9, 11, 30, 0))
    assert eval_5.elapsed_minutes == 90
    assert eval_5.is_breached
    assert eval_5.requires_escalation
    print(
        f"[Caso 5 - Escalamiento con SLA Vencido P0] {eval_5.incident_id}: "
        f"elapsed={eval_5.elapsed_minutes}m / {eval_5.allowed_minutes}m | "
        f"breached={eval_5.is_breached} | escalation={eval_5.requires_escalation}"
    )

    print("\nTodos los casos de prueba finalizaron exitosamente.")


if __name__ == "__main__":
    _run_demo()
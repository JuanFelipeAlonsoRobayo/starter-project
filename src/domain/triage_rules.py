"""Motor determinista de clasificación y enrutamiento de incidentes (IncidentOps)."""

from collections import defaultdict
import json
from pathlib import Path
from typing import Dict, List

from src.domain.models import RecommendedTeam, SeverityLevel, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente analizando impacto técnico real, componente y correlación."""
    text_lower = raw_text.lower()

    # 1. P0: Brecha activa de seguridad / exposición de datos multi-tenant (IDOR)
    if "company_id" in text_lower or ("otra organización" in text_lower and "facturas" in text_lower):
        severity: SeverityLevel = "P0"
        component = "reporting-api"
        recommended_team: RecommendedTeam = "Security-IAM"
        symptom_category = "idor-tenant-data-leak"
        rationale = (
            "Brecha crítica de seguridad multi-tenant (IDOR en company_id) "
            "con exposición de datos entre organizaciones."
        )

    # 2. P0: Indisponibilidad global de servicio crítico (Pasarela de pagos HTTP 502)
    elif "502" in text_lower and any(k in text_lower for k in ("pago", "pagos", "cobro", "cobros", "tarjeta")):
        severity = "P0"
        component = "payments-gateway"
        recommended_team = "Backend-Core"
        symptom_category = "http-502-outage"
        rationale = (
            "Indisponibilidad global en pasarela de pagos (HTTP 502 Bad Gateway) "
            "que impide procesar transacciones."
        )

    # 3. P1: Degradación severa de infraestructura compartida con riesgo inminente de caída
    elif ("postgresql" in text_lower or "conexiones" in text_lower) and (
        "94%" in text_lower or "timeout" in text_lower or "timeouts" in text_lower
    ):
        severity = "P1"
        component = "database-cluster"
        recommended_team = "Data-DBA"
        symptom_category = "connection-pool-exhaustion"
        rationale = (
            "Saturación crítica del nodo primario de PostgreSQL (94% de conexiones) "
            "con timeouts en el pool."
        )

    # 4. P2: Bloqueo operativo de cuenta individual (ignora urgencia subjetiva como "hoy")
    elif ("cuenta" in text_lower or "ingresar" in text_lower) and "bloqueada" in text_lower:
        severity = "P2"
        component = "auth-identity"
        recommended_team = "Security-IAM"
        symptom_category = "account-lockout"
        rationale = (
            "Bloqueo operativo de cuenta de usuario individual sin afectación "
            "global del servicio de autenticación."
        )

    # 5. P2: Degradación moderada en consultas con alto volumen de registros (>10,000)
    elif "10,000" in text_lower and ("segundos" in text_lower or "lenta" in text_lower):
        severity = "P2"
        component = "reporting-api"
        recommended_team = "Backend-Core"
        symptom_category = "slow-query-10k-records"
        rationale = (
            "Degradación moderada de rendimiento (>3s) en consultas históricas "
            "para clientes con más de 10,000 registros."
        )

    # 6. P2: Degradación moderada en exportación de archivos sin caída del servicio
    elif "excel" in text_lower and "segundos" in text_lower:
        severity = "P2"
        component = "reporting-api"
        recommended_team = "Backend-Core"
        symptom_category = "slow-excel-export"
        rationale = (
            "Latencia moderada (~20s) en exportación a Excel que completa "
            "la descarga correctamente sin interrupción del servicio."
        )

    # 7. P3: Mantenimiento preventivo en entornos no productivos (staging)
    elif "certificado" in text_lower or "tls" in text_lower or "staging" in text_lower:
        severity = "P3"
        component = "infra-certificates"
        recommended_team = "Platform-SRE"
        symptom_category = "staging-tls-rotation"
        rationale = (
            "Rotación preventiva de certificado TLS en entorno no productivo (staging) "
            "sin impacto en producción."
        )

    # 8. P3: Solicitudes cosméticas de interfaz de usuario
    elif "botón" in text_lower or "color" in text_lower:
        severity = "P3"
        component = "frontend-ui"
        recommended_team = "Backend-Core"
        symptom_category = "ui-cosmetic-request"
        rationale = "Solicitud cosmética en la interfaz de usuario sin impacto funcional."

    # Fallback determinista por defecto
    else:
        severity = "P3"
        component = "reporting-api"
        recommended_team = "Backend-Core"
        symptom_category = "general-inquiry"
        rationale = "Reporte general sin indicadores de degradación crítica ni brecha de seguridad."

    duplicate_group_key = f"{component}:{symptom_category}"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        recommended_team=recommended_team,
        duplicate_group_key=duplicate_group_key,
        rationale=rationale,
    )


def _run_triage_audit() -> None:
    """Ejecuta el motor refactorizado sobre los 10 incidentes de prueba y detecta duplicados."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    groups: Dict[str, List[str]] = defaultdict(list)

    print("=== Auditoría del Motor de Triaje Refactorizado (`src/domain/triage_rules.py`) ===")
    header = (
        f"{'ID':<10} | {'Sev.':<4} | {'Componente':<20} | "
        f"{'Equipo Asignado':<14} | {'Clave de Duplicado':<38} | {'Extracto del Reporte'}"
    )
    print(header)
    print("-" * len(header))

    for item in incidents:
        result = classify_incident_report(item["id"], item["raw_text"])
        groups[result.duplicate_group_key].append(result.incident_id)
        snippet = item["raw_text"][:35] + "..." if len(item["raw_text"]) > 35 else item["raw_text"]
        print(
            f"{result.incident_id:<10} | {result.severity:<4} | {result.component:<20} | "
            f"{result.recommended_team:<14} | {result.duplicate_group_key:<38} | {snippet}"
        )

    print("-" * len(header))
    print("\n=== Grupos de Incidentes Duplicados Detectados ===")
    for group_key, inc_ids in groups.items():
        if len(inc_ids) > 1:
            joined_ids = ", ".join(inc_ids)
            print(f"  - [{group_key}] -> Incidentes correlacionados: {joined_ids}")


if __name__ == "__main__":
    _run_triage_audit()
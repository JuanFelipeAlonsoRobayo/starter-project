# Contrato — Auditoría de SLA

Superficie de auditoría definida por el feature (acuerdos del equipo):

- HTTP: `GET /api/v1/incidents/{incident_id}/sla`
- CLI: `sla`

Ambos invocan exactamente el caso de uso `IncidentService.evaluate_incident_sla`; los JSON son equivalentes (paridad REST/CLI).

## HTTP

- Parámetro opcional `reference_time` (ISO 8601; puede incluir zona UTC; normalizado a naive UTC).
- Response exitoso: `200 OK` con `SLAEvaluationResponse`:

| Campo | Regla |
| --- | --- |
| `incident_id` | Identificador del incidente auditado. |
| `severity` | Severidad registrada. |
| `elapsed_minutes` | Minutos transcurridos del SLA, según la política vigente (ver [Estado del SLA de un incidente](../spec.md#estado-del-sla-de-un-incidente)). |
| `allowed_minutes` | Límite de SLA de la severidad (ADR-002). |
| `remaining_minutes` | Diferencia límite menos transcurrido (puede ser negativo). |
| `is_breached` | Verdadero si `elapsed_minutes` supera `allowed_minutes`; a cualquier estado almacenado. |
| `requires_escalation` | Verdadero si el incidente no está resuelto y alcanzó el 75 % del límite (ADR-002). |

- Errores: `404 Not Found` (`INCIDENT_NOT_FOUND`) si el incidente no existe; `422` (`REFERENCE_TIME_BEFORE_CREATION`) si `reference_time < created_at`; 422 `INVALID_REFERENCE_TIME` si el valor no es ISO-8601 válido.

## CLI

```text
sla --incident-id <id> [--reference-time <ISO-8601>]
```

- stdout: JSON de `SLAEvaluationResponse` (igual al cuerpo HTTP).
- Códigos de salida: `2` + `INCIDENT_NOT_FOUND` para ID desconocido; `1` por `REFERENCE_TIME_BEFORE_CREATION` (acuerdo: 422 ↔ exit 1); `1` inesperado (`INTERNAL_ERROR`, stderr).

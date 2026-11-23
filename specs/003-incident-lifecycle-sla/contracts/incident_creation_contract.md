# Contrato — Creación de incidentes

Superficie de creación definida por el feature (acuerdos del equipo):

- HTTP: `POST /api/v1/incidents`
- CLI: `create`

Ambos invocan exactamente el caso de uso `IncidentService.create_incident`; los JSON son equivalentes (paridad REST/CLI).

## HTTP

- Request (`CreateIncidentRequest`, `extra="forbid"`):

| Campo | Regla |
| --- | --- |
| `title` | Obligatorio. Cadena no vacía ni de solo espacios. Vacío/solo espacios → 422 (`EMPTY_TITLE`). |
| `raw_text` | Obligatorio. Cadena no vacía ni de solo espacios, con el texto del reporte original. Vacío/solo espacios → 422 (`EMPTY_RAW_TEXT`). |
| `incident_id` | Opcional. Valor proporcionado o autogenerado `INC-<HEX8>` (8 hex cifras). |
| `created_at` | Opcional (ISO-8601; naive o aware → normalizado a naive UTC). Default: instante actual. |
| `status` | Opcional. Default `"OPEN"`. |

- Response exitoso: `201 Created` (HTTP) / JSON (CLI) de `IncidentCreatedResponse`:

| Campo | Regla |
| --- | --- |
| `incident_id` | Identificador del incidente creado. |
| `severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale` | Clasificación completa (resultado de `classify_incident_report`). |
| `is_duplicate` | `true` si existe al menos un incidente equivalente abierto. |
| `duplicate_of` | `list[str]` de `incident_id` de incidentes equivalentes abiertos; sin `RESOLVED` ni el propio ID del incidente nuevo. |

- Errores: 422 (`EMPTY_TITLE`/`EMPTY_RAW_TEXT`/`INVALID_CREATED_AT`/`INVALID_STATUS`); 500 (`INTERNAL_ERROR`, sobre estándar).

## CLI

```text
create --title <title> --raw-text <raw_text> [--incident-id <id>] [--created-at <ISO-8601>] [--status <OPEN|IN_PROGRESS|ESCALATION_REQUIRED|RESOLVED>]
```

- stdout: JSON de `IncidentCreatedResponse` (igual al cuerpo HTTP).
- Códigos de salida: `1` por `ValidationError` (vacíos/espacios — acuerdo del equipo); `1` inesperado (`INTERNAL_ERROR`, stderr).

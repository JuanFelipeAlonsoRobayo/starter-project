# 001 — Triage endpoint: manual de aceptación

- **Estado**: Borrador
- **Referencias**: `docs/spec.md` (contrato normativo), `docs/ROADMAP.md` (H001), `docs/adr/003-arquitectura-hexagonal.md`
- **Alcance**: verificación manual de los casos acordados para HTTP y CLI, sin persistencia.

## Contrato mínimo

- HTTP: `POST /triage` con `Content-Type: application/json` y cuerpo `{ "incident_id": "...", "raw_text": "..." }`.
- CLI: `triage --incident-id <id> --raw-text <texto>`; la salida por defecto es JSON.
- Campos de salida: `incident_id`, `severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`.
- `incident_id` vacío o `raw_text` vacío/solo espacios: HTTP `422 Unprocessable Entity`.
- Sin persistencia: no se detectan duplicados históricos; `duplicate_group_key` es una clave derivada.

## Escenario 1 — Caída crítica HTTP 502 en pasarela de pagos

```gherkin
Scenario: Caída crítica HTTP 502 en pasarela de pagos
  Given un reporte con incident_id "INC-1000" y raw_text "La pasarela de pagos devuelve 502 al intentar cobrar con tarjeta"
  When se envía POST /triage con ese reporte
  Then responde 200
  And severity es "P0"
  And component es "payments-gateway"
  And recommended_team es "Backend-Core"
  And duplicate_group_key es "payments-gateway:http-502-outage"
```

## Escenario 2 — Cuenta individual bloqueada mencionando "hoy"

```gherkin
Scenario: Cuenta individual bloqueada mencionando "hoy"
  Given un reporte con incident_id "INC-1002" y raw_text "Mi cuenta está bloqueada y necesito ingresar hoy"
  When se envía POST /triage con ese reporte
  Then responde 200
  And severity es "P2"
  And component es "auth-identity"
  And recommended_team es "Security-IAM"
  And duplicate_group_key es "auth-identity:account-lockout"
  And severity no es "P0"
```

## Escenario 3 — Entradas vacías o con solo espacios

```gherkin
Scenario Outline: Entradas vacías o con solo espacios
  Given un reporte con incident_id "<incident_id>" y raw_text "<raw_text>"
  When se envía POST /triage con ese reporte
  Then responde 422 Unprocessable Entity
  And error.code es "<error_code>"

  Examples:
    | incident_id | raw_text | error_code        |
    | INC-1003    | " "      | EMPTY_RAW_TEXT    |
    | ""          | "La pasarela de pagos devuelve 502" | EMPTY_INCIDENT_ID |
```

## Escenario 4 — Paridad del CLI

```gherkin
Scenario: Paridad del CLI
  Given el comando triage --incident-id INC-1001 --raw-text "La pasarela de pagos devuelve 502 al intentar cobrar con tarjeta"
  When se ejecuta el CLI
  Then el código de salida es 0
  And stdout es un JSON válido
  And severity es "P0"
  And component es "payments-gateway"
  And recommended_team es "Backend-Core"
  And duplicate_group_key es "payments-gateway:http-502-outage"
```

## Verificación manual

1. HTTP: enviar cada cuerpo a `POST /triage` y comprobar estado, campos y clave de duplicado.
2. CLI: ejecutar el comando indicado y validar que stdout sea JSON parseable con los mismos campos que HTTP.
3. Vacíos: confirmar `422 Unprocessable Entity` y que el mensaje de error no repita el texto recibido.
4. Repetir una misma entrada y confirmar que la salida no cambia: no hay estado ni persistencia.

# Especificación H001 — Triaje multi-interfaz

- **Estado**: Borrador
- **Hito**: H001 — Triaje multi-interfaz
- **Referencias**: `docs/ROADMAP.md`, `docs/adr/003-arquitectura-hexagonal.md`, `docs/constitution.md`
- **Objetivo**: exponer el triaje determinista de reportes mediante HTTP (frontend) y CLI (soporte), sin persistencia.

## 1. Alcance

Incluye:

- Un caso de uso de triaje compartido por ambos adaptadores.
- Contrato HTTP para clasificar un reporte y devolver su enrutamiento.
- Contrato CLI para clasificar un reporte desde terminal.
- Validación, errores y casos borde definidos en esta especificación.

Fuera de alcance de H001:

- Persistencia, historial o detección real de duplicados.
- Alertas, ciclo de vida, SLA y auditoría temporal.
- Autenticación, autorización, cuotas o rate limiting.
- Procesamiento por lote, UI, MCP o versión explícita del motor de reglas.
- Metadatos del reporte distintos de `incident_id` y `raw_text`.

## 2. Arquitectura esperada

Según ADR-003:

- `src/domain/`: reglas de triaje y resultado tipado; sin IO ni frameworks.
- `src/application/`: caso de uso compartido de triaje; sin FastAPI ni Typer.
- `src/adapters/inbound/`: adaptador HTTP con FastAPI/Pydantic v2 y adaptador CLI con Typer.
- H001 no requiere adaptador de salida: no hay persistencia.

Los adaptadores solo validan, traducen y presentan. No reimplementan reglas ni calculan severidad, componente, equipo o clave de duplicado.

## 3. Contrato de entrada

### 3.1 HTTP

- Método y ruta: `POST /triage`.
- `Content-Type`: `application/json` en UTF-8.
- Cuerpo:

```json
{
  "incident_id": "INC-001",
  "raw_text": "El endpoint permite ver company_id de otra organización"
}
```

Campos:

| Campo | Tipo | Obligatorio | Regla |
| --- | --- | --- | --- |
| `incident_id` | string | Sí | Debe ser no vacío; se ecoa sin validar formato, longitud ni unicidad. |
| `raw_text` | string | Sí | Se recorta (`strip`) y debe tener entre 1 y 10 000 caracteres; vacío o solo espacios se rechaza con 422. |

- No se aceptan campos adicionales: un campo desconocido invalida la petición.
- La longitud se mide en caracteres Unicode (code points) después de recortar.
- Solo se admite JSON; otros tipos de contenido se rechazan.

### 3.2 CLI

Comando lógico:

```text
triage --incident-id <id> --raw-text <texto> [--human]
```

- `--incident-id` es obligatorio y no puede estar vacío.
- `--raw-text` es obligatorio y no puede estar vacío ni contener solo espacios.
- La salida por defecto es JSON, con el mismo objeto que devuelve HTTP.
- `--human` es opcional y presenta una salida legible para soporte.
- El CLI invoca el caso de uso en proceso: no requiere el servidor HTTP.
- La forma exacta de invocación desde el repositorio se documentará en `AGENTS.md` al implementar; el contrato es el nombre `triage` y sus argumentos.

## 4. Contrato de salida

La respuesta HTTP y la salida por defecto del CLI comparten el mismo objeto:

```json
{
  "incident_id": "INC-001",
  "severity": "P0",
  "component": "reporting-api",
  "recommended_team": "Security-IAM",
  "duplicate_group_key": "reporting-api:idor-tenant-data-leak",
  "rationale": "Brecha crítica de seguridad multi-tenant (IDOR en company_id) con exposición de datos entre organizaciones."
}
```

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `incident_id` | string | Eco del identificador recibido. |
| `severity` | `P0` \| `P1` \| `P2` \| `P3` | Severidad determinada por la primera regla coincidente. |
| `component` | string | Componente inferido por la regla. |
| `recommended_team` | `Backend-Core` \| `Platform-SRE` \| `Data-DBA` \| `Security-IAM` | Equipo de enrutamiento. |
| `duplicate_group_key` | string | Clave derivada con formato `<component>:<symptom_category>`. No implica comparación con otros incidentes. |
| `rationale` | string | Explicación descriptiva en español; no es un identificador estable. |

No se exponen `consistency_ratio`, `status` ni versión de reglas en H001.

### 4.1 Salida legible del CLI

Con `--human`, el CLI muestra los campos con etiquetas:

```text
Incidente: INC-001
Severidad: P0
Componente: reporting-api
Equipo: Security-IAM
Clave de duplicado: reporting-api:idor-tenant-data-leak
Motivo: Brecha crítica de seguridad multi-tenant (IDOR en company_id) con exposición de datos entre organizaciones.
```

El formato exacto de alineación no es contractual; los campos y valores sí.

## 5. Reglas y precedencia

La clasificación se evalúa en el orden de la tabla. La primera regla coincidente gana; si ninguna coincide, aplica el fallback.

La comparación es por subcadena sobre `raw_text` en minúsculas, sin tokenización, sin límites de palabra y sin normalización de acentos.

| Orden | Señal en `raw_text` (sin distinguir mayúsculas) | Severidad | Componente | Equipo | `symptom_category` |
| --- | --- | --- | --- | --- | --- |
| 1 | `company_id` o (`otra organización` y `facturas`) | P0 | `reporting-api` | `Security-IAM` | `idor-tenant-data-leak` |
| 2 | `502` y (`pago`, `pagos`, `cobro`, `cobros` o `tarjeta`) | P0 | `payments-gateway` | `Backend-Core` | `http-502-outage` |
| 3 | (`postgresql` o `conexiones`) y (`94%`, `timeout` o `timeouts`) | P1 | `database-cluster` | `Data-DBA` | `connection-pool-exhaustion` |
| 4 | (`cuenta` o `ingresar`) y `bloqueada` | P2 | `auth-identity` | `Security-IAM` | `account-lockout` |
| 5 | `10,000` y (`segundos` o `lenta`) | P2 | `reporting-api` | `Backend-Core` | `slow-query-10k-records` |
| 6 | `excel` y `segundos` | P2 | `reporting-api` | `Backend-Core` | `slow-excel-export` |
| 7 | `certificado`, `tls` o `staging` | P3 | `infra-certificates` | `Platform-SRE` | `staging-tls-rotation` |
| 8 | `botón` o `color` | P3 | `frontend-ui` | `Backend-Core` | `ui-cosmetic-request` |
| Fallback | Ninguna señal anterior | P3 | `reporting-api` | `Backend-Core` | `general-inquiry` |

Esta tabla es contractual para H001. Cualquier cambio exige actualizar el dominio, esta especificación y sus escenarios BDD en el mismo cambio.

## 6. Errores HTTP

Todos los errores del endpoint usan este sobre:

```json
{
  "error": {
    "code": "EMPTY_RAW_TEXT",
    "message": "raw_text no puede estar vacío."
  }
}
```

- `code` es estable y apto para lógica del cliente.
- `message` es descriptivo, en español y no incluye `raw_text`.
- Los mensajes no se consideran contrato estable.

| HTTP | `code` | Causa |
| --- | --- | --- |
| 200 | — | Clasificación exitosa. |
| 422 | `EMPTY_RAW_TEXT` | `raw_text` vacío o solo espacios tras recortar. |
| 422 | `EMPTY_INCIDENT_ID` | `incident_id` vacío. |
| 400 | `RAW_TEXT_TOO_LONG` | `raw_text` supera 10 000 caracteres tras recortar. |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | El cuerpo no es `application/json`. |
| 422 | `INVALID_REQUEST` | JSON malformado, campo obligatorio ausente, tipo incorrecto o campo desconocido. |
| 500 | `INTERNAL_ERROR` | Fallo inesperado; no se filtra detalle interno. |

No se define autenticación en H001: el servicio es de uso interno. CORS permanece deshabilitado por defecto; si el frontend se sirve desde otro origen, se configura una allowlist explícita, nunca `*`.

## 7. Errores y salida del CLI

- Éxito, incluida una clasificación P0: código de salida `0`.
- Entrada inválida o uso incorrecto (vacío, demasiado largo, argumentos faltantes): código `2`, mensaje en `stderr`, sin clasificación.
- Fallo inesperado: código `1`, mensaje en `stderr`.
- En la salida JSON (por defecto), los errores se emiten en `stderr` con el mismo sobre `{error:{code,message}}`.
- Los errores nunca incluyen el `raw_text` recibido.

## 8. Casos borde

- `raw_text` vacío o solo espacios: rechazo 422; no se aplica el fallback P3.
- `incident_id` vacío: rechazo 422.
- `raw_text` de 10 001 caracteres o más: rechazo 400.
- Texto no reconocido: fallback P3 `general-inquiry`.
- Texto que activa varias reglas: gana la de menor número en la tabla.
- Mayúsculas y minúsculas: no afectan la coincidencia.
- Acentos: no se normalizan; `boton` no activa la regla de `botón`.
- `incident_id` ausente, vacío o de tipo distinto de string: rechazo por esquema o validación.
- `incident_id` repetido: no se detecta ni rechaza; no hay estado.
- Llamadas repetidas con la misma entrada: producen la misma salida.
- Reiniciar el servicio o el CLI no altera resultados: no hay persistencia ni caché.

## 9. Privacidad y observabilidad

- `raw_text` no se registra en logs, trazas ni mensajes de error, en ningún nivel.
- Se permite registrar `incident_id`, severidad, componente, equipo, duración y código de error.
- No se persisten reportes ni resultados en disco, base de datos o caché.
- `duplicate_group_key` es solo una clave derivada; no se compara con historial.

## 10. Escenarios BDD

```gherkin
Feature: Triaje determinista por HTTP y CLI

  Scenario: HTTP clasifica una brecha IDOR como P0
    Given un reporte con incident_id "INC-001" y raw_text "El endpoint permite ver company_id de otra organización"
    When se envía POST /triage con ese reporte
    Then responde 200
    And severity es "P0"
    And component es "reporting-api"
    And recommended_team es "Security-IAM"
    And duplicate_group_key es "reporting-api:idor-tenant-data-leak"
    And incident_id es "INC-001"

  Scenario: La clasificación no distingue mayúsculas
    Given un reporte con raw_text "COMPANY_ID expuesto entre organizaciones"
    When se envía POST /triage con ese reporte
    Then responde 200
    And severity es "P0"
    And component es "reporting-api"

  Scenario: La primera regla coincidente gana
    Given un reporte con raw_text "company_id expuesto y la pasarela de pagos devuelve 502 al cobrar con tarjeta"
    When se envía POST /triage con ese reporte
    Then responde 200
    And severity es "P0"
    And component es "reporting-api"
    And recommended_team es "Security-IAM"

  Scenario: Un texto no reconocido cae en P3 general
    Given un reporte con raw_text "El equipo solicita una demostración del producto"
    When se envía POST /triage con ese reporte
    Then responde 200
    And severity es "P3"
    And component es "reporting-api"
    And recommended_team es "Backend-Core"
    And duplicate_group_key es "reporting-api:general-inquiry"

  Scenario: HTTP rechaza un texto vacío
    Given un reporte con raw_text "   "
    When se envía POST /triage con ese reporte
    Then responde 422 Unprocessable Entity
    And error.code es "EMPTY_RAW_TEXT"
    And la respuesta no contiene el raw_text

  Scenario: HTTP rechaza un incident_id vacío
    Given un reporte con incident_id "" y raw_text "La pasarela de pagos devuelve 502"
    When se envía POST /triage con ese reporte
    Then responde 422 Unprocessable Entity
    And error.code es "EMPTY_INCIDENT_ID"

  Scenario: HTTP rechaza un texto demasiado largo
    Given un reporte con raw_text de 10001 caracteres
    When se envía POST /triage con ese reporte
    Then responde 400
    And error.code es "RAW_TEXT_TOO_LONG"

  Scenario: HTTP rechaza un payload inválido
    Given un cuerpo JSON sin raw_text
    When se envía POST /triage con ese cuerpo
    Then responde 422
    And error.code es "INVALID_REQUEST"

  Scenario: El CLI emite JSON por defecto con paridad respecto de HTTP
    Given el comando triage --incident-id "INC-003" --raw-text "La pasarela de pagos devuelve 502"
    When se ejecuta el CLI
    Then el código de salida es 0
    And stdout es un objeto JSON con incident_id, severity, component, recommended_team, duplicate_group_key y rationale
    And severity es "P0"
    And recommended_team es "Backend-Core"

  Scenario: El CLI presenta una salida legible con --human
    Given el comando triage --incident-id "INC-002" --raw-text "El botón de guardar cambió de color" --human
    When se ejecuta el CLI
    Then el código de salida es 0
    And stdout muestra severidad "P3", componente "frontend-ui" y equipo "Backend-Core"

  Scenario: El CLI rechaza una entrada vacía
    Given el comando triage --incident-id "INC-004" --raw-text ""
    When se ejecuta el CLI
    Then el código de salida es 2
    And stderr contiene un mensaje de validación
    And no se emite clasificación

  Scenario: No hay estado entre llamadas
    Given el mismo reporte enviado dos veces
    When se envían ambas solicitudes
    Then ambas respuestas son idénticas
    And no se crea historial ni detección de duplicados

  Scenario: Los logs no exponen el texto del reporte
    Given un reporte con un raw_text sensible
    When se procesa la solicitud
    Then ningún registro de log contiene ese raw_text
```

## 11. Pruebas de aceptación

- Cada escenario BDD tendrá al menos una prueba automatizada con `pytest`.
- Las pruebas HTTP usan el cliente de pruebas de FastAPI, sin abrir red ni requerir un servidor externo.
- Las pruebas CLI invocan el comando en proceso y verifican stdout, stderr y código de salida.
- No se requiere base de datos, archivos temporales ni servicios externos.
- Los casos de error verifican también que `raw_text` no aparezca en la respuesta ni en los logs.

## 12. Criterios de terminado

- Todos los escenarios BDD pasan con `pytest`.
- HTTP y CLI producen el mismo resultado para la misma entrada.
- La misma entrada produce siempre la misma salida.
- No se escribe en disco, base de datos ni caché.
- `raw_text` no aparece en logs ni en errores.
- Las reglas permanecen en el dominio y los adaptadores no las duplican.

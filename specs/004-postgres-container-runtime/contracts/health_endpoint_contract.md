# Contrato — Chequeo de salud de conectividad

Origen: `specs/004-postgres-container-runtime/spec.md` (RNF-002; Escenarios BDD 1–2). Referencia: `specs/002-active-incident-summary/contracts/incident_repository_port.md`.

El chequeo de salud verifica **conectividad real**: ejecuta `SELECT 1` sobre la base de datos configurada en cada petición (per `src/adapters/outbound/sqlite_repository.py:151` y per R3; el driver `psycopg[binary]` ejecuta `SELECT 1` de forma real en `PostgresIncidentRepository.check_health()`).

## HTTP — `GET /health` (adaptante primario HTTP)

| Aspecto | Contrato |
| --- | --- |
| Llamada | `GET /health` — sin body, sin headers requeridos. |
| 200 (OK) | `200 OK`, body: `{"status": "ok", "database": "connected"}`. |
| 503 (fallo) | `503 Service Unavailable`, body: `{"status": "error", "database": "unavailable"}`. |
| Semántica | Éxito ⇔ `check_health()` retorna `True` en el adaptante saliente. Cada petición ejecuta el chequeo vivo; sin caché. |

## CLI — `health` (adaptante primario CLI)

| Aspecto | Contrato |
| --- | --- |
| Llamada | `cli health`. |
| Salida (OK) | JSON: `{"status": "ok", "database": "connected"}`, exit 0. |
| Salida (fallo) | JSON: `{"status": "error", "database": "unavailable"}`, exit 1. |

## Nota de diseño

El contrato HTTP/CLI es el mismo (`status`/`database`); el endpoint se usa por despliegues en contenedores (healthcheck de `docker-compose.yml`) y la salida CLI por operadores (Spec: "exponer un chequeo real de salud de conectividad", respuesta C — endpoint HTTP + comando CLI con el mismo contrato).

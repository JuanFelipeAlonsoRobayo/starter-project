# Plan técnico — Hito 001: Triaje multi-interfaz con Arquitectura Hexagonal

- **Estado**: Implementado
- **Referencias**: `docs/constitution.md`, `docs/adr/003-arquitectura-hexagonal.md`, `docs/spec.md`, `specs/001-triage-endpoint-manual.md`
- **Alcance**: primer corte de la Arquitectura Hexagonal para el triaje determinista por HTTP y CLI, sin persistencia.
- **Fuera de alcance**: persistencia, duplicados históricos, SLA, autenticación, MCP y contenedores.

## Objetivo

Separar el núcleo determinista de triaje de sus interfaces, de modo que HTTP y CLI compartan el mismo caso de uso y las reglas permanezcan en el dominio. Los adaptadores solo validan, traducen y presentan; no reimplementan severidad, componente, equipo ni clave de duplicado.

## Dirección de dependencias

```text
adapters/inbound  →  application  →  domain
```

- `domain`: modelos, triaje y política de SLA; sin IO ni frameworks.
- `application`: caso de uso `IncidentService` y `ValidationError`; sin FastAPI ni Typer.
- `adapters/inbound`: FastAPI/Pydantic v2 y Typer como adaptadores delgados.
- H001 no requiere adaptadores de salida porque no hay persistencia.

## Estructura objetivo

```text
src/
  domain/
    __init__.py
    models.py
    triage_rules.py
    sla_calculator.py
  application/
    __init__.py
    services.py
  adapters/
    __init__.py
    inbound/
      __init__.py
      cli.py
      api/
        __init__.py
        schemas.py
        app.py
tests/
  conftest.py
  test_spec_001_triage.py
```

## Decisiones de diseño

- `ValidationError` expone `code` y `message`; no conoce HTTP. El adaptador HTTP mapea `EMPTY_INCIDENT_ID` y `EMPTY_RAW_TEXT` a 422, y `RAW_TEXT_TOO_LONG` a 400. El CLI mapea cualquier error de validación a código de salida 2.
- `IncidentService.triage_incident` recorta `raw_text` antes de validar y clasificar. `incident_id` vacío o solo espacios produce `EMPTY_INCIDENT_ID`.
- La respuesta HTTP y la salida JSON del CLI exponen solo los seis campos contractuales; se omite `consistency_ratio`.
- `triage_rules.py` conserva su demostración `__main__`, pero la ruta a `data/sample_incidents.json` se corrige a la raíz real del repositorio mediante `Path(__file__).resolve().parents[2]`.
- Los módulos heredados de `src/*.py` se mueven a `src/domain/`; las rutas antiguas dejan de existir y todas las importaciones se actualizan.
- `create_app()` permite instanciar la aplicación en pruebas; además se expone `app = create_app()` para Uvicorn.

## Tareas atómicas ordenadas

### 0. Baseline

- [x] Ejecutar `uv run python -m src.sla_calculator` y `uv run python -m src.triage_rules`; registrar la salida esperada antes de migrar.

### 1. Dependencias y configuración de pruebas

- [x] Añadir dependencias runtime con `uv add fastapi uvicorn pydantic typer`.
- [x] Añadir dependencias de desarrollo con `uv add --dev pytest httpx`.
- [x] Añadir en `pyproject.toml`:

  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["."]
  testpaths = ["tests"]
  ```

### 2. Migración del núcleo puro a `src/domain/`

- [x] Crear `src/domain/__init__.py`, `src/application/__init__.py`, `src/adapters/__init__.py`, `src/adapters/inbound/__init__.py` y `src/adapters/inbound/api/__init__.py`.
- [x] Mover `src/models.py` a `src/domain/models.py` con `git mv`; sin cambios de contenido.
- [x] Mover `src/triage_rules.py` a `src/domain/triage_rules.py`; cambiar el import a `src.domain.models` y ajustar `PROJECT_ROOT` a `Path(__file__).resolve().parents[2]`.
- [x] Mover `src/sla_calculator.py` a `src/domain/sla_calculator.py`; cambiar el import a `src.domain.models`.
- [x] Actualizar `src/incident_repository.py` para importar desde `src.domain.models` y `src.domain.sla_calculator`.
- [x] Verificar con `uv run python -m src.domain.sla_calculator`, `uv run python -m src.domain.triage_rules` y `uv run python -m src.incident_repository --records 100 --iterations 2`.

### 3. Caso de uso compartido

- [x] Crear `src/application/services.py` con `ValidationError` y `IncidentService.triage_incident(incident_id, raw_text)`.
- [x] Validar `incident_id` vacío o solo espacios, `raw_text` vacío tras `strip` y `raw_text` de más de 10 000 caracteres tras `strip`.
- [x] Delegar la clasificación en `classify_incident_report` del dominio; no importar FastAPI, Typer ni Pydantic en esta capa.

### 4. Adaptador primario HTTP

- [x] Crear `src/adapters/inbound/api/schemas.py` con `TriageRequest` (`extra="forbid"`), `TriageResponse` con los seis campos contractuales y los modelos del sobre de error.
- [x] Crear `src/adapters/inbound/api/app.py` con `create_app()` e implementar `POST /triage`.
- [x] Mapear `ValidationError` al sobre `{"error": {"code": "...", "message": "..."}}` y al estado HTTP correspondiente.
- [x] Añadir handlers para `RequestValidationError` (422 `INVALID_REQUEST`), content-type no JSON (415 `UNSUPPORTED_MEDIA_TYPE`) y fallo inesperado (500 `INTERNAL_ERROR`).
- [x] Exponer `app = create_app()` para Uvicorn y verificar la importación del adaptador.

### 5. Adaptador primario CLI

- [x] Crear `src/adapters/inbound/cli.py` con una aplicación Typer y el subcomando `triage`.
- [x] Soportar `--incident-id`, `--raw-text` y `--human`; la salida por defecto debe ser JSON con los mismos campos que HTTP.
- [x] Delegar en `IncidentService`; en `ValidationError`, escribir el sobre de error en `stderr` y salir con código 2; en fallo inesperado, salir con código 1.
- [x] Verificar manualmente el caso P0, el caso vacío y que stdout sea JSON parseable.

### 6. Pruebas de aceptación BDD

- [x] Crear `tests/conftest.py` con fixtures `api_client` (`TestClient(create_app())`) y `cli_runner` (`CliRunner()`).
- [x] Crear `tests/test_spec_001_triage.py` con los cuatro escenarios de `specs/001-triage-endpoint-manual.md`:
  - [x] HTTP 502 en pagos → 200, P0, `payments-gateway`, `Backend-Core`, `payments-gateway:http-502-outage`.
  - [x] HTTP cuenta bloqueada mencionando “hoy” → 200, P2, `auth-identity`, `Security-IAM`, `auth-identity:account-lockout`, severidad distinta de P0.
  - [x] HTTP parametrizado de entradas vacías: `raw_text=" "` → 422 `EMPTY_RAW_TEXT`; `incident_id=""` → 422 `EMPTY_INCIDENT_ID`; la respuesta no repite `raw_text`.
  - [x] CLI `INC-1001` → código 0, stdout JSON válido y paridad de campos con HTTP.
- [x] Ejecutar `uv run pytest -q` y dejar los cuatro escenarios en verde.

### 7. Documentación y verificación final

- [x] Actualizar `AGENTS.md`: nuevas rutas de módulos, comandos con `src.domain.*`, comando del CLI, `uv run pytest`, dependencias y eliminación de la afirmación de que no existe test runner.
- [x] Ejecutar la verificación final: SLA, auditoría de triaje, smoke del repositorio, pytest y CLI.
- [x] Revisar `git status` y el diff para confirmar que no se modificaron reglas de negocio ni se añadió persistencia.

### 8. Tarea recomendada fuera de los cinco puntos

- [x] Ajustar `src/context_audit.py` para escanear `src/**/*.py`; actualmente solo mira `src/*.py` y dejaría fuera `domain/`, `application/` y `adapters/`.

## Criterios de terminado

- Los cuatro escenarios de `specs/001-triage-endpoint-manual.md` pasan con `pytest`.
- HTTP y CLI producen el mismo resultado para la misma entrada.
- La misma entrada produce siempre la misma salida.
- Las reglas permanecen en `src/domain/` y ningún adaptador las duplica.
- No se escribe en disco, base de datos ni caché durante el triaje.
- `raw_text` no aparece en respuestas de error ni en logs.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| `src/context_audit.py` deja de ver el núcleo movido por escanear solo `src/*.py`. | Ejecutar la tarea 8 o documentar la limitación en `AGENTS.md`. |
| `src/incident_repository.py` rompe imports al mover el dominio. | Actualizar sus imports en la tarea 2 y ejecutar el smoke del repositorio. |
| La demo `__main__` de `triage_rules.py` lee JSON dentro del dominio. | Mantener pura la función de clasificación; el IO queda confinado a la demo. |
| Divergencia entre el contrato de `docs/spec.md` y los cuatro escenarios de `specs/001`. | Implementar los cuatro escenarios solicitados y dejar el resto como ampliación posterior. |
| Errores de validación con códigos inconsistentes entre HTTP y CLI. | Centralizar la validación en `IncidentService` y mapear códigos en cada adaptador. |

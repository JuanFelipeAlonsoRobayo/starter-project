---
name: bdd-acceptance
description: Guía la redacción de especificaciones BDD (Given / When / Then) y su traducción 1:1 a pruebas automatizadas con pytest en IncidentOps. Úsala al escribir o actualizar escenarios en spec.md o specs/*.md, y al implementar pruebas de aceptación en tests/.
---

# BDD y pruebas de aceptación en IncidentOps

Reglas para escribir escenarios legibles por negocio y convertirlos en pruebas
ejecutables sin pérdida de trazabilidad. Base normativa:
`.specify/memory/constitution.md` (principio V) y `docs/spec.md` §10–§12.

## Cuándo activar esta skill

- Redactar o modificar escenarios en `docs/spec.md` o `specs/*.md`.
- Implementar o actualizar pruebas de aceptación en `tests/`.
- Revisar que un escenario y su prueba sigan siendo el mismo contrato.

## 1. Redactar escenarios (estilo Dan North)

### Formato obligatorio

```gherkin
Feature: <capacidad observable en lenguaje de negocio>

  Scenario: <resultado único y verificable>
    Given <contexto inicial>
    And <más contexto, si aplica>
    When <un único evento>
    Then <resultado observable>
    And <otro resultado observable>
```

- `Given` describe el estado del mundo, no acciones del sistema.
- `When` contiene **un solo** evento. Si necesitas dos, son dos escenarios.
- `Then` afirma resultados observables por el negocio, con valores exactos.
- `And` continúa la cláusula anterior; no introduce una nueva fase.
- Usa `Scenario Outline` + `Examples` solo cuando el mismo comportamiento se
  repite con distintos datos (por ejemplo, entradas inválidas):

  ```gherkin
  Scenario Outline: El sistema rechaza reportes incompletos
    Given un reporte con incident_id "<incident_id>" y raw_text "<raw_text>"
    When se solicita el triaje
    Then se rechaza con el código "<error_code>"

    Examples:
      | incident_id | raw_text | error_code        |
      | INC-1003    | " "      | EMPTY_RAW_TEXT    |
      | ""          | "texto"  | EMPTY_INCIDENT_ID |
  ```

### Vocabulario ubicuo, no implementación

El escenario lo lee negocio y soporte; no debe revelar cómo está construido el
sistema.

| Sí (negocio) | No (implementación) |
| --- | --- |
| incidente, reporte, severidad, componente | `Incident`, `TriageResult`, `classify_incident_report` |
| equipo responsable, escalamiento, SLA, duplicado | `SLA_POLICY_TABLE`, `_calculate_business_minutes` |
| "el sistema clasifica el reporte como P0" | "el servicio llama a la regla 3" |
| "responde 200 con severity P0" | "el router ejecuta `IncidentService.triage_incident`" |
| "el reporte no se repite en la respuesta" | "la columna `raw_text` no se serializa" |

- Prohibido nombrar clases Python, funciones internas, módulos, fixtures,
  tablas/columnas SQL o detalles de infraestructura.
- El contrato público sí es vocabulario de negocio: `POST /triage`, `severity`,
  `recommended_team`, códigos de error y códigos de salida del CLI.
- Describe el qué, no el cómo: "el sistema rechaza..." en lugar de "el adaptador
  valida con Pydantic...".

### Un escenario, un comportamiento

- Un único resultado verificable por escenario; si el título necesita "y",
  probablemente son dos escenarios.
- Sin ambigüedad: valores concretos, límites explícitos, sin "rápido", "pronto",
  "adecuado" ni "correcto".
- Si el comportamiento depende del tiempo (SLA), fija el instante de referencia
  en el `Given`.
- Nombra el escenario por su resultado: `Scenario: El CLI rechaza una entrada
  vacía`, no `Scenario: Prueba del CLI`.

### Dónde vive cada escenario

- `docs/spec.md` §10: escenarios del hito vigente, en un bloque `gherkin`.
- `specs/NNN-<slug>.md`: escenarios del manual de aceptación de esa spec.
- El título del escenario es un identificador estable: si cambia, se actualizan
  en el mismo cambio la spec y el docstring de su prueba.

## 2. Traducir cada escenario a una prueba 1:1

### Correspondencia exacta

- Cada escenario produce **exactamente una** función `test_bdd_*` en `tests/`.
- Un `Scenario Outline` produce **una** función parametrizada: cada fila de
  `Examples` es un caso de la misma prueba, no una prueba nueva.
- El docstring cita el escenario y su spec:

  ```python
  def test_bdd_cli_parity_with_http(
      api_client: TestClient,
      cli_runner: CliRunner,
  ) -> None:
      """Escenario 4 — Paridad del CLI (specs/001-triage-endpoint-manual.md)."""
  ```

- El nombre de archivo refleja la spec: `tests/test_spec_001_triage.py` para
  `specs/001-triage-endpoint-manual.md`.
- Si una prueba existente no sigue el prefijo `test_bdd_`, renómbrala cuando
  toques su escenario.

### Ejercer los adaptadores en proceso

- HTTP: `TestClient` de FastAPI sobre la app creada en la prueba o vía la fixture
  `api_client` de `tests/conftest.py`. Nunca levantes `uvicorn` ni uses red.
- CLI: `CliRunner` de Typer con `cli_runner.invoke(app, [...])`. Nunca uses
  `subprocess` ni un binario instalado.
- Verifica `exit_code`, `stdout` y `stderr`; para JSON, `json.loads(...)`.
- Paridad: cuando el escenario lo declare, envía la misma entrada por HTTP y CLI
  y compara el cuerpo JSON con el objeto emitido por el CLI. Si el escenario es
  de una sola interfaz, no fuerces una comparación que no afirma.

```python
def test_bdd_cli_parity_with_http(
    api_client: TestClient,
    cli_runner: CliRunner,
) -> None:
    """Escenario 4 — Paridad del CLI (specs/001-triage-endpoint-manual.md)."""
    payload = {"incident_id": "INC-1001", "raw_text": "La pasarela devuelve 502"}

    cli_result = cli_runner.invoke(
        cli_app,
        [
            "triage",
            "--incident-id",
            payload["incident_id"],
            "--raw-text",
            payload["raw_text"],
        ],
    )
    assert cli_result.exit_code == 0

    http_response = api_client.post("/triage", json=payload)
    assert http_response.status_code == 200
    assert json.loads(cli_result.stdout) == http_response.json()
```

### Aislamiento total

- Sin estado compartido: cada prueba construye su propio cliente y su propio
  runner; no dependas del orden de ejecución.
- Sin persistencia real: usa SQLite en memoria (`:memory:`) o `tmp_path` cuando
  exista almacenamiento; nunca la base del repositorio.
- Sin archivos reales del repositorio: no leas `data/sample_incidents.json` ni
  documentos; usa literales de la prueba o `tmp_path`.
- Sin red externa, sin `sleep`, sin variables de entorno mutadas globalmente.
- Cada prueba debe pasar sola: `uv run pytest -q tests/test_spec_001_triage.py::test_bdd_...`.

### Afirmar lo que el escenario dice

- Verifica exactamente los resultados del `Then`, con sus valores.
- Cuando el escenario enumere el contrato de salida, compara el conjunto de
  claves; no añadas aserciones sobre campos que el escenario no menciona.
- En errores, comprueba código y mensaje observable, y que el `raw_text` no se
  repita en la respuesta.
- No uses `skip`, `xfail` ni aserciones condicionales para dejar la suite verde.

## 3. Verificación obligatoria

```bash
uv run pytest -q
```

Debe pasar completo antes de dar una tarea por terminada. Para depurar un
escenario concreto: `uv run pytest -q tests/test_spec_001_triage.py -k bdd`.

Si el escenario cambia, su prueba cambia en el mismo commit; si la prueba cambia
sin que cambie el escenario, revisa si estás ocultando una regresión.

## Checklist antes de cerrar

- [ ] Cada escenario usa `Given / When / Then`, con un solo `When`.
- [ ] El vocabulario es de negocio: sin clases, funciones internas ni SQL.
- [ ] Cada escenario tiene exactamente una función `test_bdd_*`.
- [ ] El docstring cita escenario y archivo de spec.
- [ ] HTTP se ejerce con `TestClient` y CLI con `CliRunner`, en proceso.
- [ ] La paridad se verifica donde el escenario la declara.
- [ ] La prueba es aislada: sin red, sin estado compartido, sin archivos reales.
- [ ] `uv run pytest -q` pasa completo.

## Errores comunes

- **Un escenario con dos `When`**: divídelo en dos escenarios y dos pruebas.
- **Escenario que nombra `classify_incident_report` o una tabla SQL**: reescribe
  el resultado en términos de severidad, equipo o SLA.
- **Una prueba por aserción**: la unidad es el escenario, no el `assert`.
- **Compartir un `TestClient` o una base entre pruebas**: crea el cliente en la
  fixture y la base en `tmp_path`/`:memory:`.
- **Probar el CLI con `subprocess` o el HTTP con un servidor real**: usa las
  fixtures en proceso.
- **`Scenario Outline` con una prueba por fila**: parametriza una sola función.
- **Docstring que copia el nombre del test en vez del escenario**: cita el título
  exacto de la spec para mantener la trazabilidad.

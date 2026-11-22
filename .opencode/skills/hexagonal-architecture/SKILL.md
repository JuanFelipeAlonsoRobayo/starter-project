---
name: hexagonal-architecture
description: Define y valida las reglas de Arquitectura Hexagonal (puertos y adaptadores) de IncidentOps. Úsala al crear o modificar módulos en src/domain/, src/application/ o src/adapters/, al añadir puertos, adaptadores o dependencias, y antes de dar por terminada cualquier tarea que toque esas capas.
---

# Arquitectura Hexagonal en IncidentOps

Reglas de dependencia, paridad entre adaptadores y verificación estática del
proyecto. Base normativa: `.specify/memory/constitution.md` (principios I, II y IV)
y `docs/adr/003-arquitectura-hexagonal.md`.

## Cuándo activar esta skill

- Crear, mover o modificar archivos en `src/domain/`, `src/application/` o
  `src/adapters/`.
- Añadir un puerto, un adaptador, un caso de uso o una dependencia nueva.
- Cambiar el contrato de salida o el manejo de errores de REST/CLI.
- Revisar un cambio antes de cerrarlo: la puerta `uv run ruff check src/` debe
  pasar sin errores.

## Dirección de dependencias

```text
src/adapters/inbound/  ──▶  src/application/  ──▶  src/domain/
        │                        ▲
        │                        │ implementa puertos
        └──▶ src/adapters/outbound/ (factory)
```

El dominio no conoce a nadie. La aplicación define puertos y no conoce
adaptadores. Los adaptadores entrantes conocen la aplicación; los salientes
implementan sus puertos.

## Reglas por capa

| Capa | Puede importar | Tiene prohibido importar |
| --- | --- | --- |
| `src/domain/` | solo biblioteca estándar pura | frameworks, HTTP, BD/ORM, `src.application`, `src.adapters` |
| `src/application/` | biblioteca estándar + `src.domain` | frameworks, HTTP, BD/ORM, `src.adapters` |
| `src/adapters/inbound/` | `src.application`, `src.domain`, `src.adapters.outbound.factory`, su framework | drivers de BD y repositorios concretos |
| `src/adapters/outbound/` | `src.application` (puertos), `src.domain`, su motor | reglas de negocio propias |

### `src/domain/` — núcleo puro y determinista

- Única fuente de verdad para triaje, enrutamiento, severidades P0–P3, SLA,
  escalamiento, equipos, estados y clave de duplicados.
- Cero imports de `fastapi`, `pydantic`, `typer`, `uvicorn`, clientes HTTP
  (`requests`, `httpx`), `sqlite3`, `psycopg`, `sqlalchemy`, `src.application` o
  `src.adapters`.
- Cero IO: nada de archivos, red, base de datos, `os.environ` ni reloj del host.
  El instante de referencia se recibe como argumento explícito.
- Misma entrada + mismo instante de referencia ⇒ mismo resultado.

### `src/application/` — casos de uso y puertos

- `services.py` contiene los casos de uso compartidos (`IncidentService`).
- `ports.py` contiene los puertos secundarios como `typing.Protocol`, tipados con
  el modelo de dominio:

  ```python
  from typing import Protocol

  from src.domain.models import Incident


  class IncidentRepositoryPort(Protocol):
      def save(self, incident: Incident) -> None: ...
      def get(self, incident_id: str) -> Incident | None: ...
  ```

- Solo puede importar la biblioteca estándar y `src.domain`. Nada de FastAPI,
  Pydantic, Typer, SQL ni adaptadores.
- La validación de negocio vive aquí o en el dominio, nunca en el adaptador.

### `src/adapters/inbound/` — adaptadores primarios delgados

- `api/` expone REST con FastAPI; `cli.py` expone la terminal con Typer.
- Ambos DEBEN delegar en el mismo caso de uso de `IncidentService`. El adaptador
  solo traduce entrada, presenta salida y mapea errores a su protocolo.
- Prohibido importar drivers de BD (`sqlite3`, `psycopg`, `sqlalchemy`) o
  repositorios concretos. Las dependencias salientes se obtienen únicamente a
  través de `src.adapters.outbound.factory`.
- Pydantic se usa solo para el contrato de entrada/salida HTTP; no define reglas
  de clasificación ni de SLA.
- Un futuro adaptador MCP se añade en este directorio con las mismas reglas.

### `src/adapters/outbound/` — adaptadores secundarios

- Implementan el puerto `IncidentRepositoryPort` definido en la aplicación.
- `factory.py` es el punto de composición: selecciona la implementación a partir
  de `DATABASE_URL` y devuelve el puerto. Ni el dominio ni la aplicación leen
  variables de entorno.
- El mapeo entre modelo de dominio y representación persistida vive aquí; ninguna
  regla de negocio se duplica.
- Cambiar de motor (por ejemplo H004) implica un adaptador nuevo y un ADR, no
  editar el núcleo.

## Paridad obligatoria entre adaptadores primarios

REST y CLI son dos envoltorios del mismo caso de uso:

- Ambos invocan exactamente el mismo método de `IncidentService`; ninguno
  reimplementa clasificación, severidades ni SLA.
- Comparten el mismo contrato de salida (`incident_id`, `severity`, `component`,
  `recommended_team`, `duplicate_group_key`, `rationale`). El JSON por defecto de
  la CLI equivale al cuerpo de respuesta HTTP.
- Los códigos de error provienen de `ValidationError` en la aplicación. Lo único
  específico de cada adaptador es su traducción: HTTP 422/400 frente a código de
  salida y `stderr`.
- Todo caso nuevo se cubre en ambos adaptadores dentro de
  `tests/test_spec_001_triage.py`; una diferencia de comportamiento es un bug.

## Verificación estática con Ruff

### Configuración raíz (`pyproject.toml`)

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "TID"]

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "parents"
```

- `TID251` (`banned-api`) prohíbe módulos concretos por capa.
- `TID252` (`ban-relative-imports = "parents"`) exige imports absolutos y bloquea
  `from ..capa import ...`; los imports hermanos (`from .models import ...`)
  siguen permitidos.

### Configuración jerárquica por capa

Ruff resuelve la configuración por archivo con el `ruff.toml` más cercano. Un
`ruff.toml` hijo **reemplaza** la configuración raíz para su subárbol, así que
debe usar `extend` o la puerta quedará vacía. Para añadir prohibiciones sin
perder las heredadas, usa `extend-banned-api` (no `banned-api`, que sustituye la
tabla completa).

`src/domain/ruff.toml`:

```toml
extend = "../../pyproject.toml"

[lint]
select = ["E4", "E7", "E9", "F", "TID"]

[lint.flake8-tidy-imports]
ban-relative-imports = "parents"

[lint.flake8-tidy-imports.extend-banned-api]
"fastapi".msg = "El dominio no depende de frameworks web."
"pydantic".msg = "El dominio no depende de validación de frameworks."
"typer".msg = "El dominio no depende de la CLI."
"uvicorn".msg = "El dominio no depende del servidor HTTP."
"requests".msg = "El dominio no hace IO de red."
"httpx".msg = "El dominio no hace IO de red."
"sqlite3".msg = "El dominio no depende de la base de datos."
"psycopg".msg = "El dominio no depende de la base de datos."
"sqlalchemy".msg = "El dominio no depende de un ORM."
"src.application".msg = "El dominio no conoce la aplicación."
"src.adapters".msg = "El dominio no conoce adaptadores."
```

`src/application/ruff.toml`: mismo `extend = "../../pyproject.toml"` y las mismas
prohibiciones, salvo que aquí solo se veta `src.adapters` (la aplicación sí puede
importar `src.domain`).

`src/adapters/inbound/ruff.toml`: `extend = "../../../pyproject.toml"` y vetos de
persistencia:

```toml
[lint.flake8-tidy-imports.extend-banned-api]
"sqlite3".msg = "Usa src.adapters.outbound.factory, no el driver."
"psycopg".msg = "Usa src.adapters.outbound.factory, no el driver."
"sqlalchemy".msg = "Usa src.adapters.outbound.factory, no el ORM."
"src.adapters.outbound.sqlite_repository".msg = "Obtén el repositorio vía src.adapters.outbound.factory."
```

Nombra los módulos concretos de `src.adapters.outbound`; no vetes
`src.adapters.outbound` completo, porque el `factory` debe seguir siendo
importable.

### Comando obligatorio

```bash
uv run ruff check src/
```

Debe terminar sin errores antes de dar una tarea por terminada. Complementa la
puerta con `uv run pytest -v` para la paridad REST/CLI.

Si `select` no está definido en `pyproject.toml`, Ruff aplica su conjunto por
defecto y la puerta no verifica estas fronteras: confirma la configuración antes
de confiar en un `All checks passed`. Si el comando falla con
`Failed to spawn: ruff`, declara la dependencia de desarrollo
(`uv add --dev ruff`); no la sustituyas por otra herramienta.

## Checklist antes de cerrar un cambio

- [ ] `uv run ruff check src/` sin errores.
- [ ] `uv run pytest -v` en verde, con el escenario cubierto en REST y CLI.
- [ ] Ningún import prohibido en la capa tocada (TID251/TID252 limpios).
- [ ] Las reglas nuevas están en `src/domain/`, no en el adaptador.
- [ ] `src/adapters/inbound/` no importa drivers ni repositorios concretos.
- [ ] Los puertos usan `typing.Protocol` y tipos de `src.domain`.
- [ ] El contrato de salida y los códigos de error son idénticos en REST y CLI.
- [ ] Si cambió una frontera o una dependencia, existe el ADR correspondiente y
      la constitución sigue vigente.

## Errores comunes

- **Mover el import a `if TYPE_CHECKING` para silenciar TID251**: Ruff también lo
  detecta. La solución es invertir la dependencia con un puerto, no esconder el
  import.
- **Crear un `ruff.toml` hijo sin `extend`**: desactiva silenciosamente las reglas
  raíz para esa capa. Verifica con un import prohibido de prueba.
- **Usar `banned-api` en el hijo**: reemplaza la tabla heredada. Usa
  `extend-banned-api`.
- **Instanciar el repositorio concreto en el router o en el comando CLI**: hazlo
  en el `factory` y recibe el puerto.
- **Duplicar el mapeo de severidades o el cálculo de SLA en un adaptador**:
  cualquier tabla o umbral fuera de `src/domain/` es una violación.

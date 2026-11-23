# Imagen del contenedor del servicio API (per plan.md Phase 1 / T001).
FROM python:3.12-slim

# Bootstrap de `uv` sin necesidad de pip (per research.md R4).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Instala dependencias de ejecución reproducible (sans dev) con `uv.lock`.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Código del servicio.
COPY src ./src

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "src.adapters.inbound.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

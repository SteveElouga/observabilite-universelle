# syntax=docker/dockerfile:1
# units-service — démo d'instrumentation OpenTelemetry (§10.1). Image multi-stage, exécution non-root.
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt \
 && /opt/venv/bin/opentelemetry-bootstrap -a install   # installe les instrumentations détectées (Django, gRPC, requests...)

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .
USER app
EXPOSE 8000
# Auto-instrumentation : aucune ligne de code applicatif, tout passe par l'environnement (§10.1).
CMD ["opentelemetry-instrument", "gunicorn", "units_project.wsgi", "-c", "gunicorn.conf.py"]

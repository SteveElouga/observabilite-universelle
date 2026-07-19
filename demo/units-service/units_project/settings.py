"""
settings.py — units-service (démo d'instrumentation OpenTelemetry, §10.1 du document maître).

Volontairement minimal : pas de vraie base de données, pas d'authentification. L'objectif
est de prouver la chaîne d'observabilité (traces, métriques et logs corrélés), pas de faire
une application métier. L'instrumentation ne met AUCUNE ligne dans le code applicatif : elle
passe par les variables d'environnement et le wrapper « opentelemetry-instrument ».
"""
import os
from pathlib import Path

# python-json-logger a réorganisé son module en 3.1 : on gère les deux emplacements
# pour être robuste à la version installée.
try:
    from pythonjsonlogger.json import JsonFormatter  # python-json-logger >= 3.1
except ImportError:  # versions < 3.1
    from pythonjsonlogger.jsonlogger import JsonFormatter

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("UNITS_SECRET_KEY", "demo-insecure-key-change-me")
DEBUG = os.environ.get("UNITS_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("UNITS_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "units_project.urls"
WSGI_APPLICATION = "units_project.wsgi.application"
TEMPLATES = []

# Base de données factice : la démo ne persiste rien, les endpoints n'y touchent pas.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "demo.sqlite3",
    }
}

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Journalisation structurée JSON avec trace_id/span_id (§10.1) ---
# C'est ce qui rend le lien log -> trace cliquable dans Grafana (§10.5).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "trace": {"()": "units_project.logging_utils.TraceContextFilter"},
    },
    "formatters": {
        "json": {
            "()": JsonFormatter,
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["trace"],
            "formatter": "json",
        },
    },
    "root": {"handlers": ["console"], "level": os.environ.get("UNITS_LOG_LEVEL", "INFO")},
}

"""
Configuration gunicorn pour units-service.

Un seul worker par défaut : avec « opentelemetry-instrument gunicorn », le wrapper
d'auto-instrumentation suffit tel quel en mono-worker (§10.1). Pour passer à plusieurs
workers en production, ré-initialisez le SDK OpenTelemetry dans le hook post_fork
ci-dessous (les exporters OTel n'aiment pas le fork), pattern documenté par OTel.
"""
import os

bind = os.environ.get("UNITS_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("UNITS_WORKERS", "1"))
accesslog = "-"  # accès sur stdout -> logs conteneur -> Loki via Alloy
errorlog = "-"


def post_fork(server, worker):
    """À plus d'un worker, ré-initialiser ici le SDK OTel plutôt que via le wrapper.
    Laissé vide en mono-worker (le wrapper suffit)."""
    pass

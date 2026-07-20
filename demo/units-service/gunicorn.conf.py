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
    """Profiling continu par worker (§10.1) + lien trace vers profil (§10.5).

    Pyroscope échantillonne le processus avec py-spy : il faut donc l'initialiser APRÈS le
    fork, dans chaque worker (l'initialiser dans le maître laisserait un état cassé après fork).
    On ajoute ensuite le PyroscopeSpanProcessor au tracer provider déjà mis en place par
    l'auto-instrumentation : il pose l'attribut `pyroscope.profile.id` sur le span racine, ce qui
    permet le saut trace -> profil dans Grafana (datasource Tempo, tracesToProfiles).
    """
    import os

    import pyroscope
    from opentelemetry import trace
    from pyroscope.otel import PyroscopeSpanProcessor

    pyroscope.configure(
        app_name=os.environ.get("OTEL_SERVICE_NAME", "units-service"),
        server_address=os.environ.get("PYROSCOPE_SERVER_ADDRESS", "http://pyroscope:4040"),
        sample_rate=100,
    )
    trace.get_tracer_provider().add_span_processor(PyroscopeSpanProcessor())

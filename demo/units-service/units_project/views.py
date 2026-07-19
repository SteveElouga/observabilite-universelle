"""
Endpoints de démonstration pour units-service.

Chaque appel à /demo/commande émet les trois signaux d'un coup :
  - une TRACE (auto-instrumentée par OpenTelemetry, aucune ligne de code ici) ;
  - une MÉTRIQUE métier (compteur à faible cardinalité, règle §7.3) ;
  - un LOG JSON structuré, corrélé à la trace par trace_id (§10.1 / §10.5).

L'identifiant à forte cardinalité (user.id) va en ATTRIBUT DE SPAN, jamais en label de métrique.
"""
import logging
import random

from django.http import JsonResponse
from opentelemetry import metrics, trace

logger = logging.getLogger("units")

# Un seul meter et un seul compteur, créés au niveau module.
meter = metrics.get_meter("units-service")
commandes_creees = meter.create_counter(
    "commandes_creees_total",
    description="Nombre de commandes créées",
    unit="1",
)

_MODES_PAIEMENT = ("carte", "virement", "especes")


def sante(request):
    """Sonde de vivacité simple."""
    return JsonResponse({"status": "ok", "service": "units-service"})


def creer_commande(request):
    """Démo : crée une commande fictive et émet trace + métrique + log corrélés."""
    user_id = request.GET.get("user_id", str(random.randint(1, 999)))
    mode = random.choice(_MODES_PAIEMENT)

    # Métrique métier : labels à FAIBLE cardinalité uniquement (statut, mode de paiement).
    commandes_creees.add(1, {"statut": "payee", "mode_paiement": mode})

    # Identifiant à FORTE cardinalité en ATTRIBUT DE SPAN (gratuit côté cardinalité,
    # retrouvable via TraceQL { .user.id = "42" }), jamais en label de métrique.
    trace.get_current_span().set_attribute("user.id", str(user_id))

    # Log JSON structuré : trace_id injecté par le filtre -> clic log -> trace dans Grafana.
    logger.info(
        "commande créée",
        extra={"order_id": f"CMD-{random.randint(1000, 9999)}", "mode_paiement": mode},
    )

    return JsonResponse(
        {"resultat": "commande créée", "mode_paiement": mode, "user_id": user_id}
    )

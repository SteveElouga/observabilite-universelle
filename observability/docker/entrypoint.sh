#!/bin/sh
# entrypoint.sh — prépare le conteneur puis passe la main à supervisord.
set -eu

# 1. Les configurations du socle désignent leurs voisins par leur nom de service Docker
#    (`otel-collector:4317`, `tempo:3200`, `loki:3100`…). Dans un conteneur unique, ces noms
#    doivent résoudre vers la boucle locale. On les ajoute ici plutôt que de réécrire les
#    fichiers : les mêmes configurations servent alors au compose multi-conteneurs ET à cette
#    image, et elles ne peuvent pas diverger.
if ! grep -q "otel-collector" /etc/hosts 2>/dev/null; then
  printf '127.0.0.1 otel-collector prometheus loki tempo pyroscope grafana alertmanager alloy\n' >> /etc/hosts
fi

# 2. Refus de démarrer sans mot de passe administrateur Grafana. Un défaut silencieux ferait
#    tourner une interface exposée avec « admin/admin » — le README du socle l'interdit
#    explicitement avant toute exposition réelle.
if [ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]; then
  echo "ERREUR : GRAFANA_ADMIN_PASSWORD n'est pas défini." >&2
  echo "         L'image refuse de démarrer plutôt que d'exposer Grafana avec un mot de passe par défaut." >&2
  exit 1
fi
export GF_SECURITY_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASSWORD"

# 3. Le webhook Slack d'Alertmanager n'est PAS une variable d'environnement : Alertmanager ne
#    les lit pas. Le socle attend un fichier, délibérément hors image. S'il est monté, tant
#    mieux ; sinon on écrit un fichier vide pour qu'Alertmanager démarre au lieu d'échouer.
if [ ! -f /etc/alertmanager/secrets/slack_webhook_url ]; then
  mkdir -p /etc/alertmanager/secrets
  : > /etc/alertmanager/secrets/slack_webhook_url
fi

# 4. Passage à supervisord, qui reste root pour pouvoir ouvrir /dev/stdout et poser l'identité
#    `obs` sur chacun des huit programmes. Lui n'ouvre aucun port et ne parle à aucun réseau.
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf

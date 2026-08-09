#!/bin/sh
# entrypoint.sh — prépare le conteneur puis passe la main à supervisord.
set -eu

# 1. Les configurations du socle désignent leurs voisins par leur nom de service Docker
#    (`otel-collector:4317`, `tempo:3200`, `loki:3100`…). Dans un conteneur unique, ces noms
#    doivent résoudre vers la boucle locale. On les ajoute ici plutôt que de réécrire les
#    fichiers : les mêmes configurations servent alors au compose multi-conteneurs ET à cette
#    image, et elles ne peuvent pas diverger.
if ! grep -q "otel-collector" /etc/hosts 2>/dev/null; then
  printf '127.0.0.1 otel-collector prometheus loki tempo pyroscope grafana alertmanager alloy node-exporter blackbox-exporter postgres-exporter\n' >> /etc/hosts
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

# 2 bis. RÉCONCILIATION DU MOT DE PASSE, et non simple transmission. Grafana n'applique
#        GF_SECURITY_ADMIN_PASSWORD qu'à la CRÉATION de l'utilisateur admin ; ensuite sa base
#        fait foi et la variable est ignorée EN SILENCE. Comme /var/lib/obs est un volume, la
#        base survit au remplacement du conteneur : régénérer son .env suffit alors à se
#        retrouver dehors, avec pour tout indice « invalid username or password ».
#        Constaté le 09/08 sur une base créée la veille — une heure pour comprendre.
#
#        On réaligne donc à chaque démarrage. Contrepartie assumée, et symétrique de
#        « allowUiUpdates: false » sur les dashboards : un mot de passe changé depuis
#        l'interface est écrasé au redémarrage. Sur une plateforme provisionnée, la variable
#        d'environnement est la source de vérité, pas l'état accumulé dans un volume.
if [ -f /var/lib/obs/grafana/grafana.db ]; then
  if /usr/share/grafana/bin/grafana cli --homepath /usr/share/grafana \
       --config /etc/grafana/grafana.ini \
       admin reset-admin-password "$GRAFANA_ADMIN_PASSWORD" >/dev/null 2>&1; then
    echo "Grafana : base existante, mot de passe administrateur réaligné sur GRAFANA_ADMIN_PASSWORD."
  else
    echo "Grafana : base existante mais réalignement du mot de passe IMPOSSIBLE." >&2
    echo "          L'accès se fera avec l'ancien mot de passe, pas celui de l'environnement." >&2
  fi
  # La CLI a écrit en tant que root ; sans cela Grafana, qui tourne en « obs », ne peut plus
  # ouvrir sa propre base en écriture.
  chown -R obs:obs /var/lib/obs/grafana
fi

# 3. Le webhook Slack d'Alertmanager n'est PAS une variable d'environnement : Alertmanager ne
#    les lit pas. Le socle attend un fichier, délibérément hors image. S'il est monté, tant
#    mieux ; sinon on écrit un fichier vide pour qu'Alertmanager démarre au lieu d'échouer.
mkdir -p /etc/alertmanager/secrets
for secret in slack_webhook_url oneuptime_webhook_url; do
  # oneuptime_webhook_url manquait ici alors qu'alertmanager.yml le référence pour la garde
  # (receiver « page-oncall »). Même traitement que Slack : fichier vide plutôt qu'un refus.
  [ -f "/etc/alertmanager/secrets/$secret" ] || : > "/etc/alertmanager/secrets/$secret"
done

# 3 bis. postgres_exporter ne démarre que branché. Sans chaîne de connexion il sort aussitôt, et
#        supervisord le relancerait sans fin : une fausse panne qui masque les vraies. On décide
#        ici, une fois, plutôt que de laisser un processus agoniser en boucle.
if [ -n "${DATA_SOURCE_NAME:-}" ]; then
  PG_EXPORTER_AUTOSTART=true
  echo "postgres_exporter : chaîne de connexion détectée, collecte PostgreSQL activée."
else
  PG_EXPORTER_AUTOSTART=false
  echo "postgres_exporter : DATA_SOURCE_NAME absente — collecte PostgreSQL désactivée (attendu hors PostgreSQL)."
fi
export PG_EXPORTER_AUTOSTART

# 3 ter. Cibles optionnelles du consommateur. Prometheus les découvre par fichier ; on n'écrit
#        que celles dont l'adresse est fournie. Un fichier laissé à « [] » ne déclare aucune
#        cible : la règle d'alerte correspondante existe mais reste muette, ce qui vaut mieux
#        qu'un job perpétuellement « down » pour un composant que personne n'a demandé.
ecrire_cible() {   # $1 = nom du fichier, $2 = adresse hôte:port, $3 = étiquette du job
  if [ -n "$2" ]; then
    printf '[{"targets":["%s"],"labels":{"role":"%s"}}]\n' "$2" "$3" \
      > "/etc/prometheus/targets/$1.yml"
    echo "cible $3 : $2"
  fi
}
# PostgreSQL est scruté par l'exportateur LOCAL, pas par la base : l'adresse est donc fixe, et
# c'est la présence de la chaîne de connexion qui décide.
[ -n "${DATA_SOURCE_NAME:-}" ] && ecrire_cible postgres "postgres-exporter:9187" postgres
ecrire_cible rabbitmq "${RABBITMQ_METRICS_TARGET:-}" rabbitmq
ecrire_cible keycloak "${KEYCLOAK_METRICS_TARGET:-}" keycloak

# Les sondes de la démonstration visent des conteneurs qui n'existent QU'EN MODE COMPOSE. Les
# laisser actives dans l'image ferait sonner « ProbeDown » en permanence chez le consommateur —
# constaté en recette, corrigé ici. Le fichier versionné garde les cibles pour le compose ; on
# le vide dans l'image, sauf demande explicite.
if [ "${DEMO_TARGETS:-false}" != "true" ]; then
  printf '[]\n' > /etc/prometheus/targets/demo.yml
fi

# 4. Passage à supervisord, qui reste root pour pouvoir ouvrir /dev/stdout et poser l'identité
#    `obs` sur chacun des douze programmes. Lui n'ouvre aucun port et ne parle à aucun réseau.
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf

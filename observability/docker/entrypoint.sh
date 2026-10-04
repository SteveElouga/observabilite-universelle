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
#    les lit pas. Le socle attend un fichier, délibérément hors image.
#
#    ⚠ CORRECTION DU 14/09/2026 : écrire un fichier VIDE ne suffisait pas et masquait le
#    problème. Alertmanager lit `url_file`/`api_url_file` AU MOMENT DE NOTIFIER : un fichier
#    vide produit un échec de notification à chaque alerte, exactement comme un fichier
#    absent (1 447 échecs en 72 h constatés en recette). La configuration effective est donc
#    désormais RENDUE par alertmanager/render-config.sh, qui n'insère une intégration que si
#    son secret existe ET n'est pas vide. On ne crée plus de fichier vide.
mkdir -p /etc/alertmanager/secrets
ALERTMANAGER_RENDERED_CONFIG=${ALERTMANAGER_RENDERED_CONFIG:-/var/lib/obs/alertmanager/alertmanager.yml}
export ALERTMANAGER_RENDERED_CONFIG
# /var/lib/obs est un VOLUME : un volume préexistant, créé par une version antérieure de
# l'image, n'a pas forcément ce sous-répertoire. Sans lui le rendu échoue et le conteneur
# entier refuse de démarrer, pour une raison sans rapport visible avec l'alerting.
mkdir -p "$(dirname "$ALERTMANAGER_RENDERED_CONFIG")"
sh /etc/alertmanager/render-config.sh
chown obs:obs "$ALERTMANAGER_RENDERED_CONFIG"

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

# Passerelle GraphQL du consommateur, sondée par `{__typename}` (module http_graphql). Cette
# cible était VERSIONNÉE en dur jusqu'au 15/09/2026 : partout où le consommateur ne tourne pas
# sur le réseau obs-edge, elle produisait un « ProbeDown » (severity=page) permanent. Elle ne
# s'écrit donc plus que sur demande.
if [ -n "${APPLICATION_GRAPHQL_TARGET:-}" ]; then
  printf '[{"targets":["%s"],"labels":{"role":"application","composant":"graphql"}}]\n' \
    "$APPLICATION_GRAPHQL_TARGET" > /etc/prometheus/targets/application-graphql.yml
  echo "sonde de l'application (passerelle GraphQL) : $APPLICATION_GRAPHQL_TARGET"
fi

# Sondes HTTP du consommateur qui ne sont PAS joignables par nom depuis la plateforme (elles
# ne partagent pas le réseau obs-edge) : proxy frontal, passerelle tierce… Liste d'URLs
# séparées par des espaces.
if [ -n "${APPLICATION_PROBE_TARGETS:-}" ]; then
  liste=""
  for cible in $APPLICATION_PROBE_TARGETS; do
    liste="${liste:+$liste,}\"$cible\""
  done
  printf '[{"targets":[%s],"labels":{"role":"application"}}]\n' "$liste" \
    > /etc/prometheus/targets/application-http.yml
  echo "sondes de l'application : $APPLICATION_PROBE_TARGETS"
fi

# Les sondes de la DÉMONSTRATION n'existent plus dans l'image depuis le 04/10/2026 : le job
# `blackbox-demo` et ses cibles visaient des conteneurs du seul compose de ce dépôt, et
# .dockerignore les écarte désormais. DEMO_TARGETS n'a donc plus d'effet ici.

# 4. Passage à supervisord, qui reste root pour pouvoir ouvrir /dev/stdout et poser l'identité
#    `obs` sur chacun des douze programmes. Lui n'ouvre aucun port et ne parle à aucun réseau.
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf

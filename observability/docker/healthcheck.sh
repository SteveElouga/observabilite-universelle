#!/bin/sh
# healthcheck.sh — la sonde vérifie la CHAÎNE, pas seulement Grafana.
#
# Une première version ne sondait que Grafana : le conteneur s'est déclaré « healthy » alors que
# quatre composants sur huit étaient morts. Une sonde qui ment est pire que pas de sonde.
set -eu

# Grafana — l'interface
wget -q -O /dev/null http://127.0.0.1:3000/api/health || exit 1
# Loki et Tempo — les deux magasins que gp-formuloo interroge
wget -q -O /dev/null http://127.0.0.1:3100/ready || exit 1
wget -q -O /dev/null http://127.0.0.1:3200/ready || exit 1
# Prometheus — métriques
wget -q -O /dev/null http://127.0.0.1:9090/-/healthy || exit 1
# OTel Collector — l'entrée de la chaîne, et le piège de cette sonde.
#
# Une version antérieure se contentait de vérifier qu'« un processus écoute sur 4318 ». Le
# conteneur s'est déclaré sain alors que le Collector était mort : c'était Tempo, dont les
# récepteurs OTLP occupaient le port. Une sonde doit identifier QUI répond, pas seulement QUE
# quelque chose répond.
#
# Aucune extension health_check n'étant déclarée dans la configuration du socle, on interroge la
# télémétrie interne du Collector : la présence d'une métrique préfixée `otelcol_` ne peut venir
# que de lui.
wget -q -O - http://127.0.0.1:8888/metrics 2>/dev/null | grep -q '^otelcol_' || exit 1
exit 0

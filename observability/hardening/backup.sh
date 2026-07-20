#!/bin/sh
# backup.sh — sauvegarde des volumes à état de la plateforme (§7.5).
#
# L'as-code (dashboards provisionnés, datasources, règles, SLO) est déjà votre première
# sauvegarde, puisqu'il vit dans le dépôt. Ce script couvre l'état NON versionné :
#   - grafana-data : tableaux de bord créés à la main, préférences ;
#   - gt-db        : historique des erreurs GlitchTip (base Postgres) ;
#   - kuma-data    : configuration d'Uptime Kuma.
#
# Les données de télémétrie (Prometheus, Loki, Tempo) sont volontairement PAS sauvegardées :
# leur perte est jugée acceptable (§7.5). Adaptez si votre politique diffère.
#
# Usage :   ./backup.sh [dossier_de_destination]   (défaut : ./backups)
# Planification : ajoutez une ligne cron sur l'hôte, par exemple chaque nuit à 3 h :
#   0 3 * * * cd /chemin/vers/observability && ./hardening/backup.sh /var/backups/observabilite
set -eu

DEST="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/$STAMP"
mkdir -p "$OUT"
OUT_ABS="$(cd "$OUT" && pwd)"

for vol in grafana-data gt-db kuma-data; do
	# Docker préfixe les volumes par le nom du projet (dossier) ; on retrouve le nom complet.
	full="$(docker volume ls -q | grep -E "_${vol}\$" | head -n1)"
	if [ -z "$full" ]; then
		echo "volume $vol introuvable, ignoré" >&2
		continue
	fi
	echo "sauvegarde de $full ..."
	docker run --rm -v "$full":/src:ro -v "$OUT_ABS":/dst alpine \
		tar czf "/dst/${vol}.tar.gz" -C /src .
done

echo "sauvegarde terminée dans $OUT"
# Restauration d'un volume :
#   docker run --rm -v <volume_complet>:/dst -v "$PWD":/src alpine tar xzf /src/<vol>.tar.gz -C /dst

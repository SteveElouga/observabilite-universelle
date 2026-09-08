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
	full=""   # jamais de report d'une itération à l'autre (sinon un $vol ambigu sans
	          # correspondance COMPOSE_PROJECT_NAME hériterait silencieusement du $full précédent)
	# Docker préfixe les volumes par le nom du projet (dossier) ; on retrouve le nom complet.
	matches="$(docker volume ls -q | grep -E "_${vol}\$" || true)"
	count="$(printf '%s\n' "$matches" | grep -c . || true)"
	if [ "$count" -eq 0 ]; then
		echo "volume $vol introuvable, ignoré" >&2
		continue
	fi
	if [ "$count" -gt 1 ]; then
		# Vérifié en conditions réelles le 08/09/2026 : plusieurs projets Compose nommés
		# "observability" (ex. un durcissement testé en parallèle du socle de dev) produisent
		# chacun un volume "*_grafana-data" etc. Un `head -n1` silencieux aurait alors sauvegardé
		# un projet au hasard, sans le dire — pire qu'une absence de sauvegarde. On refuse plutôt
		# de choisir : filtrez avec COMPOSE_PROJECT_NAME (ex. COMPOSE_PROJECT_NAME=observability
		# ./backup.sh) pour ne garder que le volume de ce projet.
		echo "plusieurs volumes correspondent à $vol, choix ambigu :" >&2
		printf '%s\n' "$matches" | sed 's/^/  - /' >&2
		if [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
			full="$(printf '%s\n' "$matches" | grep -E "^${COMPOSE_PROJECT_NAME}_${vol}\$" || true)"
		fi
		if [ -z "${full:-}" ]; then
			echo "  → définissez COMPOSE_PROJECT_NAME pour désambiguïser (ex. COMPOSE_PROJECT_NAME=observability $0), $vol ignoré" >&2
			continue
		fi
	else
		full="$matches"
	fi
	echo "sauvegarde de $full ..."
	docker run --rm -v "$full":/src:ro -v "$OUT_ABS":/dst alpine \
		tar czf "/dst/${vol}.tar.gz" -C /src .
done

echo "sauvegarde terminée dans $OUT"
# Restauration d'un volume :
#   docker run --rm -v <volume_complet>:/dst -v "$PWD":/src alpine tar xzf /src/<vol>.tar.gz -C /dst

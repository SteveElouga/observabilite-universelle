#!/bin/sh
# slo/regenerer.sh — régénère les règles Sloth à partir des fichiers SLO-as-code.
#
# Un seul artefact : prometheus/rules/rules-slo.yml, les SLO de la DÉMO, git-ignoré
# (.gitignore:9). Les SLO d'un projet observé vivent dans son dépôt, avec ses règles : il les
# génère lui-même et les monte dans `rules/consommateur/` (README, « Ce que le projet fournit »).
#
# Usage :  sh slo/regenerer.sh          (depuis observability/, ou de n'importe où)
#          IMAGE_SLOTH=… sh slo/regenerer.sh
#
# Le binaire vient de l'image officielle épinglée, pour que tout le monde régénère le MÊME
# fichier : un `sloth` local d'une autre version produirait une dérive à chaque exécution.
set -eu

IMAGE_SLOTH=${IMAGE_SLOTH:-ghcr.io/slok/sloth:v0.16.0}
RACINE=$(cd "$(dirname "$0")/.." && pwd)

generer() {   # $1 = source SLO-as-code, $2 = fichier de règles produit
  docker run --rm --user "$(id -u):$(id -g)" -v "$RACINE:/w" -w /w "$IMAGE_SLOTH" \
    generate -i "$1" -o "$2"
  echo "régénéré : $2"
}

generer slo/units-service.yml prometheus/rules/rules-slo.yml

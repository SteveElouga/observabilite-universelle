#!/bin/sh
# slo/regenerer.sh — régénère les règles Sloth à partir des fichiers SLO-as-code.
#
# Pourquoi un script, et pas une ligne de README (corrigé le 15/09/2026). Deux artefacts
# générés cohabitent dans ce dépôt, avec deux traitements DIFFÉRENTS :
#
#   · prometheus/rules/rules-slo.yml  (SLO de la DÉMO)         → git-ignoré (.gitignore:9)
#   · prometheus/rules/slo-sgfe.yml   (SLO du CONSOMMATEUR)    → VERSIONNÉ
#
# La divergence est délibérée : la démo ne tourne que chez qui lance le profil `demo` et peut
# régénérer ses règles, tandis qu'une installation du socle sans binaire `sloth` n'aurait
# AUCUN SLO SGFE si le fichier n'était pas livré — les écrans « SLO et budget d'erreur »
# resteraient vides sans que rien ne le dise. Mais versionner un artefact généré crée deux
# sources de vérité : rien n'empêche `slo/sgfe.yml` de diverger des règles réellement
# chargées. C'est ce script qui rend l'une reproductible depuis l'autre, et le test
# `tests/test_tableaux_de_bord.py::SLOGeneresEtVersionnes` qui interdit la dérive — même
# principe que le `generated.ts` du frontend, livré ET vérifié par une porte.
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

generer slo/sgfe.yml          prometheus/rules/slo-sgfe.yml
generer slo/units-service.yml prometheus/rules/rules-slo.yml

echo "Rappel : slo-sgfe.yml est VERSIONNÉ (le commiter), rules-slo.yml est git-ignoré."

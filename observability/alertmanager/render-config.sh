#!/bin/sh
# render-config.sh — assemble la configuration EFFECTIVE d'Alertmanager.
#
# Pourquoi ce script existe (incident du 11/09/2026). `alertmanager.yml` déclarait en dur
# une intégration OneUptime pointant `url_file: …/secrets/oneuptime_webhook_url`, fichier
# absent de l'installation. Alertmanager lit `url_file` AU MOMENT DE NOTIFIER, pas au
# chargement : la configuration passait `amtool check-config`, le conteneur démarrait vert,
# et chaque alerte `severity=page` échouait en « notify retry canceled due to unrecoverable
# error … no such file or directory » (1 447 échecs en 72 h). Détection : oui. Alerte : non.
#
# Principe retenu : UNE INTÉGRATION DONT LE SECRET MANQUE N'ENTRE PAS DANS LA CONFIGURATION.
# Le socle versionné ne contient que ce qui est toujours vrai ; ce script y insère, aux
# ancres « >>> integrations-optionnelles: <receiver> », les blocs dont le secret existe ET
# n'est pas vide. Un secret absent = un bloc absent = zéro échec de notification.
#
# Usage :
#   render-config.sh                      # rend la configuration et s'arrête
#   render-config.sh --config.file=… …    # rend la configuration puis exec alertmanager
#
# Variables (toutes optionnelles) :
#   ALERTMANAGER_BASE_CONFIG      socle versionné   (défaut /etc/alertmanager/alertmanager.yml)
#   ALERTMANAGER_SECRETS_DIR      dossier secrets   (défaut /etc/alertmanager/secrets)
#   ALERTMANAGER_RENDERED_CONFIG  sortie            (défaut /tmp/alertmanager.yml)
#   ALERT_EMAIL_TO / ALERT_EMAIL_FROM / ALERT_SMTP_SMARTHOST / ALERT_SMTP_USERNAME
#                                 e-mail de secours ; le mot de passe vit dans
#                                 $ALERTMANAGER_SECRETS_DIR/smtp_password
set -eu

BASE=${ALERTMANAGER_BASE_CONFIG:-/etc/alertmanager/alertmanager.yml}
SECRETS=${ALERTMANAGER_SECRETS_DIR:-/etc/alertmanager/secrets}
OUT=${ALERTMANAGER_RENDERED_CONFIG:-/tmp/alertmanager.yml}
ALERTMANAGER_BIN=${ALERTMANAGER_BIN:-/bin/alertmanager}

# Un secret « présent » est un fichier NON VIDE une fois les blancs retirés : le socle en
# mode image crée des fichiers vides pour que le conteneur démarre, et un fichier vide ne
# vaut pas mieux qu'un fichier absent — il produirait la même notification en échec.
secret_utilisable() {
  [ -f "$SECRETS/$1" ] || return 1
  [ -s "$SECRETS/$1" ] || return 1
  [ -n "$(tr -d ' \t\r\n' < "$SECRETS/$1")" ] || return 1
  return 0
}

# Notification Slack, gabarit compris. Écrite ici et non dans le socle pour que la règle
# « pas de secret, pas d'intégration » vaille AUSSI pour le canal principal : sans cela, une
# installation sans `slack_webhook_url` rejouait mot pour mot l'incident du 11/09 (chaque
# notification en « read api_url_file: … no such file or directory »).
#
# Le gabarit est explicite parce que le gabarit `text` par défaut d'Alertmanager est une
# chaîne VIDE : sans lui, Slack reçoit un titre et rien d'autre.
bloc_slack() {   # $1 = fichier de secret, $2 = canal
  printf '    slack_configs:\n'
  printf '      - api_url_file: %s/%s\n' "$SECRETS" "$1"
  printf '        channel: "%s"\n' "$2"
  printf '        send_resolved: true\n'
  printf "        title: '{{ .Status | toUpper }} · {{ .CommonLabels.alertname }}{{ if .CommonLabels.service_name }} · {{ .CommonLabels.service_name }}{{ end }}'\n"
  printf '        text: |-\n'
  printf '          {{ range .Alerts -}}\n'
  printf '          *{{ .Annotations.summary }}*\n'
  printf '          {{ .Annotations.description }}\n'
  printf '          {{ if .Annotations.suivi }}_Suivi :_ {{ .Annotations.suivi }}\n'
  printf '          {{ end }}{{ if .Annotations.runbook_url }}<{{ .Annotations.runbook_url }}|Que faire — runbook>{{ end }}\n'
  printf '          {{ end }}\n'
}

integration_slack() {
  secret_utilisable slack_webhook_url || return 0
  bloc_slack slack_webhook_url "${ALERT_SLACK_CHANNEL:-#alertes}"
}

# Canal de la DETTE D'INSTRUMENTATION (`severity=dette`) : deux règles y déclarent un trou de
# surveillance et sont donc vraies en permanence. Elles ne doivent pas revenir dans le canal
# d'incident — c'est le bruit que C-354 a nettoyé. Un webhook dédié les sépare vraiment ;
# à défaut on retombe sur le webhook principal avec un canal différent, étant entendu qu'un
# webhook créé par une app Slack est lié à son canal et IGNORE ce champ (seuls les webhooks
# « legacy custom integration » l'honorent). Dans ce cas, la séparation tient à la seule
# fréquence : une fois par semaine au lieu d'une fois par jour.
integration_slack_dette() {
  if secret_utilisable slack_webhook_dette_url; then
    bloc_slack slack_webhook_dette_url "${ALERT_SLACK_CHANNEL_DETTE:-#dette-technique}"
  elif secret_utilisable slack_webhook_url; then
    bloc_slack slack_webhook_url "${ALERT_SLACK_CHANNEL_DETTE:-#dette-technique}"
  fi
}

# Blocs insérés dans page-oncall (astreinte) : Slack, OneUptime, puis e-mail de secours.
blocs_page_oncall() {
  integration_slack
  if secret_utilisable oneuptime_webhook_url; then
    printf '    webhook_configs:\n'
    printf '      - url_file: %s/oneuptime_webhook_url\n' "$SECRETS"
    printf '        send_resolved: true\n'
  fi
  blocs_email
}

# Blocs insérés dans slack (tickets) : Slack et e-mail de secours.
blocs_slack() {
  integration_slack
  blocs_email
}

# Un e-mail n'est écrit que si TOUS ses éléments sont là. Un `email_configs` à moitié rempli
# échouerait à chaque notification — exactement le défaut qu'on corrige ici.
email_configure() {
  secret_utilisable smtp_password || return 1
  [ -n "${ALERT_EMAIL_TO:-}" ] || return 1
  [ -n "${ALERT_EMAIL_FROM:-}" ] || return 1
  [ -n "${ALERT_SMTP_SMARTHOST:-}" ] || return 1
  return 0
}

# Canal indépendant de Slack et de sa résolution DNS.
blocs_email() {
  email_configure || return 0
  printf '    email_configs:\n'
  printf '      - to: %s\n' "$ALERT_EMAIL_TO"
  printf '        from: %s\n' "$ALERT_EMAIL_FROM"
  printf '        smarthost: %s\n' "$ALERT_SMTP_SMARTHOST"
  printf '        auth_username: %s\n' "${ALERT_SMTP_USERNAME:-$ALERT_EMAIL_FROM}"
  printf '        auth_password_file: %s/smtp_password\n' "$SECRETS"
  printf '        require_tls: true\n'
  printf '        send_resolved: true\n'
  printf "        headers: { Subject: '{{ .Status | toUpper }} · {{ .CommonLabels.alertname }}' }\n"
}

# Veilleuse : battement de cœur vers un surveillant EXTERNE. Son silence est le signal.
blocs_veilleuse() {
  secret_utilisable veilleuse_webhook_url || return 0
  printf '    webhook_configs:\n'
  printf '      - url_file: %s/veilleuse_webhook_url\n' "$SECRETS"
  printf '        send_resolved: false\n'
}

rendre() {
  tmp="$OUT.tmp.$$"
  : > "$tmp"
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    case "$ligne" in
      *'>>> integrations-optionnelles: page-oncall'*) blocs_page_oncall >> "$tmp" ;;
      *'>>> integrations-optionnelles: slack'*)       blocs_slack       >> "$tmp" ;;
      *'>>> integrations-optionnelles: dette-technique'*) integration_slack_dette >> "$tmp" ;;
      *'>>> integrations-optionnelles: veilleuse'*)   blocs_veilleuse   >> "$tmp" ;;
      *) printf '%s\n' "$ligne" >> "$tmp" ;;
    esac
  done < "$BASE"
  mv "$tmp" "$OUT"
}

rendre

# Journal de ce qui est réellement branché : une plateforme muette doit le DIRE.
for integration in oneuptime_webhook_url slack_webhook_url smtp_password veilleuse_webhook_url; do
  if secret_utilisable "$integration"; then
    echo "alertmanager : intégration « $integration » active."
  else
    echo "alertmanager : intégration « $integration » ABSENTE (secret manquant ou vide) — aucun envoi par ce canal." >&2
  fi
done

if secret_utilisable slack_webhook_dette_url; then
  echo "alertmanager : dette d'instrumentation → webhook Slack dédié (canal ${ALERT_SLACK_CHANNEL_DETTE:-#dette-technique})."
elif secret_utilisable slack_webhook_url; then
  echo "alertmanager : dette d'instrumentation → webhook Slack PRINCIPAL, canal demandé ${ALERT_SLACK_CHANNEL_DETTE:-#dette-technique} (ignoré si le webhook est lié à un canal). Fournir $SECRETS/slack_webhook_dette_url pour séparer réellement les canaux." >&2
fi

# Le pire état possible n'est plus « une intégration en échec », c'est « aucune intégration
# du tout » : Alertmanager démarre vert, groupe les alertes, et ne les remet à personne. On
# refuse de le laisser passer inaperçu.
if ! secret_utilisable slack_webhook_url && ! secret_utilisable oneuptime_webhook_url && ! email_configure; then
  echo "alertmanager : ATTENTION — AUCUN canal de notification n'est configuré. Les alertes seront évaluées, groupées… et transmises à PERSONNE. Fournir au moins $SECRETS/slack_webhook_url." >&2
fi

echo "alertmanager : configuration effective rendue dans $OUT"

[ "$#" -eq 0 ] || exec "$ALERTMANAGER_BIN" "$@"

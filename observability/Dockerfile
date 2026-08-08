# syntax=docker/dockerfile:1
#
# Dockerfile — socle d'observabilité en UNE image.
#
# POURQUOI CETTE IMAGE EXISTE. Le socle est nativement une composition de seize images amont.
# GP-Formuloo veut pouvoir tirer une image et déclarer UN service dans son compose ; c'est ce
# que produit ce fichier. Le dépôt reste la source de vérité : rien n'est recopié ailleurs.
#
# CE QU'ELLE CONTIENT — le pipeline de télémétrie, c'est-à-dire ce dont FT-3 a besoin :
#   OTel Collector · Prometheus · Loki · Tempo · Pyroscope · Grafana · Alertmanager · Alloy
#   et Caddy devant, qui termine le TLS (durcissement §7.4).
#
# CE QU'ELLE NE CONTIENT PAS, ET POURQUOI :
#   · node-exporter        — exige `pid: host` et le montage de `/`. Embarqué, il mesurerait le
#                            conteneur au lieu de l'hôte : autant ne pas mentir. Reste un service
#                            à part si les métriques machine sont voulues.
#   · blackbox-exporter    — sonde depuis l'extérieur ; l'enfermer avec ses cibles ôte son sens.
#   · Uptime Kuma          — le compose du socle le dit lui-même : en production elle se déploie
#                            HORS infrastructure, sinon elle tombe avec ce qu'elle surveille.
#   · GlitchTip + Postgres + Redis + worker
#                          — une application avec sa base. Mettre PostgreSQL dans une image
#                            multi-processus, c'est promettre une durabilité qu'on ne tient pas.
#
# LES VERSIONS NE SONT PAS CHOISIES ICI. Chaque binaire est extrait de l'image amont épinglée par
# le compose du socle : l'image ne peut pas dériver de la plateforme qu'elle emballe.

FROM otel/opentelemetry-collector-contrib:0.116.1 AS collector
FROM prom/prometheus:v3.1.0                       AS prometheus
FROM grafana/loki:3.3.2                           AS loki
FROM grafana/tempo:2.7.0                          AS tempo
FROM grafana/pyroscope:1.10.0                     AS pyroscope
FROM grafana/grafana:11.4.0                       AS grafana
FROM prom/alertmanager:v0.27.0                    AS alertmanager
FROM grafana/alloy:v1.6.1                         AS alloy
FROM caddy:2-alpine                               AS caddy

# BASE GLIBC, ET NON ALPINE — constat, pas préférence. Le binaire `alloy` est construit contre la
# glibc d'Ubuntu 24.04 : sur Alpine il sort en 127 (« command not found », en réalité l'éditeur de
# liens absent). Les sept autres binaires sont des exécutables Go statiques, y compris celui de
# Grafana — vérifié : sous musl, `ldd` répond « Not a valid dynamic program », ce qui signifie
# statique. Une base glibc convient donc à tout le monde ; l'inverse est faux.
FROM ubuntu:24.04

# supervisor : la supervision des huit processus (voir docker/supervisord.conf pour le choix).
# ca-certificates : Caddy et les exportateurs sortent en TLS.
# tzdata : sans elle, les horodatages restent en UTC brut, ce qui fausse la lecture des tableaux
#          de bord — RG-026 exige un rendu dans le fuseau du navigateur.
# wget : utilisé par la sonde de santé, absent de l'image de base.
RUN apt-get update \
 && apt-get install -y --no-install-recommends supervisor ca-certificates tzdata wget \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -g 10001 obs \
 && useradd -u 10001 -g obs -d /var/lib/obs -M -s /usr/sbin/nologin obs

# ── Binaires, extraits des images amont épinglées ────────────────────────────────────────────
COPY --from=collector    /otelcol-contrib          /usr/local/bin/otelcol-contrib
COPY --from=prometheus   /bin/prometheus           /usr/local/bin/prometheus
COPY --from=loki         /usr/bin/loki             /usr/local/bin/loki
COPY --from=tempo        /tempo                    /usr/local/bin/tempo
COPY --from=pyroscope    /usr/bin/pyroscope        /usr/local/bin/pyroscope
COPY --from=alertmanager /bin/alertmanager         /usr/local/bin/alertmanager
COPY --from=alloy        /bin/alloy                /usr/local/bin/alloy
COPY --from=caddy        /usr/bin/caddy            /usr/local/bin/caddy

# Grafana n'est pas un binaire isolé : il lui faut son arborescence (interface web, greffons).
COPY --from=grafana      /usr/share/grafana        /usr/share/grafana

# `promtool` et `amtool` ne sont PAS copiés : ce sont des outils de ligne de commande, inutiles à
# l'exécution, et ils pesaient 160 Mo à eux deux.
#
# Les cartes de source JavaScript de Grafana (334 fichiers, 130 Mo) servent à déboguer le front
# de Grafana lui-même, ce que personne ne fera ici. `strip` sur les binaires ne rapporte rien :
# ils sont déjà construits avec `-s -w`, vérifié — 287,7 Mo avant comme après.
RUN find /usr/share/grafana/public -name '*.map' -delete

# ── Configurations du socle, telles quelles ──────────────────────────────────────────────────
# Elles ne sont pas réécrites pour le conteneur unique : l'entrypoint fait résoudre les noms de
# service vers 127.0.0.1. Les mêmes fichiers servent donc au compose multi-conteneurs.
COPY otel-collector-config.yaml   /etc/otelcol/config.yaml
COPY loki-config.yaml             /etc/loki/config.yaml
COPY tempo-config.yaml            /etc/tempo/config.yaml
COPY docker/alloy-faro.alloy      /etc/alloy/config.alloy
COPY alloy-config.alloy           /etc/alloy/config.amont.alloy
COPY prometheus/                  /etc/prometheus/
COPY alertmanager/                /etc/alertmanager/
COPY grafana/provisioning/        /etc/grafana/provisioning/
COPY docker/Caddyfile             /etc/caddy/Caddyfile
COPY docker/supervisord.conf      /etc/supervisor/supervisord.conf
COPY docker/entrypoint.sh         /usr/local/bin/entrypoint.sh
COPY docker/healthcheck.sh        /usr/local/bin/healthcheck.sh

# Grafana lit son fichier principal ; le provisioning est monté à côté.
# Les configurations du socle inscrivent leurs chemins de données en dur — `path_prefix: /loki`
# dans loki-config.yaml, `/var/tempo/blocks` et `/var/tempo/wal` dans tempo-config.yaml. On crée
# donc CES chemins-là plutôt que de réécrire les fichiers : c'est ce qui garde une seule vérité
# entre le mode compose et le mode image.
# ── Remappage de ports : la seule divergence assumée entre le compose et l'image ──────────────
# En multi-conteneurs, chaque composant a son espace réseau : Tempo peut exposer son récepteur
# OTLP sur 4317 pendant que le Collector écoute AUSSI sur 4317, et Loki, Tempo et Pyroscope
# peuvent tous prendre le port gRPC 9095 de dskit. Dans un conteneur unique, ces trois-là entrent
# en collision et deux d'entre eux meurent au démarrage — constaté, pas supposé.
#
# On remappe donc le strict minimum, avec un garde-fou : si la ligne attendue disparaît d'une
# configuration amont, la construction échoue au lieu de produire une image silencieusement fausse.
#   · Tempo : récepteurs OTLP 4317 → 4327 et 4318 → 4328 ; le Collector suit sur son exportateur.
#     Tempo expose en effet SES PROPRES récepteurs OTLP, sur les mêmes ports que le Collector.
#   · Tempo : port gRPC dskit 9095 → 9096 (Loki garde 9095, Pyroscope prend 9097 par drapeau).
# Le port OTLP du Collector, lui, ne bouge JAMAIS : c'est le contrat des applications.
# Garde-fou sur la configuration d'Alloy : l'image n'embarque que le rôle Faro (pas de socket
# Docker, décision de FT-2). Les quatre blocs repris doivent toujours exister en amont, sinon la
# dérivation est périmée et la construction doit échouer.
RUN set -eu; \
    for bloc in 'faro.receiver "web"' 'loki.process "faro"' 'loki.write "default"' 'otelcol.exporter.otlp "collector"'; do \
      grep -qF "$bloc" /etc/alloy/config.amont.alloy || { echo "AMONT MODIFIE : bloc absent -> $bloc" >&2; exit 1; }; \
    done; \
    rm /etc/alloy/config.amont.alloy

RUN set -eu; \
    test "$(grep -c '0.0.0.0:4317' /etc/tempo/config.yaml)" = "1"; \
    sed -i 's|0.0.0.0:4317|0.0.0.0:4327|' /etc/tempo/config.yaml; \
    test "$(grep -c 'tempo:4317' /etc/otelcol/config.yaml)" = "1"; \
    sed -i 's|tempo:4317|tempo:4327|' /etc/otelcol/config.yaml; \
    test "$(grep -c '0.0.0.0:4318' /etc/tempo/config.yaml)" = "1"; \
    sed -i 's|0.0.0.0:4318|0.0.0.0:4328|' /etc/tempo/config.yaml; \
    test "$(grep -c 'server: { http_listen_port: 3200 }' /etc/tempo/config.yaml)" = "1"; \
    sed -i 's|server: { http_listen_port: 3200 }|server: { http_listen_port: 3200, grpc_listen_port: 9096 }|' /etc/tempo/config.yaml

RUN mkdir -p /etc/grafana \
 && printf '[paths]\nprovisioning = /etc/grafana/provisioning\ndata = /var/lib/obs/grafana\nlogs = /var/log/grafana\nplugins = /var/lib/obs/grafana/plugins\n\n[feature_toggles]\nenable = traceqlEditor\n' > /etc/grafana/grafana.ini \
 && mkdir -p /loki /var/tempo \
             /var/lib/obs/prometheus /var/lib/obs/pyroscope /var/lib/obs/grafana \
             /var/lib/obs/alertmanager /var/lib/obs/alloy /var/lib/obs/caddy /var/log/grafana \
 && chown -R obs:obs /loki /var/tempo /var/lib/obs /var/log/grafana /etc/alertmanager

# Le socle passe DEPLOY_ENV au collector ; sans valeur, le processeur `resource` refuse de se
# construire et le collector meurt au démarrage. Valeur par défaut ici, surchargeable au `run`.
ENV DEPLOY_ENV=prod

# PID 1 démarre en root le temps d'écrire une ligne dans /etc/hosts (voir l'entrypoint), puis
# supervisord bascule immédiatement sur `obs` : aucun des huit processus supervisés ne tourne en
# root. C'est aussi pourquoi Caddy écoute sur 8443/8080 et non sur 443/80.

# 8443/8080 : Caddy, seul point d'entrée en mode durci.
# 4317/4318 : OTLP — les applications de gp-formuloo émettent ici, par le réseau Docker partagé.
# 12347     : réception Faro (RUM navigateur), normalement atteinte via Caddy.
EXPOSE 8443 8080 4317 4318 12347

# Les données qui ne se reconstruisent pas depuis le dépôt.
VOLUME ["/var/lib/obs"]

# La sonde interroge Grafana, Loki, Tempo, Prometheus ET le port OTLP du collector : un conteneur
# ne peut pas se déclarer sain avec la moitié de la chaîne morte.
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

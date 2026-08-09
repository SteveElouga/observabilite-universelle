# Socle d'observabilité mono-serveur

Transcription exécutable de la **§10** du document maître [`../Architecture_Observabilite_Universelle-2.md`](../Architecture_Observabilite_Universelle-2.md) — stack LGT (Loki · Grafana · Tempo) + Prometheus, Pyroscope, GlitchTip, Uptime Kuma, Alertmanager, Alloy et OTel Collector. 100 % gratuit, auto-hébergé.

> ⚠ **Configuration de lab** : ports publiés, pas de TLS ni d'authentification inter-services. Avant toute exposition réelle, appliquer le durcissement **§7.4**, dont une mise en œuvre de référence est fournie dans **`hardening/`** (reverse proxy Caddy TLS, ports dépubliés ; voir `hardening/README.md`).

## Arborescence

```text
observability/
├── docker-compose.yml                 # le socle complet (§10.4)
├── .env.example                       # → cp .env.example .env (jamais commité)
├── otel-collector-config.yaml         # pipeline central (§10.3) — connecteurs AVANT tail sampling
├── alloy-config.alloy                 # logs Docker → Loki + récepteur Faro → Collector
├── prometheus/
│   ├── prometheus.yml
│   ├── targets/                       # cibles OPTIONNELLES, découvertes par fichier (README dédié)
│   │   ├── postgres.yml               # « [] » par défaut ; l'entrypoint les remplit selon
│   │   ├── rabbitmq.yml               #   DATA_SOURCE_NAME / RABBITMQ_METRICS_TARGET /
│   │   ├── keycloak.yml               #   KEYCLOAK_METRICS_TARGET
│   │   └── demo.yml                   # sondes de la démo — vidées hors mode compose
│   └── rules/
│       ├── red.yml                    # alertes RED sur spanmetrics (§10.6)
│       ├── probes.yml                 # alertes de sonde Blackbox (ProbeDown, cert TLS)
│       ├── budgets.yml                # budgets de latence par opération (ENF-01/02)
│       ├── infra.yml                  # remplissage disque, cible injoignable
│       ├── applicatif.yml             # file de rebut, échecs d'authentification, sauvegarde
│       └── (rules-slo.yml)            # SLO multi-burn-rate : généré par sloth, hors Git
├── alertmanager/
│   ├── alertmanager.yml               # receivers Slack + page-oncall (webhook OneUptime)
│   └── secrets/                       # webhooks réels hors Git ; seuls les .example versionnés
│       ├── slack_webhook_url.example
│       └── oneuptime_webhook_url.example
├── loki-config.yaml
├── tempo-config.yaml                  # sans metrics_generator (fait au Collector)
├── blackbox.yml                       # modules de sonde en boîte noire (http_local, http_2xx)
├── uptime-kuma/                       # sonde externe hébergée hors infra (README + compose dédié)
├── oneuptime/                         # astreinte OneUptime hors infra (README : escalade, câblage)
├── hardening/                         # durcissement §7.4 : Caddy TLS, ports dépubliés, backup.sh
├── grafana/provisioning/
│   ├── datasources/datasources.yaml   # LA corrélation : métrique→trace→log→profil (§10.5)
│   ├── dashboards/provider.yaml       # déclaration du dossier « Socle »
│   └── dashboards/socle/              # les 7 dashboards en JSON versionné (§8.3)
│       ├── ensemble.json              #   vue d'ensemble : santé, RED global, saturation
│       ├── service.json               #   par service, sélecteur $service — remplace 5 copies
│       ├── gateway.json               #   opérations exposées + Web Vitals Faro (LogQL)
│       ├── postgres.json              #   connexions, verrous, volumétrie
│       ├── evenements.json            #   débit, arriéré, files de rebut
│       ├── metier.json                #   compteurs applicatifs (convention documentée)
│       └── slo.json                   #   budget d'erreur et vitesse de consommation
├── k6/smoke.js                        # parcours synthétique (§10.7)
└── slo/units-service.yml              # SLO Sloth (§10.6)
```

## Mise en route (§10.9)

| Étape | Action | Vérification |
|---|---|---|
| 0 | `cp .env.example .env` et remplir ; créer `alertmanager/secrets/slack_webhook_url` (copie du `.example` avec le vrai webhook) ; adapter les cibles `example.com` (`prometheus.yml`, `k6/smoke.js`, `GLITCHTIP_DOMAIN` du compose) | — |
| 1 | `docker compose up -d` | `docker compose ps` : tout *healthy* (`glitchtip-migrate` : *exited (0)* — normal, one-shot) |
| 2 | Ouvrir Grafana (`:3000`, admin / `GRAFANA_ADMIN_PASSWORD`) → Explore | Les 4 datasources répondent (Prometheus, Loki, Tempo, Pyroscope) |
| 3 | Démarrer un service instrumenté (§10.1) et générer du trafic | Une trace apparaît dans Tempo |
| 4 | Depuis la trace → « logs de ce span » ; depuis un log → « Voir la trace » | **La corrélation fonctionne dans les deux sens** |
| 5 | Charger le dashboard 1860 (Node Exporter Full), créer l'écran RED (§5) | Exemplars visibles sur les courbes de latence |
| 6 | `sloth generate -i slo/units-service.yml -o prometheus/rules/rules-slo.yml` puis redémarrer Prometheus ; couper le service 2 min | L'alerte burn-rate part vers Slack |
| 7 | Sondes externes hors infra : Uptime Kuma (`uptime-kuma/README.md`) et astreinte OneUptime (`oneuptime/README.md`) | Sonde externe verte ; une alerte `page` ouvre un incident OneUptime |
| 8 | Profiling continu déjà branché sur units-service (Pyroscope, §10.1) ; pour exposer la plateforme, appliquer `hardening/` | Flame graph et saut trace→profil dans Grafana ; accès en TLS derrière Caddy |

Ports : Grafana **3000** · Prometheus **9090** · Alertmanager **9093** · Loki **3100** · Tempo **3200** · Pyroscope **4040** · Collector **4317/4318** · Alloy/Faro **12347** · Uptime Kuma **3001** · GlitchTip **8000**.

## Écarts assumés avec la §10 du document *(correctifs d'exécutabilité, reportés dans le document)*

1. **Webhook Slack en `api_url_file`** — Alertmanager ne substitue pas les variables d'environnement dans sa configuration ; le webhook vit dans `alertmanager/secrets/slack_webhook_url` (hors Git), monté dans le conteneur.
2. **`glitchtip-migrate` + healthcheck Postgres** — sans migrations ni attente de la base, le premier démarrage de GlitchTip échoue ; service one-shot + `depends_on: service_healthy / service_completed_successfully`.
3. **Télémétrie du Collector sur `0.0.0.0:8888`** — depuis les versions récentes, le Collector n'expose ses métriques internes que sur `localhost` ; sans ce réglage, le job Prometheus `otel-collector` (écran 12) ne collecte rien.
4. **Alloy : label `container` + traces Faro via le Collector** — sans relabel, les flux Loki n'ont aucun sélecteur exploitable ; et les traces frontend passent par le Collector (règle §3) pour bénéficier du tail sampling et des métriques dérivées.

## Fait, et ce qui reste

Le backlog initial est terminé : socle, démos instrumentées, alerting RED/SLO, sondes externes, astreinte OneUptime, profiling Pyroscope, durcissement (`hardening/`) et CI de sécurité (`../.github/workflows/ci.yml`). Les **sept dashboards du §8.3 sont désormais provisionnés en code** (`grafana/provisioning/dashboards/`), et les alertes du §8.4 sont écrites : budgets de latence, remplissage disque, cible injoignable, file de rebut, échecs d'authentification, sauvegarde absente. Trois exportateurs entrent dans l'image pour leur donner une source — `node-exporter`, `blackbox-exporter`, `postgres_exporter` — avec les réserves détaillées en tête du `Dockerfile` : embarqué, node-exporter mesure le conteneur, pas la machine.

Trois de ces alertes et deux de ces dashboards dépendent d'un composant que la plateforme n'héberge pas (PostgreSQL, RabbitMQ, Keycloak). Ils restent **muets et non faux** tant qu'aucune adresse n'est fournie : les cibles se découvrent par fichier, et un fichier vide ne déclare rien. Voir `prometheus/targets/README.md`.

Reste, pour la montée en charge : le passage à Kubernetes avec Mimir (§7.2). Détail dans `MEMORY.md`.

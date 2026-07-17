# Socle d'observabilité mono-serveur

Transcription exécutable de la **§10** du document maître [`../Architecture_Observabilite_Universelle-2.md`](../Architecture_Observabilite_Universelle-2.md) — stack LGT (Loki · Grafana · Tempo) + Prometheus, Pyroscope, GlitchTip, Uptime Kuma, Alertmanager, Alloy et OTel Collector. 100 % gratuit, auto-hébergé.

> ⚠ **Configuration de lab** : ports publiés, pas de TLS ni d'authentification inter-services. Avant toute exposition réelle, appliquer le durcissement **§7.4** (prévu : branche `feature/hardening`).

## Arborescence

```text
observability/
├── docker-compose.yml                 # le socle complet (§10.4)
├── .env.example                       # → cp .env.example .env (jamais commité)
├── otel-collector-config.yaml         # pipeline central (§10.3) — connecteurs AVANT tail sampling
├── alloy-config.alloy                 # logs Docker → Loki + récepteur Faro → Collector
├── prometheus/
│   ├── prometheus.yml
│   └── rules/
│       └── red.yml                    # alertes RED (rules-slo.yml : généré par sloth)
├── alertmanager/
│   ├── alertmanager.yml               # webhook Slack via api_url_file
│   └── secrets/
│       └── slack_webhook_url.example  # → créer slack_webhook_url (hors Git)
├── loki-config.yaml
├── tempo-config.yaml                  # sans metrics_generator (fait au Collector)
├── blackbox.yml                       # sondes externes
├── grafana/provisioning/datasources/
│   └── datasources.yaml               # LA corrélation : métrique→trace→log→profil (§10.5)
├── k6/smoke.js                        # parcours scripté (§10.7)
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
| 7 | Configurer Uptime Kuma (`:3001`) + brancher les jobs CI (annotations, source maps — doc CI/CD §10) | Trait « deploy » visible sur les courbes |
| 8 | *(phase 4)* SDK Pyroscope (§10.1) + receiver Alertmanager → OneUptime (§10.6) | Flame graph continu ; escalade jusqu'au téléphone |

Ports : Grafana **3000** · Prometheus **9090** · Alertmanager **9093** · Loki **3100** · Tempo **3200** · Pyroscope **4040** · Collector **4317/4318** · Alloy/Faro **12347** · Uptime Kuma **3001** · GlitchTip **8000**.

## Écarts assumés avec la §10 du document *(correctifs d'exécutabilité, reportés dans le document)*

1. **Webhook Slack en `api_url_file`** — Alertmanager ne substitue pas les variables d'environnement dans sa configuration ; le webhook vit dans `alertmanager/secrets/slack_webhook_url` (hors Git), monté dans le conteneur.
2. **`glitchtip-migrate` + healthcheck Postgres** — sans migrations ni attente de la base, le premier démarrage de GlitchTip échoue ; service one-shot + `depends_on: service_healthy / service_completed_successfully`.
3. **Télémétrie du Collector sur `0.0.0.0:8888`** — depuis les versions récentes, le Collector n'expose ses métriques internes que sur `localhost` ; sans ce réglage, le job Prometheus `otel-collector` (écran 12) ne collecte rien.
4. **Alloy : label `container` + traces Faro via le Collector** — sans relabel, les flux Loki n'ont aucun sélecteur exploitable ; et les traces frontend passent par le Collector (règle §3) pour bénéficier du tail sampling et des métriques dérivées.

## À venir (backlog `MEMORY.md`)

Dashboards RED/USE as-code (provisioning), instrumentation Django (§10.1) et Angular/Faro (§10.2), OneUptime (astreinte, machine séparée), durcissement §7.4.

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
│   ├── prometheus.yml                 # ce que l'image embarque : aucun job propre à un projet
│   ├── scrape.d/demo.yml              # job `blackbox-demo` : compose seulement, hors image
│   ├── targets/                       # cibles OPTIONNELLES, découvertes par fichier (README dédié)
│   │   ├── postgres.yml               # « [] » par défaut ; l'entrypoint les remplit selon
│   │   ├── rabbitmq.yml               #   DATA_SOURCE_NAME / RABBITMQ_METRICS_TARGET /
│   │   ├── keycloak.yml               #   KEYCLOAK_METRICS_TARGET
│   │   ├── application-graphql.yml    # « [] » : passerelle GraphQL du consommateur, activée par
│   │   ├── application-graphql.yml.example  # le profil `application` ou APPLICATION_GRAPHQL_TARGET
│   │   ├── application-http.yml       # autres surfaces HTTP (APPLICATION_PROBE_TARGETS)
│   │   ├── sgfe-graphql.yml.example   # la même, aux étiquettes de SGFE — hors image
│   │   ├── demo.yml                   # « [] » : les sondes de la démo s'activent par profil
│   │   ├── demo.yml.example           #   … depuis ce modèle (profil `demo`) — hors image
│   │   └── (*.local.yml)              # écrits par les profils, ignorés par Git : aucun conteneur
│   │                                  #   n'écrit plus dans un fichier versionné
│   └── rules/
│       ├── red.yml                    # alertes RED sur spanmetrics (§10.6)
│       ├── probes.yml                 # alertes de sonde Blackbox (ProbeDown, cert TLS)
│       ├── budgets.yml                # budgets de latence par opération (ENF-01/02)
│       ├── infra.yml                  # remplissage disque, cible injoignable
│       ├── applicatif.yml             # file de rebut, échecs d'authentification, sauvegarde
│       ├── collecte.yml               # la plateforme se surveille : pertes du Collector,
│       │                              #   notifications d'alerte en échec (écran 12)
│       ├── veilleuse.yml              # « dead man's switch » : son SILENCE est le signal
│       ├── sgfe.yml                   # alertes du CONSOMMATEUR (WhatsApp, crons…) — hors image
│       ├── slo-sgfe.yml               # SLO SGFE multi-burn-rate : GÉNÉRÉ par sloth, et
│       │                              #   VERSIONNÉ — voir « SLO générés » plus bas
│       ├── consommateur/              # VIDE dans l'image : les règles d'un projet observé,
│       │                              #   montées par lui (« Règles d'un consommateur »)
│       └── (rules-slo.yml)            # SLO de la démo : généré par sloth, hors Git
├── alertmanager/
│   ├── alertmanager.yml               # SOCLE de routage — aucune intégration en dur
│   ├── render-config.sh               # écrit la config EFFECTIVE : une intégration n'y entre
│   │                                  #   que si son secret existe (voir plus bas)
│   └── secrets/                       # webhooks réels hors Git ; seuls les .example versionnés
│       ├── slack_webhook_url.example
│       ├── slack_webhook_dette_url.example   # canal séparé pour la dette d'instrumentation
│       ├── oneuptime_webhook_url.example
│       ├── veilleuse_webhook_url.example
│       └── smtp_password.example
├── loki-config.yaml
├── tempo-config.yaml                  # sans metrics_generator (fait au Collector)
├── blackbox.yml                       # modules de sonde (http_local, http_2xx, http_graphql)
├── uptime-kuma/                       # sonde externe hébergée hors infra (README + compose dédié)
├── oneuptime/                         # astreinte OneUptime hors infra (README : escalade, câblage)
├── hardening/                         # durcissement §7.4 : Caddy TLS, ports dépubliés, backup.sh
├── grafana/provisioning/
│   ├── datasources/datasources.yaml   # LA corrélation : métrique→trace→log→profil (§10.5)
│   ├── dashboards/provider.yaml       # déclaration du dossier « Socle » (le seul de l'image)
│   ├── dashboards/sgfe.yaml           # déclaration du dossier « SGFE » — hors image
│   ├── dashboards/socle/              # les 7 dashboards GÉNÉRIQUES en JSON versionné (§8.3)
│   │   ├── ensemble.json              #   vue d'ensemble : santé, RED global, saturation
│   │   ├── service.json               #   par service, sélecteur $service — remplace 5 copies
│   │   ├── gateway.json               #   opérations exposées + Web Vitals Faro (LogQL)
│   │   ├── postgres.json              #   connexions, verrous, volumétrie
│   │   ├── evenements.json            #   débit, arriéré, files de rebut
│   │   ├── metier.json                #   compteurs applicatifs (convention documentée)
│   │   └── slo.json                   #   budget d'erreur et vitesse de consommation
│   └── dashboards/sgfe/               # les écrans du CONSOMMATEUR (compteurs sgfe_*) — hors image
│       ├── metier.json                #   factures, encaissements, parc d'abonnés, campagnes
│       └── exploitation.json          #   canal WhatsApp, présence des composants, sondes, SLO
├── tests/                             # la suite qui prouve tout ce qui précède (voir plus bas)
├── k6/smoke.js                        # parcours synthétique (§10.7)
└── slo/
    ├── regenerer.sh                   # régénère les deux fichiers de règles (sloth épinglé)
    ├── units-service.yml              # SLO Sloth de la démo (§10.6)
    └── sgfe.yml                       # SLO Sloth du consommateur → rules/slo-sgfe.yml
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
| 6 | `sh slo/regenerer.sh` puis redémarrer Prometheus ; couper le service 2 min | L'alerte burn-rate part vers Slack |
| 7 | Sondes externes hors infra : Uptime Kuma (`uptime-kuma/README.md`) et astreinte OneUptime (`oneuptime/README.md`) | Sonde externe verte ; une alerte `page` ouvre un incident OneUptime |
| 8 | Profiling continu déjà branché sur units-service (Pyroscope, §10.1) ; pour exposer la plateforme, appliquer `hardening/` | Flame graph et saut trace→profil dans Grafana ; accès en TLS derrière Caddy |
| 9 | **Vérifier que l'alerte arrive vraiment**, sans attendre le premier incident : `amtool --alertmanager.url=http://localhost:9093 alert add alertname=TestLivraison severity=page` | La notification est reçue ; `docker logs` d'Alertmanager ne montre aucun « Notify for alerts failed » |

Ports : Grafana **3000** · Prometheus **9090** · Alertmanager **9093** · Loki **3100** · Tempo **3200** · Pyroscope **4040** · Collector **4317/4318** · Alloy/Faro **12347** · Uptime Kuma **3001** · GlitchTip **8000**.

## Livraison des alertes : une intégration sans secret n'existe pas

Alertmanager ne lit `url_file` / `api_url_file` **qu'au moment de notifier**. Une intégration
dont le secret manque passe donc `amtool check-config`, démarre verte… et échoue à chaque
alerte (« notify retry canceled due to unrecoverable error … no such file or directory ») —
1 447 notifications perdues en 72 h avant correction, sans que rien ne le signale.

D'où le détour par **`alertmanager/render-config.sh`** : `alertmanager.yml` est un *socle* sans
aucune intégration en dur, et le script produit la configuration effective en n'y insérant que
les canaux dont le secret existe **et n'est pas vide**. Pas de secret, pas d'intégration ; zéro
échec de notification. Ce qui est branché, et ce qui ne l'est pas, est annoncé au démarrage.

| Canal | Secret / variables | Effet s'il manque |
|---|---|---|
| Slack | `secrets/slack_webhook_url` | aucun `slack_configs` écrit |
| Astreinte OneUptime | `secrets/oneuptime_webhook_url` | aucun `webhook_configs` sur `page-oncall` |
| E-mail de secours | `secrets/smtp_password` **et** `ALERT_EMAIL_TO`/`_FROM`/`ALERT_SMTP_SMARTHOST` | aucun `email_configs` |
| Dette d'instrumentation | `secrets/slack_webhook_dette_url` | repli sur le webhook principal, une fois par semaine |
| Veilleuse | `secrets/veilleuse_webhook_url` | le récepteur `veilleuse` n'envoie rien |

**Quatre gravités, quatre destins.** `page` → astreinte (Slack + e-mail + OneUptime, rappel
toutes les heures) ; `ticket` → Slack, une fois par jour ; `veilleuse` → surveillant externe,
toutes les 5 minutes ; **`dette`** → canal de dette technique, **une fois par semaine**. Cette
dernière existe parce que deux règles déclarent volontairement un trou d'instrumentation du
dépôt observé — `SauvegardeJamaisDeclaree`, `SGFECronsNonInstrumentes` — et sont donc vraies en
permanence jusqu'à ce qu'il soit comblé. On ne les supprime pas (une surveillance qui ne peut
pas se déclencher rassure à tort), mais elles n'ont rien à faire dans le canal d'incident :
laissées en `ticket`, elles y revenaient toutes les 24 h, c'est-à-dire le bruit récurrent que
C-354 venait de nettoyer. Chacune porte une annotation `suivi` avec le constat d'origine et une
**échéance de revue** (15/12/2026) : passé cette date, on tranche — instrumenter, ou retirer la
règle — plutôt que de laisser une alerte se répéter indéfiniment.

Deux garde-fous complètent le dispositif : la règle **`ChaineAlertingVivante`**
(`prometheus/rules/veilleuse.yml`) est active en permanence et doit parvenir toutes les
5 minutes à un surveillant externe — **son silence est le signal** ; et la règle
**`NotificationsDAlerteEnEchec`** (`prometheus/rules/collecte.yml`) surveille
`alertmanager_notifications_failed_total`, que plus personne ne peut ignorer puisque
Alertmanager est désormais scruté par Prometheus.

## Règles d'un consommateur

L'image est universelle : elle n'embarque **aucune** règle propre à un projet observé. Un
consommateur qui veut alerter sur ses propres séries (publiées par OTLP ou déposées dans le
répertoire textfile de node-exporter) monte ses fichiers dans
**`/etc/prometheus/rules/consommateur/`**, que `prometheus.yml` charge en plus de `rules/*.yml` :

```yaml
  observabilite:
    image: nyobeelouga5/observabilite:<version>
    volumes:
      - ./observabilite/regles:/etc/prometheus/rules/consommateur:ro   # *.yml seulement
```

- **Un fichier seul se monte en mode image**, pas en mode compose du socle : là, `./prometheus`
  est déjà monté en `:ro` et Docker ne peut pas y créer le point de montage d'un fichier
  (« make mountpoint … read-only file system », constaté). Monter alors un **dossier**, dont le
  point de montage existe dans le dépôt.
- **Le répertoire est vide dans l'image**, et un motif sans fichier ne déclare rien : une
  installation qui ne monte rien démarre comme avant. Un fichier invalide, lui, fait refuser
  la configuration à Prometheus — on le voit au démarrage, pas à la première panne.
  `tests/test_configurations.py` prouve les trois cas (chargé, refusé, vide).
- **Un fichier ajouté ou modifié n'est relu qu'au redémarrage** du conteneur : Prometheus ne
  surveille pas ses fichiers de règles, et `/-/reload` est fermé (pas de `--web.enable-lifecycle`).
- **Le contrat d'acheminement est celui des règles du socle**, et rien d'autre n'est routé
  à dessein. Vérifié par `amtool config routes test` : `severity="warning"` et
  `severity="critical"` tombent tous deux sur la route par défaut (Slack, rappel toutes les
  4 h) — un `critical` n'atteint donc **jamais** l'astreinte. Pour être acheminée comme les
  autres, une règle de consommateur porte :

  | Élément | Valeurs | Pourquoi |
  |---|---|---|
  | étiquette `severity` | `page`, `ticket` ou `dette` | seule clé de routage (voir « Quatre gravités, quatre destins ») |
  | étiquette `service_name` | nom du service | regroupement (`group_by`) et inhibition d'un `ticket` par une `page` du même service ; une valeur gabarit (`"{{ $labels.service }}"`) convient |
  | annotations `summary`, `description` | texte | seules lues par le gabarit Slack (`render-config.sh`) |
  | annotation `runbook_url` | URL | rendue en lien « Que faire » ; une annotation `runbook` en texte libre n'est **pas** affichée |

- **Testez vos règles chez vous**, avec `promtool test rules` et la même image
  (`prom/prometheus:v3.1.0`) : la plateforme ne connaît pas vos séries et ne peut pas le faire
  à votre place.

## Conservation par signal

Chaque durée est choisie et écrite, aucune n'est héritée d'un défaut.

| Signal | Durée | Où | Pourquoi |
|---|---|---|---|
| Journaux (Loki) | **90 j** | `loki-config.yaml` : `limits_config.retention_period: 2160h` **et** bloc `compactor` | politique de conservation des journaux du consommateur, minimum d'une période d'observation SOC 2 Type II |
| Traces (Tempo) | **30 j** | `tempo-config.yaml` : `block_retention: 720h` | couvre le cycle de facturation mensuel ; les traces coûtent bien plus cher au stockage que les journaux |
| Métriques (Prometheus) | **90 j**, plafonnées à 20 Go | `docker-compose.yml` : `--storage.tsdb.retention.time` / `.size` | même horizon que les journaux, borné pour ne pas remplir le disque |

⚠ Le point qui se paie cher : `retention_period` **seul ne fait rien**. Sans bloc `compactor`
avec `retention_enabled: true` et `delete_request_store`, « the logs sent to Loki live
forever » (documentation Loki). La rétention exige en outre une période d'index de 24 h.
Contrôle : `curl :3100/config | grep -A3 compactor`, ou la suite `tests/`.

## Opérations GraphQL : une dimension bornée

Une API GraphQL reçoit tout sur `POST /graphql`. Le serveur qui suit la convention OpenTelemetry pose `graphql.operation.type` et `graphql.operation.name` sur son span et le renomme `{type} {nom}` ; `spanmetrics` en fait deux dimensions, et le tableau « Gateway et expérience utilisateur » ventile latence, débit et erreurs par opération. Mais le nom vient du **client** : un nom forgé à chaque appel ouvrirait une série par appel. La version 0.116.1 du Collector n'a pas `aggregation_cardinality_limit` ; c'est donc `transform/operations_bornees` qui borne, sur le seul pipeline des métriques (Tempo garde le nom réel).

| `GRAPHQL_OPERATIONS_CONNUES` | Effet |
|---|---|
| Posée, par exemple `ListerCommandes\|CreerCommande` | Liste blanche : une expression RE2 que la configuration ancre par `^(?:…)$`. Seuls ces noms deviennent des séries, tout autre devient `autre`. |
| Absente **ou vide** (défaut) | Tout nom devient `autre` : le tableau ne ventile que par type (`query autre`, `mutation autre`). Une valeur vide, celle que relaie `${GRAPHQL_OPERATIONS_CONNUES:-}`, vaut une absence. |

Pour voir ses opérations, un consommateur déclare donc les noms qu'il émet. Une ligne `autre` qui grossit dans le tableau signale une opération à déclarer ou un client qui forge des noms.

## Image neutre : ce que la plateforme publiée ne porte pas

L'image `nyobeelouga5/observabilite` est **universelle** : tout consommateur la tire, et aucun ne
doit y voir le nom d'un autre. Jusqu'à la 1.1.7 elle embarquait pourtant, en préprod d'un autre
projet, un dossier Grafana « SGFE », des alertes et SLO `sgfe_*`, des jobs `blackbox-sgfe-*` et
un job `blackbox-demo` visant des conteneurs de ce seul dépôt. Depuis le 04/10/2026 :

- **Les sondes de l'application** s'appellent `blackbox-application-graphql` et
  `blackbox-application-http`, réglées par `APPLICATION_GRAPHQL_TARGET` et
  `APPLICATION_PROBE_TARGETS` (voir `prometheus/targets/README.md`). L'étiquette `role` vaut
  `application`.
- **Tout fichier propre à SGFE reste dans le dépôt mais hors de l'image** : `.dockerignore`
  écarte tout nom contenant `sgfe` (règles `sgfe.yml` et `slo-sgfe.yml`, `dashboards/sgfe/` et
  sa déclaration `dashboards/sgfe.yaml`, `targets/sgfe-*`). Le compose les monte toujours.
- **La démonstration sort de l'image** : le job `blackbox-demo` vit dans
  `prometheus/scrape.d/demo.yml` (lu par `scrape_config_files`, motif vide accepté) et ses
  cibles `targets/demo*` sont écartées. `DEMO_TARGETS` n'a plus d'effet en mode image ; en
  compose, `--profile demo` fonctionne comme avant.
- **Aucun commentaire embarqué** ne nomme un projet consommateur (« le projet consommateur »).
  Preuve : `tests/test_configurations.py` reconstruit les `COPY` du Dockerfile sur une base
  minimale, avec le vrai `.dockerignore`, et y cherche le nom de chaque consommateur connu.

**Migration — les anciens noms ne sont PAS lus par l'image.** `SGFE_GRAPHQL_TARGET` et
`SGFE_PROBE_TARGETS` disparaissent de l'entrypoint : les y garder comme alias aurait écrit le
nom du projet dans l'image, c'est-à-dire le défaut même qu'on retire. Aucun déploiement connu
ne les pose (relevé le 04/10/2026 dans les compose et `.env` des projets du poste). Qui les
utilisait renomme la variable, ou la relaie dans son propre compose :
`APPLICATION_GRAPHQL_TARGET: ${SGFE_GRAPHQL_TARGET}`. Le compose **de ce dépôt**, qui n'entre
pas dans l'image, garde le repli : profil `sgfe` (alias de `application`) et
`SGFE_GRAPHQL_TARGET` lu si `APPLICATION_GRAPHQL_TARGET` est vide. Les tableaux SGFE suivent
le renommage des jobs (`job=~"blackbox-application-.*"`).

## Mémoire et redémarrage : deux moitiés d'une même protection

Le 12/09/2026, **Loki, Tempo et Pyroscope sont sortis en code 137 (OOMKilled) et sont restés
arrêtés trois jours** : aucun journal, aucune trace, aucun profil, et personne pour s'en
apercevoir — parce qu'aucun service durable ne portait de politique de redémarrage. C'est la
panne la plus coûteuse de tout ce dossier : elle rend muet l'ensemble de ce que la plateforme
sait faire, y compris ses propres alertes de perte de télémétrie.

Deux réglages, indissociables :

| Réglage | Ce qu'il fait | Ce qu'il ne fait **pas** |
|---|---|---|
| `mem_limit` | **plafond par conteneur** : fait tuer celui qui dérape avant que le noyau ne choisisse lui-même sa victime | il ne **réserve** rien, et il ne fait **revenir** personne |
| `restart: unless-stopped` | relance après une mort accidentelle **et** au redémarrage du démon ; « restarts the container irrespective of the exit code but stops restarting when the service is stopped or removed » ([docs.docker.com](https://docs.docker.com/reference/compose-file/services/)) | il n'empêche pas la mort, il en borne la durée |

Poser un plafond sans reprise n'avance que l'heure de la mort. **Tous** les services durables
portent donc `restart: unless-stopped` ; seuls les trois one-shot (`demo-targets`,
`application-targets`, `glitchtip-migrate`) gardent `restart: "no"`, les relancer en boucle n'ayant
aucun sens. Un `docker compose stop` explicite reste respecté — c'est la différence avec
`always`, et la raison du choix.

**Ordre de grandeur à surveiller avant de toucher aux plafonds.** Leur somme vaut ≈ 6,5 Gio
(768 Mio Collector + 2 Gio Prometheus + 1 Gio × 3 pour Loki/Tempo/Pyroscope + 512 Mio Alloy +
256 Mio Alertmanager) pour une VM Docker de **7,75 Gio** sur le poste de recette, partagée avec
une quarantaine de conteneurs SGFE. Comme un plafond ne réserve rien, l'OOM killer de l'hôte
frappe malgré eux dès que la somme des consommations **réelles** dépasse la VM : la reprise
automatique borne alors l'incident à quelques secondes, mais seule une VM correctement
dimensionnée (Docker Desktop → *Settings* → *Resources*) le fait disparaître.

**Ce qui le dit, désormais.** Pyroscope n'était scruté par rien (il ne pousse pas de métriques)
et ne figurait dans aucune sonde : sa mort était invisible par construction. Il est ajouté au
job `blackbox-platform` (`/ready`), aux côtés d'Alertmanager. `CibleInjoignable` et `ProbeDown`
couvrent le reste.

## SLO générés : livrés, et vérifiés

Deux artefacts Sloth cohabitent avec deux traitements **différents**, et c'est délibéré :

| Fichier | Statut | Pourquoi |
|---|---|---|
| `prometheus/rules/rules-slo.yml` (démo) | **git-ignoré** | ne concerne que qui lance le profil `demo`, et peut le régénérer |
| `prometheus/rules/slo-sgfe.yml` (consommateur) | **versionné** | sans lui, une installation sans binaire `sloth` n'a aucun SLO SGFE et les écrans « budget d'erreur » restent vides sans que rien ne le dise |

Versionner un artefact généré crée deux sources de vérité : rien n'empêcherait `slo/sgfe.yml`
de diverger des règles réellement chargées. D'où **`slo/regenerer.sh`**, qui régénère les deux
depuis l'image officielle épinglée (`ghcr.io/slok/sloth:v0.16.0` — un binaire local d'une autre
version produirait une dérive à chaque exécution), et la porte
`tests/test_tableaux_de_bord.py::SLOGeneresEtVersionnes`, qui **échoue si le fichier versionné
ne correspond plus à sa source**. Même principe que le `generated.ts` du frontend : livré, et
gardé par un test.

## Écarts assumés avec la §10 du document *(correctifs d'exécutabilité, reportés dans le document)*

1. **Webhook Slack en `api_url_file`, inséré au rendu** — Alertmanager ne substitue pas les variables d'environnement dans sa configuration ; le webhook vit dans `alertmanager/secrets/slack_webhook_url` (hors Git), monté dans le conteneur, et n'entre dans la configuration effective que s'il existe (voir « Livraison des alertes »).
2. **`glitchtip-migrate` + healthcheck Postgres** — sans migrations ni attente de la base, le premier démarrage de GlitchTip échoue ; service one-shot + `depends_on: service_healthy / service_completed_successfully`.
3. **Télémétrie du Collector sur `0.0.0.0:8888`** — depuis les versions récentes, le Collector n'expose ses métriques internes que sur `localhost` ; sans ce réglage, le job Prometheus `otel-collector` (écran 12) ne collecte rien.
4. **Alloy : `service_name` = nom de service Compose, et traces Faro via le Collector** — le label `container` seul ne suffit pas : Loki dérive alors `service_name` du nom de CONTENEUR (`sgfe-backend-gateway-1`) alors que traces et métriques portent l'`OTEL_SERVICE_NAME` (`gateway`), et le bouton « logs de ce span » ne rend aucun flux. `discovery.relabel` promeut donc le nom de service Compose, et le pipeline Faro reprend `app_name`. Les traces frontend passent par le Collector (règle §3) pour bénéficier du tail sampling et des métriques dérivées.
5. **`deployment.environment` en `insert`, jamais en `upsert`** — le Collector ne doit pas écraser l'environnement déclaré par un SDK, sous peine d'étiqueter `prod` toute la télémétrie de développement. La clé stable de la convention sémantique est `deployment.environment.name` ; l'ancienne reste alimentée le temps de la migration. ⚠ **Effet de bord à connaître de l'exploitation** : `resource_to_telemetry_conversion` reporte ces attributs en étiquettes, donc au premier redéploiement après ce changement, toute série qui portait `deployment_environment="prod"` à tort change d'identité et gagne `deployment_environment_name`. Les `rate()` / `increase()` verront **une** discontinuité, une seule fois. C'est le prix de la correction, pas un défaut — mais il vaut mieux le lire ici que le découvrir sur un graphique.
6. **Périmètre de collecte des journaux** — `discovery.docker` voit *tous* les conteneurs du démon. `LOGS_COMPOSE_PROJECTS` (défaut `.+`) borne l'ingestion aux projets Compose voulus : sans lui, les conteneurs d'autres projets finissent dans un Loki mono-tenant et sans authentification.

## Fait, et ce qui reste

Le backlog initial est terminé : socle, démos instrumentées, alerting RED/SLO, sondes externes, astreinte OneUptime, profiling Pyroscope, durcissement (`hardening/`) et CI de sécurité (`../.github/workflows/ci.yml`). Les **sept dashboards du §8.3 sont désormais provisionnés en code** (`grafana/provisioning/dashboards/`), et les alertes du §8.4 sont écrites : budgets de latence, remplissage disque, cible injoignable, file de rebut, échecs d'authentification, sauvegarde absente. Trois exportateurs entrent dans l'image pour leur donner une source — `node-exporter`, `blackbox-exporter`, `postgres_exporter` — avec les réserves détaillées en tête du `Dockerfile` : embarqué, node-exporter mesure le conteneur, pas la machine.

Trois de ces alertes et deux de ces dashboards dépendent d'un composant que la plateforme n'héberge pas (PostgreSQL, RabbitMQ, Keycloak). Ils restent **muets et non faux** tant qu'aucune adresse n'est fournie : les cibles se découvrent par fichier, et un fichier vide ne déclare rien. Voir `prometheus/targets/README.md`.

Le générique ne dispense pas du spécifique, et c'est la leçon de la revue du 14/09/2026 : une
plateforme peut être irréprochable et ne rien dire de l'application qu'elle observe. Le projet
consommateur a donc ses propres règles (`prometheus/rules/sgfe.yml`), ses propres SLO
(`slo/sgfe.yml`) et ses propres écrans (`grafana/provisioning/dashboards/sgfe/`), à côté du
socle et sans le modifier. Deux alertes y **déclarent un trou d'instrumentation** au lieu de
rester silencieuses — `SGFECronsNonInstrumentes`, `SauvegardeJamaisDeclaree` : une surveillance
qui ne peut pas se déclencher est pire que pas de surveillance, parce qu'elle rassure. Elles
sont routées en `severity: dette`, hors du canal d'incident et une fois par semaine, avec une
échéance de revue au 15/12/2026 — visibles sans redevenir du bruit (voir « Livraison des
alertes »).

## Tests

`tests/` prouve tout ce qui précède **en faisant lire chaque fichier par le binaire qui
l'exécutera** (promtool, amtool, `loki -verify-config`, `otelcol validate`, `alloy run`,
`blackbox_exporter --config.check`, `docker compose config`) puis en vérifiant le comportement
obtenu : une vraie alerte poussée dans un vrai Alertmanager atteint-elle un destinataire ;
la rétention est-elle *effective* dans `/config` ; Alloy pose-t-il le bon `service_name` ;
Loki accepte-t-il les requêtes des tableaux de bord. Cette exigence vient d'un constat : tous
les défauts corrigés ici passaient la validation statique.

Trois preuves valent d'être connues, parce qu'elles n'existaient sous aucune autre forme :
l'incident du 12/09 est **rejoué** (un conteneur plafonné à 32 Mio qui en réclame 256 ; sans
politique il meurt en 137 et personne ne le relève, avec `unless-stopped` il revient seul) ; les
deux services d'activation des sondes sont **exécutés** dans un répertoire jetable, et chaque
fichier qu'ils écrivent doit être ignoré par Git *et* relu par un job Prometheus ; et
`slo-sgfe.yml` est **régénéré** par l'image Sloth épinglée puis comparé octet pour octet.

```sh
cd observability/tests && python3 -m unittest discover -v     # Docker requis, ~9 min
```

Reste, pour la montée en charge : le passage à Kubernetes avec Mimir (§7.2). Détail dans `MEMORY.md`.

<!-- GOUVERNANCE — Fichier n°3 de l'ordre de lecture (README.md → CONTEXT.md → MEMORY.md). Mémoire évolutive : TOUTE session met à jour « État courant » et ajoute une entrée de journal AVANT de terminer (règle R11). Journal en ordre antéchronologique (le plus récent en haut). -->

# MEMORY — État courant, backlog & journal

## État courant *(à maintenir à jour à chaque session)*

- **Étape** : **#1/#3/#4/#5 mergés dans `develop`** (#5 mergé le 20/07/2026). **#6 (sondes externes) validé de bout en bout** sur `feature/uptime-externe` ; reste rebase sur `develop` + MR.
- **Branches** : `develop` = #1..#5 (rafraîchir en local par `git pull` ; le bac à sable est resté à `3892fc8`, sans réseau GitHub). `main` au bootstrap. `feature/uptime-externe` **créée depuis `feature/alerting-slo`** (chaînage pour garder MEMORY linéaire) — à **rebaser sur `develop`** : `git rebase --onto develop feature/alerting-slo feature/uptime-externe`.
- **Prochaine action** : sur le Mac, `git pull` develop, rebaser #6, push + MR #6 → `develop`. Ensuite #7 (astreinte OneUptime) ou enabler gitleaks. Pas de CI (R8 « CI verte » plus tard).
- **Remote GitHub** : **configuré** — `github.com/SteveElouga/observabilite-universelle` (privé), 4 branches publiées.
- **Point de vigilance** : Grafana OnCall est archivé (24/03/2026) — l'astreinte cible est OneUptime (phase 4) ; ne pas réintroduire OnCall.
- **Particularité du pont cloud→Mac** : la suppression de fichiers y est impossible → les verrous Git périmés sont **déplacés** dans `.git/_stale_locks/` au lieu d'être supprimés. Purger de temps en temps depuis le Mac : `rm -rf .git/_stale_locks`.

## Backlog ordonné *(une ligne = une future branche = une MR)*

| # | Travail | Branche prévue | Réf. document |
|---|---|---|---|
| 1 | ✅ **Fait (17/07/2026)** — Socle mono-serveur : arborescence `observability/` complète (compose LGT + Pyroscope + GlitchTip + Uptime Kuma, configs Collector/Prometheus/Loki/Tempo, datasources corrélées, règles RED, SLO Sloth, Alertmanager, blackbox, k6, `.env.example`). Committé, en attente de MR. | `feature/observability-socle` | §10.3–§10.7 |
| 2 | Démarrage & recette : `.env` réel (jamais commité), secret Slack (`alertmanager/secrets/`), `docker compose up`, vérifications §10.9 étapes 1–5 (corrélation aller-retour, exemplars) | *(même branche que #1 ou `fix/…`)* | §10.9 |
| 3 | ✅ **Fait (19/07/2026)** — Instrumentation Django `units-service` (`demo/units-service/`, profil compose `demo`). Recette validée dans Grafana : métrique `commandes_creees_total` (Prometheus), logs JSON avec `trace_id` (Loki), traces (Tempo). Correctif clé : `DJANGO_SETTINGS_MODULE` en env (avant `opentelemetry-instrument`). | `feature/otel-django` | §10.1 |
| 4 | ✅ **Fait (19/07/2026)** — Frontend Angular `mir-webapp` (`demo/mir-webapp/`, profil `demo`, port 8090) : Faro (RUM Web Vitals + traces, propagation W3C) + erreurs via `ErrorHandler` Angular → `faro.api.pushError` (+ GlitchTip si DSN). nginx proxifie `/api` (anti-CORS). Recette validée : RUM et erreurs dans Loki (`{source="faro"}`), trace corrélée navigateur→`units-service` dans Tempo. Branche depuis `feature/otel-django` (dépend de #3). | `feature/faro-angular` | §10.2 |
| 5 | ✅ **Fait (19/07/2026)** — Alerting réel : règles RED et SLO **réalignés sur les spanmetrics** (`traces_span_metrics_calls_total` / `_duration_milliseconds`, car units-service émet `http_server_duration_milliseconds` et non `..._request_duration_seconds`). Endpoint `/demo/erreur` (500) ajouté à units-service. **Recette validée de bout en bout** : `sloth generate` → règles chargées dans Prometheus (RED + SLO multi-burn-rate), erreurs provoquées → `HighErrorRate` Pending + `UnitsServiceAvailability` Firing → Alertmanager → **Slack `#alertes`**. Reste : MR vers `develop`. | `feature/alerting-slo` | §10.6 |
| 6 | 🔄 **En cours** — Sondes externes. Blackbox : module `http_local` (sans SSL) + cibles réelles (santé plateforme grafana/prometheus/loki/tempo + endpoints démo), gabarit HTTPS prod commenté. Alertes de sonde (`prometheus/rules/probes.yml` : ProbeDown, ProbeSlow, cert TLS). `k6/smoke.js` réécrit sur la démo locale. Uptime Kuma : pattern **hors infra** documenté (`uptime-kuma/README.md` + `docker-compose.external.yml`), service in-compose marqué dev-only. **Recette validée** (k6 100 % vert, p95 14 ms ; 6 cibles Blackbox UP). Reste : rebase + MR. | `feature/uptime-externe` | §10.7, §7.5 |
| 7 | Phase 4 — astreinte : OneUptime (machine séparée) + receiver webhook Alertmanager | `feature/oneuptime` | §4.11, §10.6 |
| 8 | Phase 4 — profiling : SDK Pyroscope Django + lien trace→profil (`pyroscope-otel`) | `feature/pyroscope-sdk` | §10.1, §10.5 |
| 9 | Durcissement avant exposition : reverse proxy TLS, auth, ports non publiés, secrets | `feature/hardening` | §7.4 |
| 10 | CI/CD : annotations de déploiement + upload source maps + Renovate | `feature/cicd-hooks` | doc CI/CD §10 |

## Décisions & exceptions consignées

| Date | Type | Détail |
|---|---|---|
| 2026-07-17 | Décision | Révision du document maître : OneUptime (astreinte), span-metrics au Collector avant échantillonnage, Pyroscope au compose, §7.4/§7.5/§9.4 ajoutées. Validée par Steve via questionnaire (4 questions, options recommandées retenues). |
| 2026-07-17 | Décision | Démarche **pas à pas** versionnée **GitHub** ; cadrage d'abord, implémentation ensuite. Règles Git R1–R13 adoptées (`README.md`). |
| 2026-07-17 | **Exception unique** | Commit de bootstrap effectué **directement sur `main`** (dépôt vide : `develop` ne pouvait pas encore exister). Portée : ce seul commit initial. Toute modification ultérieure de `main`/`develop` passe par MR (R2, R4, R6). |

## Journal *(antéchronologique — ajouter chaque nouvelle entrée EN HAUT)*

### 2026-07-20 — Session Claude : #5 validé de bout en bout + backlog #6 (sondes externes)
- **#5 recette complète sur le Mac** : `sloth generate` → Prometheus charge `service-red` (red.yml) **et** `sloth-slo-alerts-units-service-requests-availability` (rules-slo.yml). Erreurs via `/demo/erreur` → `HighErrorRate` Pending (100 % de spans en erreur) et `UnitsServiceAvailability` **Firing** → Alertmanager (receiver `slack`) → **Slack `#alertes`** (`[FIRING:1] UnitsServiceAvailability`). Chaîne d'alerting bout en bout OK. Reste : MR `feature/alerting-slo` → `develop`.
- **Détail SLO** : l'alerte page Sloth exige deux fenêtres (5m **et** 1h) au-dessus du seuil ; à 100 % d'erreurs les deux passent d'emblée, d'où un firing quasi immédiat. En dégradation réaliste (quelques %), elle serait plus lente que `HighErrorRate` (`for: 5m`).
- **#6 démarré** sur `feature/uptime-externe` (depuis `feature/alerting-slo`, choix « tout est encore local » via questionnaire).
  - **Blackbox** : ajout du module `http_local` (sans `fail_if_not_ssl`, les cibles internes sont en HTTP) ; `http_2xx` (SSL) conservé pour la prod. `prometheus.yml` : cibles fictives `example.com` remplacées par deux jobs réels — `blackbox-platform` (grafana/prometheus/loki/tempo, toujours actifs) et `blackbox-demo` (units-service `/sante/`, mir-webapp). Job HTTPS `blackbox-public` laissé commenté comme gabarit prod.
  - **Alertes de sonde** : `prometheus/rules/probes.yml` (ProbeDown `probe_success==0`, ProbeSlow `probe_duration_seconds>1`, ProbeSSLCertExpiringSoon pour les cibles HTTPS). Chargé via `rule_files: rules/*.yml`.
  - **k6** : `k6/smoke.js` réécrit sur la démo locale (`BASE_URL` paramétrable, défaut `http://localhost:8088`, exerce `/sante/` + `/demo/commande`). Câblage CI reporté au #10.
  - **Uptime Kuma hors infra** : `uptime-kuma/README.md` (pourquoi hors infra = dead man's switch, où l'héberger, moniteurs, notif Slack) + `uptime-kuma/docker-compose.external.yml` (Kuma autonome sur machine séparée). Service in-compose annoté **dev-only**.
- **Recette #6 validée sur le Mac** : `k6 run k6/smoke.js` → 590/590 checks OK, p95 13,8 ms, 0 % d'erreur. Puis les 6 cibles Blackbox UP (`blackbox-platform` 4/4, `blackbox-demo` 2/2). **Piège** : après modif de `blackbox.yml`, il faut `docker compose restart blackbox-exporter` — sinon l'exporteur garde l'ancienne config sans le module `http_local` et répond 400 « Unknown module » (Prometheus seul redémarré ne suffit pas). ProbeDown non rejoué : même routage Alertmanager→Slack que #5, déjà prouvé.
- **Reste** : `git rebase --onto develop feature/alerting-slo feature/uptime-externe` **après** le merge de #5, puis MR #6.

### 2026-07-19 — Session Claude : backlog #5 — alerting réel + SLO (règles RED/SLO)
- Branche `feature/alerting-slo` depuis `develop` (`3892fc8`, avec #1/#3/#4 mergés).
- **Découverte** : units-service émet `http_server_duration_milliseconds` (pas `http_server_request_duration_seconds` du socle), plus les spanmetrics `traces_span_metrics_calls_total` / `_duration_milliseconds`. Les règles RED et SLO du socle n'auraient donc jamais eu de données.
- **Correctif** : `red.yml` et `slo/units-service.yml` réécrits sur les **spanmetrics** (source RED canonique, §10.3) : erreurs via `status_code="STATUS_CODE_ERROR"`, latence via `traces_span_metrics_duration_milliseconds_bucket` (seuil en ms, pas en s). Endpoint `/demo/erreur` (HTTP 500 → span en erreur) ajouté à units-service pour tester.
- **Recette validée sur le Mac (bout en bout)** : `sloth generate -i slo/units-service.yml -o prometheus/rules/rules-slo.yml` (binaire sloth installé) → `docker compose restart prometheus`. Prometheus charge le groupe `service-red` (RED, red.yml) **et** `sloth-slo-alerts-units-service-requests-availability` (SLO multi-burn-rate, rules-slo.yml). Erreurs provoquées via `/demo/erreur` : `HighErrorRate` passe en **Pending** (100 % de spans en erreur, `for: 5m`) et `UnitsServiceAvailability` en **Firing** (burn rate à 100 % » budget 0,1 %, fenêtres courte et longue franchies d'emblée). L'alerte remonte à **Alertmanager** (receiver `slack`, labels Sloth) puis à **Slack `#alertes`** : `[FIRING:1] UnitsServiceAvailability`.
- Détail SLO : l'alerte page Sloth exige les deux fenêtres (5m **et** 1h) au-dessus du seuil pour éviter les faux positifs ; à 100 % d'erreurs, les deux passent tout de suite, d'où un firing quasi immédiat. En dégradation réaliste (quelques %), elle serait plus lente que `HighErrorRate`.
- `rules-slo.yml` reste un **artefact généré** (git-ignoré) : à régénérer par `sloth generate` sur chaque cible, jamais commité.
- Reste : pousser `feature/alerting-slo` + MR → `develop`.

### 2026-07-19 — Session Claude : recette mir-webapp (backlog #4 validé)
- Recette Docker de `mir-webapp` sur le Mac (`docker compose --profile demo up -d --build`). L'app Angular compile et tourne du premier build.
- Deux correctifs de recette sur `feature/faro-angular` :
  - **Label Loki** : le récepteur Faro écrivait sans label filtrable → ajout d'un `loki.process` posant `source="faro"` dans `alloy-config.alloy`. Les événements RUM se filtrent via `{source="faro"}`.
  - **Erreurs Angular** : Angular intercepte les erreurs dans sa zone, le gestionnaire par défaut de Faro ne les voit pas → `ObservabilityErrorHandler` qui pousse via `faro.api.pushError` (et Sentry/GlitchTip si DSN).
- **Validé dans Grafana** : `{source="faro"}` montre Web Vitals + fetch ; `kind=exception` montre l'erreur JS avec stack trace ; Tempo Search sur `units-service`/`mir-webapp` montre une trace unique avec les deux services (corrélation navigateur→Django).
- Détail : le tail sampling du Collector ne garde qu'environ 10 % des traces rapides, donc chercher une trace par ID au hasard renvoie souvent 404 ; utiliser la recherche par service dans Tempo.

### 2026-07-19 — Session Claude : backlog #4 — frontend Angular mir-webapp (Faro + GlitchTip)
- Création de `demo/mir-webapp/` : app Angular 18 (standalone) instrumentée §10.2. Faro Web SDK (Web Vitals, erreurs JS, `TracingInstrumentation` avec propagation W3C) + GlitchTip via `@sentry/angular` (initialisé seulement si un DSN est fourni). Composant démo : bouton « appeler le backend » (trace propagée) + bouton « erreur JS ».
- Config Angular modelée sur celle, éprouvée, du frontend Formuloo (builder `application`, tsconfig ES2022). Dockerfile multi-stage (build Node → nginx). nginx sert l'app et **proxifie `/api` vers `units-service`** (même origine, pas de CORS, `traceparent` transmis) ; Faro poste direct sur `alloy:12347` (CORS ouvert côté Alloy). Compose : profil `demo`, port hôte 8090.
- **Dépendance #4 → #3** : branche `feature/faro-angular` créée depuis `feature/otel-django` (pas `develop`, qui n'a pas encore units-service). À rebaser après le merge de #3 : `git rebase --onto develop feature/otel-django feature/faro-angular`.
- **Non validé en préparation** : proxy bloque npm, donc pas de compilation Angular ici. Recette (`npm install` + build Docker) à faire sur le Mac ; itération probable comme pour units-service (scaffold Angular à la main).

### 2026-07-19 — Session Claude : recette de la démo units-service (backlog #3 validé)
- Recette Docker sur le Mac (`docker compose --profile demo up -d --build`). Deux bugs trouvés et corrigés (commit `fix(demo)`) :
  - **`DJANGO_SETTINGS_MODULE` doit être dans l'env du conteneur** : `opentelemetry-instrument` touche aux settings Django avant `wsgi.py`, donc le `setdefault` arrivait trop tard → Django chargeait des settings vides → `AttributeError: ROOT_URLCONF` → 500 sur toutes les requêtes.
  - Import `JsonFormatter` rendu robuste aux deux emplacements de `python-json-logger` (>= 3.1 : `pythonjsonlogger.json`).
- **Validé dans Grafana** : `/sante/` et `/demo/commande` répondent 200 ; métrique `commandes_creees_total` (3 séries par `mode_paiement`) dans Prometheus ; log JSON `{… "trace_id":"1509…"}` dans Loki. Corrélation OK.
- Détail : le Collector force `deployment.environment=prod` (son `DEPLOY_ENV`, §10.3), donc la démo apparaît en `prod` ; `service.namespace=demo` la distingue.
- Reste : pousser `feature/otel-django` + MR → `develop`.

### 2026-07-19 — Session Claude : backlog #3 — démo Django units-service instrumentée
- Socle et guide **mergés dans `develop`** (`88d14de`) via les 2 MR ; `develop` contient tout (observability/, docs/), aucun secret. Backlog #1 terminé.
- **Backlog #3 démarré** sur `feature/otel-django` (depuis `develop`). Création de `demo/units-service/` : projet Django `units_project` instrumenté §10.1, sans aucune ligne d'instrumentation dans le code applicatif (tout par env + `opentelemetry-instrument`).
  - Endpoints `/sante/` et `/demo/commande` ; ce dernier émet les 3 signaux : trace auto, métrique `commandes_creees_total` (labels à faible cardinalité), `user.id` en attribut de span, log JSON avec `trace_id`.
  - `TraceContextFilter`, config LOGGING JSON, `requirements.txt` épinglé, `Dockerfile` multi-stage non-root avec `opentelemetry-bootstrap`, `gunicorn.conf.py`, README.
  - Branché au compose sous **profil `demo`** (opt-in), OTLP vers `otel-collector:4317`, port hôte `8088` (8000 pris par GlitchTip). `.env.example` complété (`UNITS_SECRET_KEY`).
- **Validation** : syntaxe Python OK (`py_compile`). La validation runtime (`manage.py check`, `docker compose --profile demo up`, télémétrie visible dans Grafana) est **à faire sur le Mac** : le bac à sable n'a ni Docker ni accès PyPI (proxy 403).
- **Choix actés** (questionnaire) : démo lançable branchée sur la pile, emplacement `demo/`, profil `demo` opt-in — pour valider la plateforme de bout en bout en gardant le cœur propre.

### 2026-07-19 — Session Claude : incident secret (push protection GitHub) + réécriture d'historique
- **Correction de l'entrée précédente** : seules `main`, `develop` et `docs/guide-utilisation-observabilite` ont été acceptées par le remote. Le push de `feature/observability-socle` a été **refusé par la protection anti-secrets de GitHub** : une URL de webhook Slack figurait dans `observability/alertmanager/secrets/slack_webhook_url.example` (introduite au commit socle). Un placeholder au format d'un webhook, pas un secret réel avéré, mais un `.example` ne doit jamais contenir d'URL qui matche le motif.
- **Correctif** : `.example` remplacé par un placeholder neutre (aucune URL `hooks.slack.com/...`), puis **historique de la branche réécrit** (rebase interactif éditant le commit socle) pour purger le motif. Vérifié : 0 occurrence dans l'arbre et dans tous les diffs de la branche. La branche n'ayant jamais été acceptée par le remote, aucun force-push nécessaire.
- **À faire** : `git push origin feature/observability-socle` (nouveau, propre), puis les 2 MR vers `develop`.
- **Reco gouvernance** : le hook `pre-commit` ne scanne pas les secrets (il ne protège que `main`/`develop`). Ajouter une détection de secrets (gitleaks / pre-commit) serait un bon enabler pour attraper ça localement, avant GitHub.

### 2026-07-19 — Session Claude : publication GitHub (remote + push des 4 branches)
- Remote `origin` posé sur le dépôt parent : `github.com/SteveElouga/observabilite-universelle` (privé).
- **4 branches poussées** : `main`, `develop`, `feature/observability-socle`, `docs/guide-utilisation-observabilite`. Le hook `pre-push` a bien toléré la création initiale de `develop`.
- Incident corrigé : un `git` lancé par erreur depuis `observability/` y avait créé un dépôt imbriqué vide (branche `master`, aucun commit) qui captait les commandes, d'où « src refspec main does not match any ». `observability/.git` retiré, `observability/` de nouveau suivi par le parent (15 fichiers), remote reposé au bon niveau.
- Reste : protections R8 sur GitHub, puis les 2 MR vers `develop`. Descriptions de MR et checklist R10 préparées.

### 2026-07-19 — Session Claude : correctifs de recette + guide d'utilisation
- Recette du socle (backlog #2) sur le Mac : deux correctifs d'exécutabilité corrigés et commités (`fix(observability)` `8f87d49`) sur `feature/observability-socle`.
  - `node-exporter` : retrait de la propagation `rslave` sur le montage `/` (incompatible Docker Desktop Mac/Win : « path / is mounted ... not a shared or slave mount »).
  - `tempo` : récepteur OTLP forcé sur `0.0.0.0:4317/4318` (Tempo 2.7 écoute sinon sur `localhost`, d'où le « connection refused » du Collector vers `tempo:4317`).
  - Chaîne validée de bout en bout : trace de fumée (curl OTLP) → Collector → tail sampling → Tempo → Grafana, corrélation OK. La trace de démonstration est marquée en erreur et lente pour passer l'échantillonnage.
- Nouveau **guide d'utilisation de la plateforme** (`docs/Guide_Utilisation_Plateforme_Observabilite.md`, commit `66358a6`) sur sa propre branche `docs/guide-utilisation-observabilite` créée depuis `develop` (R1). Référence d'intégration façon API pour tout projet consommateur : prérequis, concepts, chaque technologie justifiée (rôle, place, choix, fonctionnement), points d'entrée, trois méthodes de branchement (reco : réseau Docker partagé en local, endpoint stable derrière proxy à l'échelle), cloisonnement par projet (`X-Scope-OrgID` / Mimir), évolutions futures. Dossier `docs/` dédié.
- **Intégration dans `develop` volontairement NON faite** : R2/R4/R6 imposent une MR, impossible tant que le remote GitHub n'existe pas. Aucune fusion directe. Les deux branches sont prêtes pour leurs MR respectives.
- Rappel recette macOS : accorder à Docker l'accès disque à `~/Documents` (sinon « operation not permitted »), ou lancer la pile hors dossier protégé.

### 2026-07-17 — Session Claude : implémentation du socle observability/ (backlog #1)
- Transcription exécutable de la §10 sur `feature/observability-socle` : 15 fichiers (compose 16 services, Collector avec connecteurs avant tail sampling, datasources de corrélation, RED, SLO Sloth, blackbox, k6, `.env.example`, README du socle).
- **4 correctifs d'exécutabilité** appliqués au code ET reportés dans le document maître (§10) : ① webhook Slack en `api_url_file` (Alertmanager ne lit pas les variables d'environnement) ; ② service one-shot `glitchtip-migrate` + healthcheck Postgres + `depends_on` conditionnels ; ③ télémétrie interne du Collector exposée sur `0.0.0.0:8888` (sinon le job Prometheus `otel-collector` ne collecte rien — défaut localhost) ; ④ Alloy : relabel `container` sur les logs Docker (sinon flux Loki sans sélecteur) et traces Faro routées via le Collector (règle §3, cohérent avec les métriques dérivées).
- `.gitignore` : exclusion du secret Slack réel et de `rules-slo.yml` (artefact généré par sloth).
- Validation : 10 fichiers YAML parsés, références croisées compose (16 services, volumes, env vars vs `.env.example`), pipelines Collector (connecteurs câblés exporter+receiver), uids datasources, syntaxe k6 — tout vert.
- 3 commits sur la branche feature : `chore(repo)` (chmod hooks + .dockerignore), `feat(observability)` (socle + .gitignore), `docs` (doc §10 synchronisée + MEMORY). `main`/`develop` intacts.
- **Recette d'exécution NON faite** (pas de Docker dans l'environnement de session) : c'est le backlog #2, à faire sur le serveur cible ou le Mac.

### 2026-07-17 — Session Claude : cadrage & initialisation du dépôt
- Création du triptyque de gouvernance (`README.md`, `CONTEXT.md`, `MEMORY.md`) avec les règles Git R1–R13.
- Création des hooks de protection (`.githooks/pre-commit`, `.githooks/pre-push` — blocage de `main`/`develop`, création initiale sur remote vierge tolérée pour la première publication) + `scripts/install-hooks.sh` + `.gitignore`.
- Init du dépôt : `git init -b main`, commit bootstrap (exception consignée ci-dessus), `develop` créée depuis `main`, `feature/observability-socle` créée depuis `develop` et laissée active, `core.hooksPath=.githooks`.
- Vérification : commit test sur `main` **refusé par le hook** ✅ (`commit_exit=1`) ; retour sur `feature/observability-socle`. Les trois branches pointent sur le commit de bootstrap `a28ca38`.
- Ajout préventif d'un **`.dockerignore`** racine (aucune image construite dans ce dépôt à ce stade — compose = images officielles ; le fichier garantit qu'un futur `build:` n'embarquera ni secrets ni `.git`). À committer avec la MR du socle.

### 2026-07-17 — Session Claude : analyse & révision du document d'observabilité
- Analyse complète du document (points forts + 7 points d'attention), vérification web du statut de Grafana OnCall (archivé 24/03/2026).
- Révision appliquée après questionnaire : OneUptime, deux pipelines de traces au Collector (`spanmetrics`/`servicegraph` avant tail sampling), Pyroscope 1.10.0 au compose + datasource + `tracesToProfiles`, sections §7.4/§7.5, annexe §9.4 (sources des chiffres), 2 bugs YAML préexistants corrigés. ~150 lignes modifiées ; 11 blocs YAML et 12 diagrammes Mermaid validés.

### 2026-07-09 — Avant sessions Claude
- Rédaction initiale des deux documents d'architecture (`Architecture_CICD_Universelle.md`, `Architecture_Observabilite_Universelle-2.md`).

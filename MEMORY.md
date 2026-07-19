<!-- GOUVERNANCE — Fichier n°3 de l'ordre de lecture (README.md → CONTEXT.md → MEMORY.md). Mémoire évolutive : TOUTE session met à jour « État courant » et ajoute une entrée de journal AVANT de terminer (règle R11). Journal en ordre antéchronologique (le plus récent en haut). -->

# MEMORY — État courant, backlog & journal

## État courant *(à maintenir à jour à chaque session)*

- **Étape** : socle + **correctifs de recette committés** sur `feature/observability-socle` (backlog #1 ✅, #2 entamé — 5 commits). **Guide d'utilisation** de la plateforme rédigé sur `docs/guide-utilisation-observabilite`. Gouvernance en place, hooks actifs.
- **Branches** : `main` et `develop` figées sur le bootstrap `a28ca38` ; `feature/observability-socle` porte le socle + 2 correctifs (récepteur Tempo, node-exporter) ; `docs/guide-utilisation-observabilite` (créée depuis `develop`) porte le guide. **Les 4 branches sont publiées sur le remote.**
- **Prochaine action** : activer les protections R8 (`main`/`develop`), puis ouvrir les 2 MR ciblant `develop` (socle d'abord ; guide ensuite, après rebase R5). NB : pas encore de CI dans le dépôt, donc l'exigence « CI verte » de R8 est à activer le jour où une CI existera.
- **Remote GitHub** : **configuré** — `github.com/SteveElouga/observabilite-universelle` (privé), 4 branches publiées.
- **Point de vigilance** : Grafana OnCall est archivé (24/03/2026) — l'astreinte cible est OneUptime (phase 4) ; ne pas réintroduire OnCall.
- **Particularité du pont cloud→Mac** : la suppression de fichiers y est impossible → les verrous Git périmés sont **déplacés** dans `.git/_stale_locks/` au lieu d'être supprimés. Purger de temps en temps depuis le Mac : `rm -rf .git/_stale_locks`.

## Backlog ordonné *(une ligne = une future branche = une MR)*

| # | Travail | Branche prévue | Réf. document |
|---|---|---|---|
| 1 | ✅ **Fait (17/07/2026)** — Socle mono-serveur : arborescence `observability/` complète (compose LGT + Pyroscope + GlitchTip + Uptime Kuma, configs Collector/Prometheus/Loki/Tempo, datasources corrélées, règles RED, SLO Sloth, Alertmanager, blackbox, k6, `.env.example`). Committé, en attente de MR. | `feature/observability-socle` | §10.3–§10.7 |
| 2 | Démarrage & recette : `.env` réel (jamais commité), secret Slack (`alertmanager/secrets/`), `docker compose up`, vérifications §10.9 étapes 1–5 (corrélation aller-retour, exemplars) | *(même branche que #1 ou `fix/…`)* | §10.9 |
| 3 | Instrumentation Django `units-service` (auto-instr. OTel, logs JSON + trace_id, métrique métier) | `feature/otel-django` | §10.1 |
| 4 | Frontend Angular `mir-webapp` : Faro (RUM + traces) + GlitchTip (erreurs) | `feature/faro-angular` | §10.2 |
| 5 | Alerting réel : webhook Slack, règles RED actives, SLO Sloth généré (`sloth generate`) | `feature/alerting-slo` | §10.6 |
| 6 | Sondes externes : Uptime Kuma configuré (hébergé hors infra), Blackbox ciblé, k6 en CI | `feature/uptime-externe` | §10.7, §7.5 |
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

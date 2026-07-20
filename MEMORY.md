<!-- GOUVERNANCE — Fichier n°3 de l'ordre de lecture (README.md → CONTEXT.md → MEMORY.md). Mémoire évolutive : TOUTE session met à jour « État courant » et ajoute une entrée de journal AVANT de terminer (règle R11). Journal en ordre antéchronologique (le plus récent en haut). -->

# MEMORY — État courant, backlog & journal

## État courant *(à maintenir à jour à chaque session)*

- **Étape** : **Backlog initial TERMINÉ et intégralement mergé dans `develop`** (`4ed4d7f`) : socle, démos units-service/units-webapp, alerting RED/SLO, sondes externes, plan de correction du bilan (S1..S4 + R8), astreinte OneUptime (#7), profiling Pyroscope (#8). Plus aucune branche de travail en attente.
- **Branches** : `develop` = `4ed4d7f`, **protégé (R8 actif)** : MR obligatoire, CI verte requise, historique linéaire, `enforce_admins`. `main` au bootstrap.
- **Prochaine action** : plus de backlog initial. Évolutions « à venir » du document maître, hors périmètre : dashboards RED/USE as-code (provisioning Grafana), montée à l'échelle Kubernetes + Mimir (§7.2). Reste aussi le volet organisationnel du bilan (politiques, évaluation de risque), volontairement hors périmètre.
- **Remote GitHub** : **configuré** — `github.com/SteveElouga/observabilite-universelle` (privé), 4 branches publiées.
- **Point de vigilance** : Grafana OnCall est archivé (24/03/2026) — l'astreinte cible est OneUptime (phase 4) ; ne pas réintroduire OnCall.
- **Particularité du pont cloud→Mac** : la suppression de fichiers y est impossible → les verrous Git périmés sont **déplacés** dans `.git/_stale_locks/` au lieu d'être supprimés. Purger de temps en temps depuis le Mac : `rm -rf .git/_stale_locks`.

## Backlog ordonné *(une ligne = une future branche = une MR)*

| # | Travail | Branche prévue | Réf. document |
|---|---|---|---|
| 1 | ✅ **Fait (17/07/2026)** — Socle mono-serveur : arborescence `observability/` complète (compose LGT + Pyroscope + GlitchTip + Uptime Kuma, configs Collector/Prometheus/Loki/Tempo, datasources corrélées, règles RED, SLO Sloth, Alertmanager, blackbox, k6, `.env.example`). Committé, en attente de MR. | `feature/observability-socle` | §10.3–§10.7 |
| 2 | Démarrage & recette : `.env` réel (jamais commité), secret Slack (`alertmanager/secrets/`), `docker compose up`, vérifications §10.9 étapes 1–5 (corrélation aller-retour, exemplars) | *(même branche que #1 ou `fix/…`)* | §10.9 |
| 3 | ✅ **Fait (19/07/2026)** — Instrumentation Django `units-service` (`demo/units-service/`, profil compose `demo`). Recette validée dans Grafana : métrique `commandes_creees_total` (Prometheus), logs JSON avec `trace_id` (Loki), traces (Tempo). Correctif clé : `DJANGO_SETTINGS_MODULE` en env (avant `opentelemetry-instrument`). | `feature/otel-django` | §10.1 |
| 4 | ✅ **Fait (19/07/2026)** — Frontend Angular `units-webapp` (`demo/units-webapp/`, profil `demo`, port 8090) : Faro (RUM Web Vitals + traces, propagation W3C) + erreurs via `ErrorHandler` Angular → `faro.api.pushError` (+ GlitchTip si DSN). nginx proxifie `/api` (anti-CORS). Recette validée : RUM et erreurs dans Loki (`{source="faro"}`), trace corrélée navigateur→`units-service` dans Tempo. Branche depuis `feature/otel-django` (dépend de #3). | `feature/faro-angular` | §10.2 |
| 5 | ✅ **Fait (19/07/2026)** — Alerting réel : règles RED et SLO **réalignés sur les spanmetrics** (`traces_span_metrics_calls_total` / `_duration_milliseconds`, car units-service émet `http_server_duration_milliseconds` et non `..._request_duration_seconds`). Endpoint `/demo/erreur` (500) ajouté à units-service. **Recette validée de bout en bout** : `sloth generate` → règles chargées dans Prometheus (RED + SLO multi-burn-rate), erreurs provoquées → `HighErrorRate` Pending + `UnitsServiceAvailability` Firing → Alertmanager → **Slack `#alertes`**. Reste : MR vers `develop`. | `feature/alerting-slo` | §10.6 |
| 6 | ✅ **Fait (20/07/2026)** — Sondes externes. Blackbox : module `http_local` (sans SSL) + cibles réelles (santé plateforme grafana/prometheus/loki/tempo + endpoints démo), gabarit HTTPS prod commenté. Alertes de sonde (`prometheus/rules/probes.yml` : ProbeDown, ProbeSlow, cert TLS). `k6/smoke.js` réécrit sur la démo locale. Uptime Kuma : pattern **hors infra** documenté (`uptime-kuma/README.md` + `docker-compose.external.yml`), service in-compose marqué dev-only. **Recette validée** (k6 100 % vert, p95 14 ms ; 6 cibles Blackbox UP). Mergé (`b0c69b7`). | `feature/uptime-externe` | §10.7, §7.5 |
| 7 | ✅ **Fait (20/07/2026)** — Astreinte OneUptime. `alertmanager.yml` : receiver `page-oncall` (Slack **+** webhook OneUptime via `url_file`), les alertes `severity=page` partent aux deux, `ticket` reste Slack seul. Secret `oneuptime_webhook_url` hors Git (+ `.example`). `observability/oneuptime/README.md` : pourquoi hors infra, déploiement, politique d'escalade, câblage, complémentarité avec Uptime Kuma. Mergé (`30e4ef5`). | `feature/oneuptime` | §4.11, §10.6 |
| 8 | ✅ **Fait (20/07/2026)** — Profiling continu units-service. `requirements.txt` : `pyroscope-io==1.1.0` + `pyroscope-otel==1.1.0`. `gunicorn.conf.py` (`post_fork`) : `pyroscope.configure(app_name, server_address, sample_rate)` par worker (après fork, py-spy) + `PyroscopeSpanProcessor` sur le tracer provider auto-instrumenté → attribut `pyroscope.profile.id` sur le span racine (lien trace→profil, tracesToProfiles déjà en datasource). Compose units-service : `PYROSCOPE_SERVER_ADDRESS`, `cap_add: SYS_PTRACE`, `depends_on: pyroscope`. Recette Mac à faire. | `feature/pyroscope-sdk` | §10.1, §10.5 |
| 9 | ✅ **Fait (20/07/2026)** — Durcissement avant exposition (= lot S3, `observability/hardening/`) : surcouche `docker-compose.hardening.yml` (reverse proxy **Caddy** TLS + ports internes dépubliés via `!override []`), `Caddyfile` (TLS local interne / Let's Encrypt en prod ; Grafana, GlitchTip, Faro exposés ; accès admin backends en basic auth commentés), `backup.sh` (sauvegarde grafana-data/gt-db/kuma-data), `README` (usage local/prod, restriction CORS Alloy, chiffrement au repos, SSO Grafana). Recette Mac à faire. | `feature/hardening` | §7.4 |
| 10 | ✅ **Fait (20/07/2026)** — CI/CD sécurité (= lot S4, `.github/workflows/ci.yml`) : jobs gitleaks (secrets), lint (yamllint + hadolint + promtool + `compose config`), build (units-webapp `npm ci` + build, units-service `manage.py check`), scan (Trivy fs HIGH/CRITICAL + SBOM Syft CycloneDX). `renovate.json` (mises à jour de dépendances). Sur MR vers develop/main. À brancher dans R8 comme required status check. Reste possible plus tard : annotations de déploiement + source maps (doc CI/CD). | `feature/cicd-securite` | doc CI/CD §10 |
| S1 | ✅ **Fait (20/07/2026)** — Enablers de sécurité locale : gitleaks en pre-commit (+ `.gitleaks.toml`), units-webapp non-root (nginx unprivileged, 8080), verrou de dépendances (`npm ci` + `package-lock.json`). Mergé. | `feature/durcissement-securite` | Bilan §sécurité |
| S2 | ✅ **Fait (20/07/2026)** — Dossier de sécurité documentaire : `SECURITY.md` (politique + signalement + secrets), `docs/Modele_Menace.md` (STRIDE, frontières, tableau priorisé), `docs/Runbooks_Incident.md` (un playbook par alerte + panne plateforme). | `docs/dossier-securite` | Bilan §documentation |

> **Plan de correction (bilan 2026-07-20) — TERMINÉ** : S1 (enablers locaux), S2 (dossier sécurité), S3 (durcissement infra, #9), S4 (CI/CD sécurité, #10) et **R8** (protections de branches GitHub, actif le 20/07) faits. Seul reste, volontairement hors périmètre, le volet organisationnel du registre (point #9 : politiques écrites et évaluation de risque formelle).

## Décisions & exceptions consignées

| Date | Type | Détail |
|---|---|---|
| 2026-07-17 | Décision | Révision du document maître : OneUptime (astreinte), span-metrics au Collector avant échantillonnage, Pyroscope au compose, §7.4/§7.5/§9.4 ajoutées. Validée par Steve via questionnaire (4 questions, options recommandées retenues). |
| 2026-07-17 | Décision | Démarche **pas à pas** versionnée **GitHub** ; cadrage d'abord, implémentation ensuite. Règles Git R1–R13 adoptées (`README.md`). |
| 2026-07-17 | **Exception unique** | Commit de bootstrap effectué **directement sur `main`** (dépôt vide : `develop` ne pouvait pas encore exister). Portée : ce seul commit initial. Toute modification ultérieure de `main`/`develop` passe par MR (R2, R4, R6). |
| 2026-07-20 | **Décision propriétaire (R13)** | Steve autorise la **modification du hook `pre-commit`** pour y **ajouter le scan gitleaks**. C'est un renforcement de sécurité, jamais un contournement des protections de branches. Portée : ajout d'un bloc de scan de secrets dans `.githooks/pre-commit` + fichier `.gitleaks.toml`. |
| 2026-07-20 | Décision | Steve (questionnaire) : renommer la démo frontend `mir-webapp` → `units-webapp` (paire avec `units-service`), et **étendre** le renommage aux exemples du document CI/CD pour la cohérence globale. |
| 2026-07-20 | **Décision propriétaire (R13)** | Steve autorise la **mise à jour de la règle R8** dans la section « Règles Git » du `README.md` (protégée par R12) : la formuler au présent (protections **actives**) et refléter le réglage réel du dépôt solo (**0 approbation** requise, CI verte + `enforce_admins`). Portée : réécriture de la seule ligne R8, aucune autre règle modifiée. |

## Journal *(antéchronologique — ajouter chaque nouvelle entrée EN HAUT)*

### 2026-07-20 — Session Claude : hygiène (.gitignore Obsidian)
- `CONTEXT.md` avait été reformaté par Obsidian dans l'arbre de travail (tableaux réalignés, mais comment de gouvernance en tête supprimé et coquille « référencec » introduite). **Restauré** à sa version commitée ; aucun impact sur l'historique (c'étaient des modifs non commitées).
- Ajout de `.obsidian/` au `.gitignore` (comme `.idea/`, `.vscode/`) pour ne pas versionner la config de l'éditeur. **Piège à retenir** : désactiver le formatage automatique d'Obsidian pour ce coffre, sinon les `.md` (dont `CONTEXT.md`) seront reformatés à chaque sauvegarde.

### 2026-07-20 — Session Claude : mise à jour finale de la documentation (backlog bouclé)
- Backlog initial 100 % mergé dans `develop` (`4ed4d7f`). PR #9 (doublon obsolète de #6) à fermer, PR #19 (#8) mergée.
- **Audit exhaustif de la doc par sous-agent** : aucune trace résiduelle de `mir-webapp` (renommage complet). 4 fichiers périmés, tous sur le décalage « à venir / à activer » vs « fait ».
- **Corrections** (branche `docs/mise-a-jour-finale`) :
  - `README.md` (hors section Règles Git) : table de structure réactualisée (docs/, hardening/, oneuptime/, SECURITY.md, CI) ; « démarrage rapide » au présent.
  - `observability/README.md` : durcissement livré dans `hardening/` ; arborescence complétée (`hardening/`, `oneuptime/`, secret OneUptime) ; mise en route étapes 7-8 à jour ; section « à venir » réduite aux dashboards as-code + Mimir/K8s.
  - `docs/Bilan_Maturite_Conformite.md` : encart en tête + section « Suite donnée » (registre soldé : 6/9 faits, 2 partiels, 1 organisationnel ouvert). L'instantané original du matin est conservé.
  - `docs/Parcours_Expertise_Observabilite.md` : docs de sécurité ajoutés à la liste de référence ; Pyroscope et plan de correction au présent/passé.
  - `MEMORY.md` : état courant = backlog terminé.
- **Non touché volontairement** : la section « Règles Git » du `README.md` (R8 « à activer », « ≥1 approbation ») est protégée par R12 ; sa mise à jour attend une décision explicite du propriétaire (R13). Le statut réel (R8 actif, 0 approbation car dépôt solo) est déjà consigné en tête de MEMORY.

### 2026-07-20 — Session Claude : #8 — profiling continu Pyroscope (units-service)
- Sur `feature/pyroscope-sdk` (depuis `develop`, indépendant de #7 ; rebasé sur `develop`+#7 avec réconciliation `MEMORY.md`). Dernier lot du backlog initial.
- **Versions vérifiées sur PyPI** : `pyroscope-io==1.1.0` et `pyroscope-otel==1.1.0` (Python >= 3.10 ; units-service en 3.12). API confirmée sur la page pyroscope-otel 1.1.0.
- **`gunicorn.conf.py`** (`post_fork`) : `pyroscope.configure(app_name, server_address=http://pyroscope:4040, sample_rate=100)` par worker (py-spy échantillonne le processus, donc APRÈS le fork), puis `trace.get_tracer_provider().add_span_processor(PyroscopeSpanProcessor())` — pattern officiel pour l'auto-instrumentation.
- **Lien trace→profil** : le span processor pose `pyroscope.profile.id` sur le span racine ; `tracesToProfiles` est déjà en datasource (§10.5), donc le saut Tempo→Pyroscope marche sans toucher Grafana.
- **Compose** : units-service reçoit `PYROSCOPE_SERVER_ADDRESS`, `cap_add: [SYS_PTRACE]` (py-spy dans un conteneur) et `depends_on: pyroscope`.
- **Reste** : MR #8. Recette Mac (graphe de flammes de units-service dans Pyroscope, saut trace→profil).

### 2026-07-20 — Session Claude : #7 — astreinte OneUptime (receiver Alertmanager)
- Sur `feature/oneuptime`, mergé dans `develop` (`30e4ef5`).
- **`alertmanager.yml`** : nouveau receiver `page-oncall` avec `slack_configs` **et** `webhook_configs` (`url_file: secrets/oneuptime_webhook_url`, Alertmanager >= 0.26). La route `severity=page` pointe désormais sur `page-oncall` (Slack + OneUptime), `severity=ticket` reste sur `slack`. Inhibition page→ticket conservée.
- **Secret** : `secrets/oneuptime_webhook_url.example` (URL neutre) ; le vrai fichier reste hors Git (`.gitignore` couvre déjà `secrets/*` sauf `*.example`).
- **`observability/oneuptime/README.md`** : pourquoi hors infra (l'astreinte doit survivre à la panne du serveur, comme Uptime Kuma), déploiement (hébergé ou auto-hébergé sur machine séparée, sans dupliquer leur compose), création de la politique d'escalade et de l'intégration entrante, câblage du webhook, vérification, complémentarité Uptime Kuma (détection) / OneUptime (action humaine). Rappel : Grafana OnCall archivé, ne pas réintroduire.
- **Recette** : validable sans OneUptime réel via un webhook de test (webhook.site) pour prouver que `page-oncall` notifie bien les deux canaux.

### 2026-07-20 — Session Claude : plan de correction bouclé (S4 mergé, R8 actif)
- **S4 mergé** dans `develop` (PR #16, `e5a648c`). Premier run CI : deux correctifs techniques (`promtool` via `--entrypoint` car l'image prom/prometheus a `prometheus` en entrypoint ; Trivy lancé en conteneur car l'action `@0.24.0` n'existait pas). Le scan a ensuite détecté un vrai **CVE-2025-64459** (injection SQL, Django 5.1.4) → **Django bumpé en 5.1.14** ; CI verte, quatre jobs OK.
- **R8 activé** par Steve via `gh api` sur `develop` et `main` : MR obligatoire, `enforce_admins: true`, `required_linear_history` sur develop, force-push et suppression interdits, et **les 4 checks CI exigés** sur develop (contextes vérifiés, ils correspondent aux `name:` des jobs). 0 approbation requise (dépôt solo, GitHub interdit l'auto-approbation), `required_status_checks: null` sur main.
- **Conséquence** : gouvernance appliquée de bout en bout côté serveur. Plus aucun changement n'entre dans `develop` sans MR ni CI verte, propriétaire compris. Toute MEMORY future passe donc par une MR (comme celle-ci).
- **Suite** : phase 4 du backlog initial, #7 (astreinte OneUptime) puis #8 (profiling Pyroscope).

### 2026-07-20 — Session Claude : lot S4 — CI/CD sécurité (GitHub Actions)
- Sur `feature/cicd-securite`, depuis `develop` complet (`53a643b`, S2 et S3 mergés). Clôt le plan de correction issu du bilan.
- **`.github/workflows/ci.yml`** (MR vers develop/main + push + manuel), quatre jobs : `secrets` (gitleaks en `--no-git` sur l'arbre, config `.gitleaks.toml`) ; `lint` (yamllint, hadolint sur les deux Dockerfiles, `promtool check rules` sur red.yml + probes.yml, `docker compose config` base et durcissement) ; `build` (units-webapp `npm ci` + build Angular, units-service `pip install` + `manage.py check`) ; `scan` (Trivy fs HIGH/CRITICAL, `ignore-unfixed`, plus SBOM Syft CycloneDX publié en artefact).
- **`renovate.json`** : mises à jour de dépendances groupées (images Docker, Python, npm, actions GitHub) ; s'active si l'app Renovate est installée sur le dépôt.
- **À faire côté GitHub** : après le premier run, ajouter les jobs comme *required status checks* dans la protection de `develop` (R8) pour imposer la CI verte. Le gitleaks du hook `pre-commit` est ainsi doublé côté serveur.
- **Reste** : MR S4. Le plan de correction (hors volet organisationnel) est terminé.

### 2026-07-20 — Session Claude : lot S3 — durcissement infra (surcouche Caddy)
- Sur `feature/hardening` (chaîné sur `docs/dossier-securite`, à rebaser après le merge de S2). Nouveau dossier `observability/hardening/`, aucune modification du compose de base (durcissement opt-in).
- **Reverse proxy Caddy** (`docker-compose.hardening.yml` + `Caddyfile`) : point d'entrée unique en TLS. Grafana, GlitchTip et le point de collecte Faro exposés en HTTPS ; Prometheus/Loki/Tempo/Pyroscope/Alertmanager **dépubliés** (`ports: !override []`, joignables seulement via Grafana sur le réseau Docker). Local : `*.localhost` + `tls internal`. Prod : domaines réels + Let's Encrypt automatique. Accès admin direct aux backends via basic auth, laissé commenté.
- **Sauvegarde** (`backup.sh`) : archive `grafana-data`, `gt-db`, `kuma-data` (état non reconstructible depuis le dépôt) ; télémétrie volontairement non sauvegardée (§7.5). À planifier par cron.
- **README durcissement** : usage local vs prod, restriction des origines Faro (`cors_allowed_origins`), rôles et SSO Grafana, chiffrement au repos au niveau de l'hôte (LUKS ou stockage chiffré).
- `.gitignore` : exclusion de `observability/hardening/backups/`.
- **Prérequis** : Docker Compose >= 2.24 (tag `!override`). **Recette Mac** : `docker compose -f docker-compose.yml -f hardening/docker-compose.hardening.yml up -d`, puis accès `https://grafana.localhost`.
- **Reste** : MR S3. Ensuite S4 (CI/CD sécurité, #10) et R8.

### 2026-07-20 — Session Claude : lot S2 — dossier de sécurité documentaire
- Sur `docs/dossier-securite`, depuis `develop` complet (`6674d33`, renommage inclus). Trois nouveaux documents, aucune modification de code.
- **`SECURITY.md`** (racine) : signalement privé de vulnérabilité, périmètre, posture laboratoire assumée (pas de TLS ni d'auth, ne pas exposer en l'état), gestion des secrets (gitignore, `alertmanager/secrets`, gitleaks), bonnes pratiques déployeur, dépendances épinglées, versions supportées.
- **`docs/Modele_Menace.md`** : méthode STRIDE. Actifs, frontières de confiance, diagramme de flux Mermaid, analyse par famille de menace avec mitigations en place et planifiées, tableau récapitulatif priorisé (gravité + état). Renvoie au bilan et au lot #9.
- **`docs/Runbooks_Incident.md`** : un runbook par alerte réelle (HighErrorRate, HighLatencyP99, UnitsServiceAvailability, ProbeDown, ProbeSlow, ProbeSSLCertExpiringSoon) + panne plateforme + escalade. Chaque : signification, diagnostic (corrélation Grafana + requêtes PromQL/TraceQL), remédiation, escalade. Rappelle le faux positif ProbeDown (redémarrer `blackbox-exporter` après modif de config).
- **Reste** : MR S2 → `develop`. Ensuite S3 (durcissement infra, #9), S4 (CI/CD sécurité, #10), et l'action utilisateur R8.

### 2026-07-20 — Session Claude : renommage de la démo frontend `mir-webapp` → `units-webapp`
- Décision de Steve (questionnaire) : nom `units-webapp` (paire avec `units-service`), et **tout renommer**, y compris les 14 références du document CI/CD, pour la cohérence globale.
- Fait **après** l'intégration de #6, `docs` et S1 dans `develop` (renommage atomique sur un `develop` complet, `refactor/rename-units-webapp` depuis `develop`) : dossier `demo/mir-webapp/` → `demo/units-webapp/` ; service compose `units-webapp` ; contenu (Dockerfile, README, angular.json, package.json, package-lock.json, src) ; `Architecture_Observabilite_Universelle-2.md` (§10.2 Faro), `Architecture_CICD_Universelle.md`, `CONTEXT.md`, `docs/Parcours_Expertise_Observabilite.md`, `MEMORY.md`.
- **Correctif au passage** : la cible `blackbox-demo` passe de `http://mir-webapp:80/` à `http://units-webapp:8080/` (le nginx non-root du lot S1 écoute désormais sur 8080, l'ancienne cible sur 80 aurait échoué).
- **Reste** : MR du renommage → `develop`. Recette : `docker compose --profile demo up -d --build units-webapp` doit répondre 200 sur `http://localhost:8090/`.

### 2026-07-20 — Session Claude : bilan de maturité/conformité + plan de correction (lot S1)
- **Bilan** produit et vérifié par sous-agent (`docs/Bilan_Maturite_Conformite.md`) : observabilité et gouvernance de bon niveau ; sécurité d'exploitation et conformité SOC 2 pas encore en place (laboratoire assumé) ; documentation riche mais sans `SECURITY.md`, modèle de menace ni runbooks. Registre d'écarts priorisé (9 points). **Parcours d'expertise** ajouté (`docs/Parcours_Expertise_Observabilite.md`).
- **Plan de correction** (tous les points sauf le volet organisationnel #9 du registre) découpé en lots : **S1** enablers locaux, **S2** dossier sécurité, **S3** durcissement infra (= backlog #9), **S4** CI/CD sécurité (= backlog #10), plus **action utilisateur R8** (protections GitHub).
- **Lot S1** sur `feature/durcissement-securite` (depuis `develop`, R3) :
  - **gitleaks** ajouté au hook `pre-commit` (+ `.gitleaks.toml` : `useDefault = true`, allowlist des `.example` et placeholders). Décision R13 consignée. Le hook avertit si gitleaks est absent, bloque si un secret est détecté.
  - **units-webapp non-root** : image `nginxinc/nginx-unprivileged` (uid 101, écoute 8080) ; `nginx.conf` (`listen 8080`) et port compose (`8090:8080`) adaptés. Build reproductible : `npm ci` si `package-lock.json` présent, sinon `npm install`.
- **Reste (Mac)** : `brew install gitleaks` ; committer `demo/units-webapp/package-lock.json` (généré) pour activer `npm ci` ; recette du build units-webapp non-root ; puis MR S1, puis renommage du frontend en `units-webapp`.

### 2026-07-20 — Session Claude : #5 validé de bout en bout + backlog #6 (sondes externes)
- **#5 recette complète sur le Mac** : `sloth generate` → Prometheus charge `service-red` (red.yml) **et** `sloth-slo-alerts-units-service-requests-availability` (rules-slo.yml). Erreurs via `/demo/erreur` → `HighErrorRate` Pending (100 % de spans en erreur) et `UnitsServiceAvailability` **Firing** → Alertmanager (receiver `slack`) → **Slack `#alertes`** (`[FIRING:1] UnitsServiceAvailability`). Chaîne d'alerting bout en bout OK.
- **Détail SLO** : l'alerte page Sloth exige deux fenêtres (5m **et** 1h) au-dessus du seuil ; à 100 % d'erreurs les deux passent d'emblée, d'où un firing quasi immédiat. En dégradation réaliste (quelques %), elle serait plus lente que `HighErrorRate` (`for: 5m`).
- **#6** sur `feature/uptime-externe` (depuis `feature/alerting-slo`, choix « tout est encore local » via questionnaire).
  - **Blackbox** : ajout du module `http_local` (sans `fail_if_not_ssl`, les cibles internes sont en HTTP) ; `http_2xx` (SSL) conservé pour la prod. `prometheus.yml` : cibles fictives `example.com` remplacées par deux jobs réels — `blackbox-platform` (grafana/prometheus/loki/tempo, toujours actifs) et `blackbox-demo` (units-service `/sante/`, units-webapp). Job HTTPS `blackbox-public` laissé commenté comme gabarit prod.
  - **Alertes de sonde** : `prometheus/rules/probes.yml` (ProbeDown `probe_success==0`, ProbeSlow `probe_duration_seconds>1`, ProbeSSLCertExpiringSoon pour les cibles HTTPS). Chargé via `rule_files: rules/*.yml`.
  - **k6** : `k6/smoke.js` réécrit sur la démo locale (`BASE_URL` paramétrable, défaut `http://localhost:8088`, exerce `/sante/` + `/demo/commande`). Câblage CI reporté au #10.
  - **Uptime Kuma hors infra** : `uptime-kuma/README.md` (pourquoi hors infra = dead man's switch, où l'héberger, moniteurs, notif Slack) + `uptime-kuma/docker-compose.external.yml` (Kuma autonome sur machine séparée). Service in-compose annoté **dev-only**.
- **Recette #6 validée sur le Mac** : `k6 run k6/smoke.js` → 590/590 checks OK, p95 13,8 ms, 0 % d'erreur. Puis les 6 cibles Blackbox UP (`blackbox-platform` 4/4, `blackbox-demo` 2/2). **Piège** : après modif de `blackbox.yml`, il faut `docker compose restart blackbox-exporter` — sinon l'exporteur garde l'ancienne config sans le module `http_local` et répond 400 « Unknown module » (Prometheus seul redémarré ne suffit pas).
- **#6 mergé dans `develop`** (`b0c69b7`) le 20/07 (rebase-merge, après déblocage du « cannot be rebased » via le dropdown de méthode de merge).

### 2026-07-19 — Session Claude : backlog #5 — alerting réel + SLO (règles RED/SLO)
- Branche `feature/alerting-slo` depuis `develop` (`3892fc8`, avec #1/#3/#4 mergés).
- **Découverte** : units-service émet `http_server_duration_milliseconds` (pas `http_server_request_duration_seconds` du socle), plus les spanmetrics `traces_span_metrics_calls_total` / `_duration_milliseconds`. Les règles RED et SLO du socle n'auraient donc jamais eu de données.
- **Correctif** : `red.yml` et `slo/units-service.yml` réécrits sur les **spanmetrics** (source RED canonique, §10.3) : erreurs via `status_code="STATUS_CODE_ERROR"`, latence via `traces_span_metrics_duration_milliseconds_bucket` (seuil en ms, pas en s). Endpoint `/demo/erreur` (HTTP 500 → span en erreur) ajouté à units-service pour tester.
- **Recette validée sur le Mac (bout en bout)** : `sloth generate -i slo/units-service.yml -o prometheus/rules/rules-slo.yml` (binaire sloth installé) → `docker compose restart prometheus`. Prometheus charge le groupe `service-red` (RED, red.yml) **et** `sloth-slo-alerts-units-service-requests-availability` (SLO multi-burn-rate, rules-slo.yml). Erreurs provoquées via `/demo/erreur` : `HighErrorRate` passe en **Pending** (100 % de spans en erreur, `for: 5m`) et `UnitsServiceAvailability` en **Firing** (burn rate à 100 % » budget 0,1 %, fenêtres courte et longue franchies d'emblée). L'alerte remonte à **Alertmanager** (receiver `slack`, labels Sloth) puis à **Slack `#alertes`** : `[FIRING:1] UnitsServiceAvailability`.
- Détail SLO : l'alerte page Sloth exige les deux fenêtres (5m **et** 1h) au-dessus du seuil pour éviter les faux positifs ; à 100 % d'erreurs, les deux passent tout de suite, d'où un firing quasi immédiat. En dégradation réaliste (quelques %), elle serait plus lente que `HighErrorRate`.
- `rules-slo.yml` reste un **artefact généré** (git-ignoré) : à régénérer par `sloth generate` sur chaque cible, jamais commité.
- Reste : pousser `feature/alerting-slo` + MR → `develop`.

### 2026-07-19 — Session Claude : recette units-webapp (backlog #4 validé)
- Recette Docker de `units-webapp` sur le Mac (`docker compose --profile demo up -d --build`). L'app Angular compile et tourne du premier build.
- Deux correctifs de recette sur `feature/faro-angular` :
  - **Label Loki** : le récepteur Faro écrivait sans label filtrable → ajout d'un `loki.process` posant `source="faro"` dans `alloy-config.alloy`. Les événements RUM se filtrent via `{source="faro"}`.
  - **Erreurs Angular** : Angular intercepte les erreurs dans sa zone, le gestionnaire par défaut de Faro ne les voit pas → `ObservabilityErrorHandler` qui pousse via `faro.api.pushError` (et Sentry/GlitchTip si DSN).
- **Validé dans Grafana** : `{source="faro"}` montre Web Vitals + fetch ; `kind=exception` montre l'erreur JS avec stack trace ; Tempo Search sur `units-service`/`units-webapp` montre une trace unique avec les deux services (corrélation navigateur→Django).
- Détail : le tail sampling du Collector ne garde qu'environ 10 % des traces rapides, donc chercher une trace par ID au hasard renvoie souvent 404 ; utiliser la recherche par service dans Tempo.

### 2026-07-19 — Session Claude : backlog #4 — frontend Angular units-webapp (Faro + GlitchTip)
- Création de `demo/units-webapp/` : app Angular 18 (standalone) instrumentée §10.2. Faro Web SDK (Web Vitals, erreurs JS, `TracingInstrumentation` avec propagation W3C) + GlitchTip via `@sentry/angular` (initialisé seulement si un DSN est fourni). Composant démo : bouton « appeler le backend » (trace propagée) + bouton « erreur JS ».
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

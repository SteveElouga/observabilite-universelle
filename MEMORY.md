<!-- GOUVERNANCE — Fichier n°3 de l'ordre de lecture (README.md → CONTEXT.md → MEMORY.md). Mémoire évolutive : TOUTE session met à jour « État courant » et ajoute une entrée de journal AVANT de terminer (règle R11). Journal en ordre antéchronologique (le plus récent en haut). -->

# MEMORY — État courant, backlog & journal

## État courant *(à maintenir à jour à chaque session)*

- **Étape** : cadrage terminé — triptyque de gouvernance en place, dépôt Git initialisé, hooks de protection actifs et testés.
- **Branches** : `main` (bootstrap) → `develop` → `feature/observability-socle` (**branche de travail active**, vide pour l'instant).
- **Prochaine action** : implémenter le socle §10 dans `observability/` **sur `feature/observability-socle`**, puis MR → `develop` (checklist R10).
- **Remote GitHub** : **pas encore configuré.** À la création : suivre « Première publication » du `README.md` et activer immédiatement les protections R8.
- **Point de vigilance** : Grafana OnCall est archivé (24/03/2026) — l'astreinte cible est OneUptime (phase 4) ; ne pas réintroduire OnCall.

## Backlog ordonné *(une ligne = une future branche = une MR)*

| # | Travail | Branche prévue | Réf. document |
|---|---|---|---|
| 1 | Socle mono-serveur : arborescence `observability/` complète (compose LGT + Pyroscope + GlitchTip + Uptime Kuma, configs Collector/Prometheus/Loki/Tempo, datasources corrélées, règles RED, SLO Sloth, Alertmanager, blackbox, k6, `.env.example`) | `feature/observability-socle` | §10.3–§10.7 |
| 2 | Démarrage & recette : `.env` réel (jamais commité), `docker compose up`, vérifications §10.9 étapes 1–5 (corrélation aller-retour, exemplars) | *(même branche que #1 ou `fix/…`)* | §10.9 |
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

### 2026-07-17 — Session Claude : cadrage & initialisation du dépôt
- Création du triptyque de gouvernance (`README.md`, `CONTEXT.md`, `MEMORY.md`) avec les règles Git R1–R13.
- Création des hooks de protection (`.githooks/pre-commit`, `.githooks/pre-push` — blocage de `main`/`develop`, création initiale sur remote vierge tolérée pour la première publication) + `scripts/install-hooks.sh` + `.gitignore`.
- Init du dépôt : `git init -b main`, commit bootstrap (exception consignée ci-dessus), `develop` créée depuis `main`, `feature/observability-socle` créée depuis `develop` et laissée active, `core.hooksPath=.githooks`.
- Vérification : commit test sur `main` **refusé par le hook** ✅ ; retour sur `feature/observability-socle`.

### 2026-07-17 — Session Claude : analyse & révision du document d'observabilité
- Analyse complète du document (points forts + 7 points d'attention), vérification web du statut de Grafana OnCall (archivé 24/03/2026).
- Révision appliquée après questionnaire : OneUptime, deux pipelines de traces au Collector (`spanmetrics`/`servicegraph` avant tail sampling), Pyroscope 1.10.0 au compose + datasource + `tracesToProfiles`, sections §7.4/§7.5, annexe §9.4 (sources des chiffres), 2 bugs YAML préexistants corrigés. ~150 lignes modifiées ; 11 blocs YAML et 12 diagrammes Mermaid validés.

### 2026-07-09 — Avant sessions Claude
- Rédaction initiale des deux documents d'architecture (`Architecture_CICD_Universelle.md`, `Architecture_Observabilite_Universelle-2.md`).

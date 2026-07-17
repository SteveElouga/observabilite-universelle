<!-- GOUVERNANCE — Fichier n°2 de l'ordre de lecture (README.md → CONTEXT.md → MEMORY.md). Contexte durable : ce qui change rarement. L'état courant et le journal vivent dans MEMORY.md. -->

# CONTEXT — Observabilité universelle

## Objectif du projet

Implémenter, **pas à pas**, la stack d'observabilité **100 % gratuite, open source et auto-hébergée** décrite dans le document maître, en suivant le modèle de maturité (§8) : chaque étape apporte une valeur immédiate, vit sur **sa propre branche Git** et s'intègre par MR (règles du `README.md`). L'objectif final : la navigation macro → micro en deux clics (métrique → trace → log → profil) décrite au §1 du document.

## Documents de référence

| Document | Rôle | Points clés |
|---|---|---|
| `Architecture_Observabilite_Universelle-2.md` | **Document maître.** Architecture, comparatifs, écrans, stack retenue, code complet. | Révisé le **17/07/2026** (voir note de révision en tête du document). La **§10** est la source de vérité du code du socle ; la **§10.9** donne l'ordre de mise en route. |
| `Architecture_CICD_Universelle.md` | Compagnon CI/CD. | Annotations de déploiement, upload des source maps, Renovate (mise à jour des versions épinglées). |

## Stack retenue (décidée — ne pas rediscuter sans nouvelle décision consignée)

| Rôle | Outil | Note |
|---|---|---|
| Instrumentation | **OpenTelemetry** (+ Faro web, SDK Sentry mobile) | Standard non négociable, anti-verrouillage |
| Pipeline | **OTel Collector** (+ Alloy : logs conteneurs & récepteur Faro) | Point de contrôle volume/coût ; span-metrics & service graph générés **ici, avant échantillonnage** |
| Métriques | **Prometheus** | **Mimir réservé à l'échelle Kubernetes** (§7.2/§10.8), pas au mono-serveur |
| Logs | **Loki** | Logs JSON structurés, `trace_id` injecté |
| Traces | **Tempo** | Tail sampling au Collector (100 % erreurs/lentes, 10 % baseline) |
| Profils | **Pyroscope** | Serveur dans le compose ; SDK à activer en phase 4 |
| Erreurs & crash | **GlitchTip** (SDK Sentry) | Drop-in Sentry ; Sentry self-host si besoin de replay/profiling |
| RUM web | **Grafana Faro** | Corrélé au backend dans le même Grafana |
| Uptime / synthétique | **Uptime Kuma** + Blackbox Exporter + k6 | Sonde à héberger **hors** de l'infra surveillée (§7.5) |
| Visualisation | **Grafana** | Datasources provisionnées = le câblage de la corrélation (§10.5) |
| Alerte | **Alertmanager + Grafana Alerting** | Alerter sur les symptômes (SLO/burn rate), pas les causes |
| Astreinte | **OneUptime** | ⚠ Remplace Grafana OnCall, **archivé le 24/03/2026** ; machine séparée recommandée |
| SLO | **Sloth** (+ Pyrra en option) | SLO-as-code → règles multi-burn-rate |

## Décisions actées

| Date | Décision |
|---|---|
| 2026-07-17 | Révision du document maître : **OneUptime** remplace OnCall ; **span-metrics au Collector avant tail sampling** (2 pipelines traces, `metrics_generator` Tempo retiré) ; **Pyroscope au compose** ; ajout §7.4 (durcissement), §7.5 (HA/sauvegarde), §9.4 (sources) ; 2 bugs YAML corrigés (`${VAR}` non quotés en flow mapping). |
| 2026-07-17 | **Démarche pas à pas**, versionnée **Git/GitHub (pour ce projet)** : d'abord le cadrage (ce triptyque + dépôt + hooks), puis le socle §10 sur `feature/observability-socle`, puis le reste du backlog (`MEMORY.md`). |
| 2026-07-17 | Modèle de branches et règles R1–R13 adoptés (voir `README.md`). Bootstrap du dépôt vide sur `main` = **exception unique**, consignée dans `MEMORY.md`. |

## Cibles techniques du projet

- **Backend** : Django — service de référence `units-service` (gunicorn) ; instrumentation OTel §10.1 du document maître.
- **Frontend** : Angular — application `mir-webapp` ; Faro + GlitchTip §10.2.
- **Mobile** : SDK Sentry → GlitchTip (symbolication via pipeline CI).
- **Topologie de départ** : mono-serveur Docker Compose (§7.1 / §10.4) ; cible d'échelle : Kubernetes agent/gateway (§7.2 / §10.8).
- **Plateforme Git** : **GitHub** (le terme « MR » du dépôt = Pull Request GitHub).

## Conventions non négociables (résumé opérationnel du document maître)

1. Labels communs partout : `service`, `env`, `version`, `region`. **Jamais** d'identifiant à forte cardinalité (`user_id`, UUID, request_id) en label de métrique ou de log → attribut de span / structured metadata Loki (§7.3).
2. Logs **JSON structurés** avec `trace_id`/`span_id` injectés (§10.1) — c'est ce qui rend la corrélation cliquable.
3. **Tout transite par l'OTel Collector** ; aucune application branchée directement sur un backend de stockage (§3).
4. Alerter sur les **symptômes** (SLO / burn rate), enquêter avec les causes (§10.6).
5. Dashboards, datasources, alertes et SLO : **as-code, versionnés, provisionnés** — jamais de modification manuelle durable dans les UIs.
6. **Aucun secret en clair dans Git** : `.env` local (ignoré), `.env.example` versionné ; masquage des données sensibles au Collector (`attributes/redact`).
7. Avant toute exposition réelle : appliquer le **durcissement §7.4** (ports non publiés, TLS, auth, secrets).
8. Ports de référence : Grafana 3000 · Prometheus 9090 · Alertmanager 9093 · Loki 3100 · Tempo 3200 · Pyroscope 4040 · Collector 4317/4318 · Alloy/Faro 12347 · Uptime Kuma 3001 · GlitchTip 8000.

## Environnement de travail (sessions Claude / Cowork)

- Racine du dépôt = dossier connecté : `Architecture cible` (Documents du Mac de Steve).
- L'environnement local (VM du Mac) n'a **pas d'accès réseau** : installations, fetch et recherches se font côté cloud ; les opérations réseau Git (push/pull vers GitHub) sont exécutées par Steve depuis son terminal.
- Fuseau horaire de référence : Africa/Douala (UTC+1).
- Rappel R11 : lire le triptyque en début de session, mettre à jour `MEMORY.md` en fin de session.

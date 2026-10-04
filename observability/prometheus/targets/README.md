# prometheus/targets/ — cibles optionnelles, découvertes par fichier

Cinq jobs de `prometheus.yml` lisent ce répertoire au lieu d'une liste en dur : `postgres`,
`rabbitmq`, `keycloak`, `blackbox-application-graphql` et `blackbox-application-http`. Ils
alimentent les alertes §8.4 (DLQ, échecs d'authentification, sondes) et les dashboards §8.3
(PostgreSQL, RabbitMQ) du projet consommateur. En compose, un sixième s'y ajoute,
`blackbox-demo` (`prometheus/scrape.d/demo.yml`), que l'image publiée n'embarque pas.

**Pourquoi pas des `static_configs`.** Une cible écrite en dur mais absente rend le job *down*,
donc `up == 0`, donc l'alerte « service injoignable » sonne — pour un composant que personne
n'attendait. Un fichier vide (`[]`) ne déclare aucune cible : pas de série, pas de fausse alerte,
et la règle reste écrite, prête à s'allumer.

**La règle, sans exception : c'est l'ACTIVATION qui est explicite, jamais la désactivation.**
Tous les fichiers versionnés ici valent `[]`. Une seule cible faisait exception jusqu'au
15/09/2026 — la passerelle GraphQL du consommateur, écrite en dur : partout où le projet
consommateur ne tourne pas sur le réseau `obs-edge`, la sonde échouait vraiment et `ProbeDown`
(*severity=page*) sonnait en permanence. C'est le défaut qu'on venait de corriger sur les cibles
de démonstration, reproduit ailleurs.

**Qui les remplit.**

| Variable | Écrit | Exemple |
|---|---|---|
| `DATA_SOURCE_NAME` | `postgres.yml` | `postgresql://obs:...@postgres:5432/app?sslmode=disable` |
| `RABBITMQ_METRICS_TARGET` | `rabbitmq.yml` | `rabbitmq:15692` (greffon `rabbitmq_prometheus`) |
| `KEYCLOAK_METRICS_TARGET` | `keycloak.yml` | `keycloak:9000` (port de gestion, métriques activées) |
| `APPLICATION_PROBE_TARGETS` | `application-http.yml` | `http://nginx/healthz http://passerelle:3000/health` (URLs séparées par des espaces) |
| `APPLICATION_GRAPHQL_TARGET` | `application-graphql.yml` | `http://gateway:8000/graphql` |

En **mode image**, c'est `docker/entrypoint.sh` qui écrit ces fichiers au démarrage, à partir des
variables ci-dessus ; aucune n'est obligatoire. En **mode compose**, il n'y a pas d'entrypoint :
ce sont deux services one-shot sous profil qui activent les sondes optionnelles —
`docker compose --profile demo up` et `docker compose --profile application up -d`.

**Fichiers `*.local.yml` : l'activation qui ne salit pas le dépôt.** Les jobs à activation
explicite ne lisent pas un nom de fichier mais un motif — `demo*.yml` et
`application-graphql*.yml` — ce qui leur fait prendre, en plus du fichier versionné (`[]`), un
éventuel `demo.local.yml` / `application-graphql.local.yml`. Ces noms sont ignorés par Git
(`.gitignore` racine : `observability/**/*.local.*`), et ce sont eux qu'écrivent les services
one-shot. Avant le 15/09/2026, `demo-targets` recopiait ses cibles **sur** le fichier versionné :
une démonstration laissait le dépôt sale et un `git add -A` distrait y remettait les cibles en
dur. Aucun conteneur n'écrit plus dans un fichier suivi par Git.

Pour activer une sonde à la main, sans profil :

```sh
cp prometheus/targets/application-graphql.yml.example prometheus/targets/application-graphql.local.yml
```

Prometheus relit ce répertoire tout seul (`file_sd`, rafraîchissement par défaut 5 min) : aucun
redémarrage n'est nécessaire. Un motif qui ne correspond à aucun fichier ne déclare aucune cible
et ne produit **aucune** erreur — vérifié sur Prometheus v3.1.0, et figé par la suite `tests/`.

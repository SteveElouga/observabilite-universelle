# prometheus/targets/ — cibles optionnelles, découvertes par fichier

Trois jobs de `prometheus.yml` lisent ce répertoire au lieu d'une liste en dur : `postgres`,
`rabbitmq`, `keycloak`. Ils alimentent les alertes §8.4 (DLQ, échecs d'authentification) et les
dashboards §8.3 (PostgreSQL, RabbitMQ) du consommateur.

**Pourquoi pas des `static_configs`.** Une cible écrite en dur mais absente rend le job *down*,
donc `up == 0`, donc l'alerte « service injoignable » sonne — pour un composant que personne
n'attendait. Un fichier vide (`[]`) ne déclare aucune cible : pas de série, pas de fausse alerte,
et la règle reste écrite, prête à s'allumer.

**Qui les remplit.** `docker/entrypoint.sh`, au démarrage, à partir de variables d'environnement :

| Variable | Écrit | Exemple |
|---|---|---|
| `DATA_SOURCE_NAME` | `postgres.yml` | `postgresql://obs:...@postgres:5432/app?sslmode=disable` |
| `RABBITMQ_METRICS_TARGET` | `rabbitmq.yml` | `rabbitmq:15692` (greffon `rabbitmq_prometheus`) |
| `KEYCLOAK_METRICS_TARGET` | `keycloak.yml` | `keycloak:9000` (port de gestion, métriques activées) |

Aucune de ces variables n'est obligatoire. Les fichiers versionnés ici valent `[]` : c'est l'état
par défaut d'une plateforme qui n'observe encore aucune base, aucun courtier, aucun IdP.

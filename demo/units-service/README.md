# units-service (démonstration d'instrumentation OpenTelemetry)

Petit service Django instrumenté selon la **§10.1** du document maître. Il a deux buts : prouver que la plateforme fonctionne de bout en bout avec une vraie application qui émet de la télémétrie, et servir de **référence copiable** pour instrumenter un projet Django.

L'instrumentation ne met **aucune ligne dans le code applicatif** : tout passe par les variables d'environnement et le wrapper `opentelemetry-instrument` (voir le `Dockerfile`).

## Ce qu'il démontre

À chaque appel de `/demo/commande`, le service émet les trois signaux d'un coup :

1. Une **trace**, auto-instrumentée (aucune ligne de code).
2. Une **métrique métier**, `commandes_creees_total`, avec des labels à faible cardinalité (`statut`, `mode_paiement`), conformément à la règle de cardinalité (§7.3).
3. Un **log JSON structuré** portant le `trace_id`, ce qui rend le passage log vers trace cliquable dans Grafana (§10.5).

L'identifiant à forte cardinalité (`user.id`) est placé en **attribut de span**, jamais en label de métrique. On le retrouve dans Tempo via TraceQL : `{ .user.id = "42" }`.

## Lancer la démo

Le service est déclaré dans `observability/docker-compose.yml` sous le profil `demo` (opt-in). Depuis le dossier `observability/`, avec la pile d'observabilité en marche :

```bash
docker compose --profile demo up -d --build
```

Puis générez de la télémétrie :

```bash
curl http://localhost:8088/demo/commande        # à répéter plusieurs fois
curl http://localhost:8088/sante/               # sonde de vivacité
```

## Ce que vous devez voir

| Signal | Où | Quoi |
|---|---|---|
| Traces | Grafana, Explore, source Tempo | Rechercher le service `units-service` |
| Métriques | Prometheus (`:9090`) ou Grafana | La série `commandes_creees_total` par `statut` et `mode_paiement` |
| Logs | Grafana, Explore, source Loki | Les lignes JSON du service, avec `trace_id`, cliquables vers la trace |

Note sur l'échantillonnage : une trace de `/demo/commande` est rapide et sans erreur, donc seule une fraction est conservée par le tail sampling du Collector. Répétez l'appel plusieurs fois pour en voir apparaître. Les métriques et les logs, eux, remontent toujours.

## Notes

Ce service tourne ici dans le même compose que la plateforme, par simplicité. Un vrai projet **externe et indépendant** se brancherait plutôt par un réseau Docker partagé ou un point d'entrée stable, comme décrit dans le guide `docs/Guide_Utilisation_Plateforme_Observabilite.md`, section « Brancher un projet ».

Gunicorn tourne avec un seul worker : en mono-worker, le wrapper `opentelemetry-instrument` suffit. Pour passer à plusieurs workers, initialisez le SDK dans le hook `post_fork` de `gunicorn.conf.py` (les exporters OpenTelemetry n'aiment pas le fork).

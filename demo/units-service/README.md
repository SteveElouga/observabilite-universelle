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

## Profiling continu (Pyroscope, §10.1 et §10.5)

En plus des trois signaux, le service pousse un **profil de performance continu** vers Pyroscope. Le SDK `pyroscope-io` échantillonne la pile d'exécution et envoie les profils à `pyroscope:4040`. Comme Pyroscope s'appuie sur py-spy pour lire la pile du processus, le conteneur reçoit la capacité `SYS_PTRACE` et le SDK est initialisé dans le hook `post_fork` de gunicorn, une fois par worker, car l'initialiser avant le fork laisserait un état cassé.

Le paquet `pyroscope-otel` ajoute un `PyroscopeSpanProcessor` au tracer provider de l'auto-instrumentation. Il pose l'attribut `pyroscope.profile.id` sur le span racine de chaque trace, ce qui crée le **lien trace vers profil** : depuis une trace lente dans Tempo, on saute au profil correspondant dans Pyroscope grâce à `tracesToProfiles`, déjà configuré dans les datasources Grafana (§10.5). Autrement dit, on ne répond plus seulement à « quelle requête est lente » mais à « quelle fonction la ralentit ».

Dans Grafana, ouvrez la source Pyroscope pour voir le graphe de flammes de `units-service`, ou partez d'une trace dans Tempo et suivez le lien vers son profil.

Pour un profil **spectaculaire**, appelez `/demo/calcul` : cet endpoint brûle volontairement du CPU dans la fonction `_calcul_intensif` (boucle Python pure, bornée par le paramètre `?n=`, défaut 5 M). En le sollicitant en rafale, une seule fonction domine alors tout le graphe de flammes — l'effet classique du profiling qui pointe « la » ligne coûteuse. Les autres endpoints ne calculant presque rien, leur profil CPU reste discret.

## Notes

Ce service tourne ici dans le même compose que la plateforme, par simplicité. Un vrai projet **externe et indépendant** se brancherait plutôt par un réseau Docker partagé ou un point d'entrée stable, comme décrit dans le guide `docs/Guide_Utilisation_Plateforme_Observabilite.md`, section « Brancher un projet ».

Gunicorn tourne avec un seul worker. Le hook `post_fork` de `gunicorn.conf.py` initialise Pyroscope par worker ; le même endroit sert à ré-initialiser le SDK OpenTelemetry si vous passez à plusieurs workers, car les exporters n'aiment pas le fork.

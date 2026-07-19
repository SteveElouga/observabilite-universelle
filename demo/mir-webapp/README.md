# mir-webapp (démonstration RUM frontend)

Petite application Angular instrumentée selon la **§10.2** du document maître. Elle complète `units-service` (le backend de démo) en prouvant la partie **côté navigateur** de l'observabilité : expérience réelle utilisateur, erreurs JavaScript, et surtout la **propagation de trace** du clic jusqu'à la requête Django.

## Ce qu'elle démontre

1. **RUM avec Grafana Faro** : Web Vitals, erreurs JavaScript, sessions, envoyés au récepteur Faro d'Alloy.
2. **Trace de bout en bout** : le bouton « Appeler le backend » émet une requête vers `units-service`. Faro pose l'en-tête W3C `traceparent`, et comme l'appel passe par le proxy nginx (même origine), il arrive à Django avec ce contexte. La trace du navigateur et la trace Django ne forment alors **qu'une seule trace** dans Tempo.
3. **Suivi d'erreurs avec GlitchTip** : le bouton « Déclencher une erreur JS » lève une exception, captée par Faro et, si un DSN est configuré, remontée à GlitchTip.

## Prérequis

La démo `units-service` (backlog #3) doit être présente et lancée, car `mir-webapp` appelle son endpoint. Les deux vivent sous le profil `demo`.

## Lancer la démo

Depuis le dossier `observability/`, avec la pile d'observabilité en marche :

```bash
docker compose --profile demo up -d --build
```

Puis ouvrez http://localhost:8090 et cliquez sur les deux boutons.

## Ce que vous devez voir dans Grafana

| Signal | Où | Quoi |
|---|---|---|
| Trace de bout en bout | Explore, source Tempo | Après « Appeler le backend » : une trace unique du navigateur (`mir-webapp`) jusqu'à `units-service` |
| Expérience réelle et erreurs | Explore, source Loki | Les événements Faro : Web Vitals, et l'erreur JS après le second bouton |
| Erreurs (optionnel) | GlitchTip (`:8000`) | L'erreur JS regroupée, si un DSN est configuré |

## Choix techniques

nginx sert l'application et **proxifie `/api` vers `units-service`**. Cela garde l'appel en même origine, donc pas de CORS ni de requête préflight, et l'en-tête `traceparent` est transmis tel quel au backend. Faro, lui, poste directement sur `http://localhost:12347/collect` : le récepteur d'Alloy accepte déjà le CORS de toutes origines (à restreindre en production, §7.4).

## Activer GlitchTip

Créez un projet dans GlitchTip (`:8000`), récupérez son DSN, collez-le dans `src/environments/environment.ts` (champ `glitchtipDsn`), puis reconstruisez l'image. Sans DSN, la démo fonctionne quand même : les erreurs restent captées par Faro.

## Notes

Ce frontend n'a pas pu être compilé dans l'environnement de préparation (accès npm indisponible). La recette (`npm install` puis build, ou build Docker) se fait sur votre poste ; prévoyez un ou deux ajustements de versions au premier build, comme pour tout scaffold Angular fait à la main.

En développement pur, `npm install` puis `npm start` lance `ng serve` sur le port 4200 ; dans ce mode il faut configurer le proxy de `ng serve` pour `/api`, sinon utilisez simplement la voie Docker ci-dessus qui embarque déjà le proxy nginx.

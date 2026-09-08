# Durcissement avant exposition

Cette surcouche fait passer la plateforme de la configuration de laboratoire, où tout est en clair et sans authentification, à une configuration exposable. Elle répond au lot #9 du backlog et à la section 7.4 du document maître, ainsi qu'aux écarts de sécurité listés dans le bilan. Elle est volontairement séparée du compose de base, pour que le lab reste simple et que le durcissement s'active à la demande.

## Ce que ça change

Un reverse proxy Caddy devient le point d'entrée unique. Il termine le TLS et n'expose vers l'extérieur que ce qui doit l'être. Les ports des services internes ne sont plus publiés sur l'hôte : Prometheus, Loki, Tempo, Pyroscope et Alertmanager ne sont plus joignables directement, seulement par Grafana sur le réseau Docker, ce qui réduit fortement la surface d'attaque. Restent accessibles de l'extérieur, en HTTPS et via Caddy, l'interface Grafana, l'interface GlitchTip, et le point de collecte du navigateur pour Faro.

## Mise en route

Tout se fait depuis le dossier `observability/`. Docker Compose 2.24 ou plus récent est nécessaire, à cause du tag `!override` qui retire les ports publiés du compose de base.

**1. Déclarer les noms locaux.** Les domaines `*.localhost` ne sont pas résolus automatiquement par le système sous macOS ni Windows (seul un navigateur comme Chrome les mappe parfois vers la boucle locale, et pas toujours). Déclarez les donc explicitement une fois pour toutes :

```bash
# macOS et Linux
echo "127.0.0.1 grafana.localhost glitchtip.localhost faro.localhost" | sudo tee -a /etc/hosts
```

Sous Windows, ajoutez la même ligne à `C:\Windows\System32\drivers\etc\hosts`.

**2. Démarrer la pile durcie.** Le `--force-recreate` est important : sans lui, un conteneur Caddy déjà présent d'un lancement antérieur peut être réutilisé sans publier ses ports 80 et 443, et plus rien n'est joignable.

```bash
docker compose -f docker-compose.yml -f hardening/docker-compose.hardening.yml up -d --force-recreate
```

Vérifiez que Caddy publie bien ses ports sur l'hôte :

```bash
docker ps --format "{{.Names}}: {{.Ports}}" | grep caddy
# attendu : 0.0.0.0:443->443/tcp (et 80). Si vous voyez seulement "80/tcp, 443/tcp"
# sans la flèche "->", les ports ne sont pas publiés : relancez avec --force-recreate.
```

**3. Accéder.** Ouvrez `https://grafana.localhost`, `https://glitchtip.localhost` et `https://faro.localhost`. Caddy signe en local avec une autorité de certification qu'il gère lui même : le navigateur affiche un avertissement, cliquez « Paramètres avancés » puis « Continuer ». C'est attendu en laboratoire.

## Passage en production

Remplacez les domaines `*.localhost` du `Caddyfile` par vos vrais domaines et retirez les directives `tls internal`. Caddy provisionne alors automatiquement des certificats Let's Encrypt, à condition que les domaines pointent vers la machine et que les ports 80 et 443 soient joignables. Renseignez un email dans le bloc global du `Caddyfile` pour Let's Encrypt.

Pour un accès direct aux backends sans passer par Grafana, décommentez les blocs correspondants du `Caddyfile` et protégez les par authentification basique. Générez le condensé du mot de passe avec `docker run --rm caddy:2-alpine caddy hash-password --plaintext 'votre-mot-de-passe'`, puis renseignez `BASIC_AUTH_USER` et `BASIC_AUTH_HASH` dans le fichier `.env` du dossier `observability/`.

## Restreindre les origines du navigateur

Le récepteur Faro accepte par défaut toutes les origines, ce qui convient au lab mais pas à la production. Dans `alloy-config.alloy`, remplacez `cors_allowed_origins = ["*"]` par le seul domaine de votre frontend, par exemple `cors_allowed_origins = ["https://app.exemple.com"]`, afin qu'un site tiers ne puisse pas pousser d'événements en votre nom.

## Authentification et rôles Grafana

Grafana garde sa propre authentification, protégée par le mot de passe administrateur. Avant une exposition réelle, définissez un mot de passe fort et propre à l'environnement, créez des comptes avec des rôles distincts de consultation et d'édition, et activez idéalement une authentification unique par OAuth ou OpenID Connect pour ne pas multiplier les mots de passe.

## Chiffrement au repos

Le chiffrement au repos ne se fait pas dans le compose mais au niveau de l'hôte, car c'est là qu'il est fiable. Chiffrez le système de fichiers ou le disque qui héberge les volumes Docker, par exemple avec LUKS sous Linux, ou utilisez un stockage déjà chiffré chez votre hébergeur. Pour la base de données GlitchTip, un volume chiffré au niveau de l'hôte suffit dans la plupart des cas ; un chiffrement au niveau de la base n'est utile que pour des exigences particulières. L'essentiel est que la décision soit prise explicitement et non oubliée.

## Sauvegarde

Le script `backup.sh` sauvegarde les volumes à état qui ne sont pas reconstructibles depuis le dépôt, à savoir les tableaux de bord créés à la main, l'historique GlitchTip et la configuration d'Uptime Kuma. Planifiez le sur l'hôte, par exemple chaque nuit. Les données de télémétrie ne sont pas sauvegardées, leur perte étant jugée acceptable ; adaptez ce choix à votre politique. Vérifiez régulièrement qu'une restauration fonctionne, une sauvegarde jamais testée n'est pas une sauvegarde.

Si plusieurs projets Compose nommés `observability` tournent sur la même machine (par exemple un second clone ou une vérification en parallèle), le script ne devine pas lequel sauvegarder : il liste les volumes candidats et ignore ceux qui restent ambigus. Précisez `COMPOSE_PROJECT_NAME` pour trancher : `COMPOSE_PROJECT_NAME=observability ./hardening/backup.sh`.

## Dépannage : accès impossible

Si `https://grafana.localhost` reste injoignable, testez la chaîne en contournant complètement la résolution de nom :

```bash
curl -k --resolve grafana.localhost:443:127.0.0.1 https://grafana.localhost -I
```

- Réponse `HTTP/2 302` vers `/login` (avec `via: ... Caddy`) : Caddy sert correctement Grafana. Il ne manque donc que la résolution du nom, c'est à dire l'étape `/etc/hosts` ci-dessus. Après l'avoir ajoutée, rechargez `https://grafana.localhost`.
- `Connection refused` : Caddy ne publie pas le port 443 sur l'hôte. Recréez le : `docker compose -f docker-compose.yml -f hardening/docker-compose.hardening.yml up -d --force-recreate caddy`, puis revérifiez ses ports (`docker ps ... | grep caddy` doit montrer `0.0.0.0:443->443/tcp`).
- `Could not resolve host` malgré le `--resolve` : très rare ; vérifiez que Docker et le conteneur Caddy tournent (`docker ps | grep caddy`).

Pour revenir simplement à la configuration de laboratoire, avec Grafana directement sur `http://localhost:3000`, arrêtez la pile durcie puis relancez la base seule :

```bash
docker compose -f docker-compose.yml -f hardening/docker-compose.hardening.yml down
docker compose up -d
```

## Ce qui reste hors de cette surcouche

La supervision indépendante de la plateforme repose sur Uptime Kuma hébergé hors infrastructure, décrit dans `../uptime-kuma/README.md`. L'analyse des dépendances et des images, ainsi que le scan de secrets en intégration continue, relèvent du lot suivant. Enfin, tout ce qui est organisationnel, comme la gestion des accès du personnel et les politiques écrites, dépasse le périmètre de cette configuration technique.

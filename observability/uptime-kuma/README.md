# Uptime Kuma hébergé hors infra

## Pourquoi hors infra

Prometheus, Blackbox et Alertmanager tournent **sur le serveur qu'ils surveillent**. Si ce
serveur tombe (panne réseau, coupure, plantage Docker), ils tombent avec lui et ne peuvent
plus alerter. C'est l'angle mort classique de toute supervision embarquée.

Uptime Kuma sur une **machine séparée** couvre cet angle mort. Depuis l'extérieur, il voit ce
qu'un utilisateur voit et détecte l'indisponibilité même quand la plateforme entière est à
terre. Il tient le rôle de « dead man's switch » que la pile locale ne peut pas assurer.

Règle : héberger Uptime Kuma **ailleurs** que la plateforme, idéalement chez un autre
fournisseur ou dans une autre région, pour ne pas partager le même point de défaillance
(alimentation, réseau, hyperviseur).

## Où l'héberger

N'importe quelle petite machine suffit (1 vCPU, 512 Mo) : une VM cloud bon marché, un VPS, un
Raspberry Pi sur un autre site, ou un service géré. Le seul impératif est qu'elle soit
**indépendante** de la plateforme et qu'elle puisse joindre ses URLs publiques.

## Déploiement

Sur la machine externe (pas sur le serveur de la plateforme) :

```bash
docker compose -f docker-compose.external.yml up -d
```

Ouvrez ensuite `http://IP_DE_CETTE_MACHINE:3001` et créez le compte administrateur au premier
lancement. En production, placez cette interface derrière HTTPS et une authentification.

## Moniteurs à configurer

Créez un moniteur par surface exposée au public. Type **HTTP(s)**, intervalle 60 s :

| Nom | URL (adaptez à votre domaine) | Ce qu'il vérifie |
|---|---|---|
| Grafana | `https://grafana.example.com/api/health` | Les tableaux de bord sont accessibles |
| Application | `https://app.example.com/` | Le frontend répond |
| API | `https://api.example.com/sante/` | Le backend répond |

Ajoutez un moniteur **Push** (heartbeat) comme dead man's switch actif : la plateforme envoie
un battement régulier à Uptime Kuma ; si le battement cesse, Uptime Kuma alerte. Utile pour
détecter un gel silencieux qui laisserait quand même répondre le port HTTP.

## Notifications vers Slack

Dans **Settings → Notifications → Add**, choisissez Slack, collez l'URL de webhook entrant du
canal `#alertes` (le même canal que celui d'Alertmanager, ou un canal dédié aux sondes
externes), puis rattachez cette notification à chaque moniteur.

Ainsi, deux chemins d'alerte indépendants arrivent dans Slack : Alertmanager depuis
l'intérieur (symptômes RED, budgets SLO) et Uptime Kuma depuis l'extérieur (indisponibilité
vue du dehors). Si le premier se tait parce que le serveur est à terre, le second parle.

## Complémentarité avec Blackbox

Blackbox (dans la pile) sonde les endpoints en HTTP **depuis l'intérieur du réseau**, sans
instrumentation, et alimente Prometheus et ses alertes (`prometheus/rules/probes.yml`). Uptime
Kuma sonde **depuis l'extérieur**. Les deux sont des vues « boîte noire » ; seule celle
d'Uptime Kuma survit à la chute du serveur surveillé.

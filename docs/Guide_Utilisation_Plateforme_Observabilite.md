# Guide d'utilisation de la plateforme d'observabilité

| Rubrique | Valeur |
|---|---|
| Nature du document | Guide d'utilisation et référence d'intégration |
| Public visé | Personnes chargées de l'observabilité, architectes, développeurs, exploitants |
| Version | 0.1 (19/07/2026) |
| Documents liés | Document maître d'architecture (le « pourquoi » de fond), README de la pile (mise en route technique) |

Ce guide explique comment brancher n'importe quel projet sur la plateforme d'observabilité et comment s'en servir pour obtenir une observabilité propre. La plateforme est un projet indépendant, pensé pour être partagé par plusieurs projets à la fois. Chaque projet reste maître de son code et se contente d'émettre sa télémétrie vers des points d'entrée stables, exactement comme on consomme une API.

## 1. Comment lire ce guide

Le document suit un ordre volontaire. Les premières sections posent les idées et le vocabulaire, les suivantes deviennent opérationnelles.

| Si vous voulez | Allez à |
|---|---|
| Comprendre à quoi sert la plateforme et son vocabulaire | Sections 3 et 4 |
| Vérifier ce qu'il faut avant de commencer | Section 2 |
| Brancher votre projet rapidement | Sections 5 et 6 |
| Garder les données de chaque projet séparées | Section 7 |
| Émettre une télémétrie propre et bien nommée | Section 8 |
| Enquêter sur un incident | Section 9 |
| Comprendre les alertes et les objectifs de fiabilité | Section 10 |
| Préparer la mise en production | Section 12 |
| Savoir où va la solution demain | Section 13 |

La plateforme repose sur un principe simple. On instrumente une seule fois avec un standard ouvert, OpenTelemetry, puis tout transite par un point de collecte central qui range chaque signal dans la base adaptée, et Grafana sert de cockpit unique pour tout relier. Ce principe vous protège du verrouillage chez un éditeur et garde la facture sous contrôle.

## 2. Prérequis

### 2.1 Côté plateforme

La plateforme doit être en service. Sur un serveur unique, elle se lance avec Docker et Docker Compose. La mise en route détaillée figure dans le README de la pile. Les valeurs d'exemple des secrets se copient depuis le fichier `.env.example` vers un fichier `.env` local qui ne part jamais dans Git.

Un ordre de grandeur des ressources, à titre indicatif, pour la topologie serveur unique.

| Ressource | Recommandation | Remarque |
|---|---|---|
| Mémoire | 16 Go de préférence | La pile d'observabilité seule consomme environ 2,5 Go, le reste laisse de la marge aux projets observés |
| Disque | 100 Go SSD selon la rétention | Le coût de stockage dépend du volume ingéré multiplié par la durée de conservation |
| Processeur | 4 cœurs virtuels | Suffisant pour un serveur unique |

### 2.2 Côté projet à brancher

Un projet n'a presque rien à installer pour émettre sa télémétrie. Il lui faut la bibliothèque d'instrumentation OpenTelemetry de son langage, pour le backend, et le SDK web Grafana Faro pour le frontend. Le reste passe par de la configuration, principalement des variables d'environnement qui pointent vers les points d'entrée de la plateforme.

### 2.3 Ce qu'il est utile de connaître

Deux notions rendent la suite plus claire. La première est celle des signaux d'observabilité (métriques, logs, traces, et quelques autres), détaillée en section 3. La seconde est le protocole OTLP, le format standard par lequel les applications envoient leur télémétrie. Ces deux points sont expliqués plus bas, aucune connaissance préalable n'est exigée.

### 2.4 Un mot sur macOS

Lorsque la plateforme tourne sous Docker Desktop sur un Mac, les conteneurs vivent dans une machine virtuelle Linux. Deux points d'attention se présentent. D'abord, cette machine doit avoir l'autorisation d'accéder au dossier qui contient la pile, sinon les montages de fichiers échouent. On accorde l'accès complet au disque à Docker dans les réglages de confidentialité, puis on redémarre Docker, ou bien on place la pile dans un dossier non protégé par le système. Ensuite, l'exportateur de métriques système ne doit pas utiliser de propagation de montage particulière sur la racine, réglage déjà corrigé dans la pile.

## 3. Les concepts

### 3.1 Les signaux

L'observabilité s'appuie sur plusieurs types de données, appelés signaux. Chacun répond à une question différente. Ensemble, ils permettent de passer d'une vue d'ensemble à la cause précise d'un problème.

| Signal | Ce qu'il apporte | Sa faiblesse |
|---|---|---|
| Métriques | Des nombres agrégés dans le temps (requêtes par seconde, latence, taux d'erreur). Vue d'ensemble et alertes | Elles disent qu'un problème existe, pas pourquoi |
| Logs | Des lignes horodatées qui décrivent un événement précis, avec tout le contexte | Volumineux, donc coûteux à conserver |
| Traces | Le parcours d'une requête à travers tous les services, étape par étape | Demande une propagation de contexte de bout en bout |
| Profils | La consommation processeur ou mémoire au niveau de la fonction de code | Signal encore récent, réservé aux besoins d'optimisation |
| Erreurs et crashs | Les exceptions regroupées et priorisées, avec la pile d'appels et la version fautive | Distinct des logs, c'est un vrai suivi de bugs |
| Expérience réelle (RUM) | Ce que vit l'utilisateur dans son navigateur ou son téléphone | Seule vue côté client, à relier au reste |

### 3.2 La corrélation, le vrai atout

Collecter les signaux ne suffit pas. Leur valeur vient de leur mise en relation. La plateforme propage des identifiants communs, en particulier l'identifiant de trace, que l'on retrouve à la fois dans les traces et dans les logs. Depuis une métrique de latence qui grimpe, on saute vers une trace représentative grâce à un exemplar. Depuis cette trace, on ouvre les logs exacts de l'opération, puis le profil de la fonction qui consomme le processeur. C'est cette navigation d'un signal à l'autre qui transforme trois bases séparées en une véritable plateforme.

### 3.3 Le pipeline en cinq couches

Quelle que soit la technologie, une chaîne d'observabilité suit toujours le même trajet. Retenez ce trajet, c'est la colonne vertébrale de la plateforme.

1. **Les sources.** Le code et l'infrastructure émettent les signaux. Le code s'instrumente avec OpenTelemetry. L'infrastructure expose son état par des exportateurs dédiés.
2. **La collecte.** Un collecteur central reçoit toute la télémétrie, la filtre, l'échantillonne, l'enrichit, puis la route. Il découple les applications du stockage. Changer de base de stockage revient à changer une configuration du collecteur, jamais le code.
3. **Le stockage.** Chaque signal va dans une base spécialisée. C'est ici que se joue l'essentiel du coût, à savoir le volume conservé multiplié par sa durée de rétention.
4. **La visualisation.** Une interface unique interroge toutes les bases, affiche les tableaux de bord et permet de naviguer d'un signal à l'autre.
5. **L'alerte et la réponse.** Des règles évaluent les données en continu et lèvent des alertes. Un système d'astreinte route la bonne alerte vers la bonne personne.

Un principe traverse ces cinq couches. On ne branche jamais une application directement sur le stockage. Tout passe par le collecteur, qui reste le point de contrôle du volume, du coût et du masquage des données sensibles.

## 4. Les technologies de la plateforme

Cette section présente chaque brique. Pour chacune, vous trouverez son rôle, sa place dans la chaîne, la raison de son choix face aux alternatives, et une idée de son fonctionnement. Toutes ces briques sont gratuites, open source et auto-hébergeables.

### 4.1 OpenTelemetry, l'instrumentation

**Rôle et place.** OpenTelemetry est la fondation, tout en haut de la chaîne, au niveau des sources. C'est lui qui fait émettre les métriques, les logs et les traces par le code.

**Pourquoi ce choix.** C'est le standard ouvert du secteur, gouverné par la fondation CNCF, adopté par la moitié à deux tiers des organisations et accepté par tous les grands éditeurs. Son intérêt décisif tient en une phrase. On instrumente son code une seule fois, avec des interfaces qui ne mentionnent aucun fournisseur, donc on reste libre de changer de stockage sans jamais réécrire l'application. Un agent propriétaire ferait l'inverse et enfermerait le projet.

**Fonctionnement.** Deux modes coexistent. L'auto-instrumentation ajoute des sondes sans toucher au code, ce qui suffit pour démarrer et couvre déjà les cadres applicatifs courants (serveur web, appels de base de données, clients réseau). L'instrumentation manuelle laisse le développeur ajouter des mesures métier, indispensables pour donner du sens business à la télémétrie.

### 4.2 Le Collector, le pipeline central

**Rôle et place.** Le collecteur OpenTelemetry se place entre les applications et le stockage, au cœur de la couche de collecte. Il reçoit la télémétrie au format OTLP, la traite, puis la range dans chaque base.

**Pourquoi ce choix.** Il est neutre, gratuit, et sait recevoir, transformer et router vers plusieurs bases à la fois. Surtout, il est le point unique où l'on décide quoi garder. C'est donc lui qui pilote le volume, et par conséquent le coût. Sans ce point de contrôle, chaque application déciderait dans son coin, sans filtrage ni masquage commun.

**Fonctionnement.** Le collecteur applique une suite de traitements. Il filtre le bruit, comme les appels de vérification de santé. Il échantillonne les traces pour n'en conserver qu'une part représentative. Il calcule des métriques dérivées des traces avant l'échantillonnage, pour ne pas fausser les chiffres. Il masque les champs sensibles, ce qui en fait le point de conformité. Puis il envoie chaque signal vers sa base.

### 4.3 Prometheus et Mimir, les métriques

**Rôle et place.** Ces deux outils stockent et interrogent les séries temporelles, dans la couche de stockage. Ils alimentent les tableaux de bord et les alertes.

**Pourquoi ce choix.** Prometheus est le standard incontesté des métriques, avec son langage de requête PromQL connu de tous et un immense catalogue d'exportateurs. Sur un serveur unique, Prometheus seul suffit largement. Pour la longue conservation et le passage à l'échelle, on lui adjoint Grafana Mimir, qui apporte la rétention longue durée, la haute disponibilité et le cloisonnement par projet. Mimir est l'extension naturelle de Prometheus, ce qui évite de changer de modèle.

**Fonctionnement.** Prometheus va chercher les métriques à intervalle régulier auprès des cibles qui les exposent. Les exportateurs traduisent l'état d'un système en métriques lisibles, par exemple l'exportateur système pour la machine, l'exportateur de conteneurs, ou les exportateurs par technologie comme celui de PostgreSQL.

### 4.4 Loki, les logs

**Rôle et place.** Loki centralise et indexe les logs, dans la couche de stockage. C'est le premier réflexe de débogage détaillé.

**Pourquoi ce choix.** Loki n'indexe que quelques étiquettes et garde le corps du message compressé sur un stockage objet bon marché. Le coût de conservation reste donc très bas, contrairement à une indexation plein texte comme celle d'Elasticsearch, plus puissante en recherche mais bien plus gourmande. Loki s'intègre nativement à Grafana et partage la logique de Prometheus, ce qui rend la corrélation naturelle.

**Fonctionnement.** La règle d'or est d'envoyer des logs structurés au format JSON, avec l'identifiant de trace injecté dans chaque ligne. On garde peu d'étiquettes pour éviter l'explosion du nombre de séries, et l'on place les champs très variés, comme l'identifiant d'utilisateur, dans les métadonnées structurées plutôt qu'en étiquette.

### 4.5 Tempo, les traces

**Rôle et place.** Tempo stocke les traces distribuées, dans la couche de stockage. Il fait le pont entre la vue d'ensemble et le détail.

**Pourquoi ce choix.** Tempo n'indexe que l'identifiant de trace et pose tout le reste sur stockage objet, ce qui le rend très économique. Il propose une recherche par TraceQL, s'intègre à Grafana, et reçoit les exemplars venus des métriques, ce qui permet de sauter d'une courbe de latence à une trace en un clic.

**Fonctionnement.** Une trace suit une requête de bout en bout. Chaque étape est un span qui porte l'identifiant de trace, sa durée et le service concerné. Pour maîtriser le volume, la plateforme conserve la totalité des traces en erreur ou lentes, et seulement une faible part des traces normales.

### 4.6 Pyroscope, les profils

**Rôle et place.** Pyroscope échantillonne en continu la pile d'appels pour savoir quelle fonction consomme le processeur ou la mémoire, dans la couche de stockage. Là où la trace pointe le service lent, le profil pointe la ligne de code.

**Pourquoi ce choix.** C'est l'outil de profiling continu le plus utilisé de l'écosystème, intégré à Grafana, avec des graphiques de flamme et une corrélation vers les traces. Il n'est pas indispensable au démarrage, on le réserve à la phase d'optimisation, mais il devient très rentable pour réduire une facture de calcul.

**Fonctionnement.** Un SDK dans l'application prélève régulièrement l'état de la pile d'appels et pousse ces échantillons vers le serveur Pyroscope, qui les agrège en graphiques lisibles.

### 4.7 GlitchTip, le suivi d'erreurs

**Rôle et place.** GlitchTip capture les exceptions du backend, du navigateur et du mobile, les regroupe et les priorise. C'est un signal à part, orienté développeur, distinct des logs.

**Pourquoi ce choix.** Deux options se présentaient. Sentry auto-hébergé est la référence, très complet, mais lourd à opérer, avec de nombreux conteneurs et plusieurs gigaoctets de mémoire. GlitchTip offre l'essentiel du même service, se contente de quelques conteneurs et de peu de mémoire, et reste compatible avec les SDK de Sentry. On change juste une adresse de connexion, sans toucher au code. La plateforme retient GlitchTip pour rester légère, et laisse la porte ouverte à Sentry si le besoin de relecture de session ou de profiling approfondi se fait sentir.

**Fonctionnement.** Chaque projet reçoit une adresse de connexion, appelée DSN. Le SDK de l'application envoie les exceptions vers GlitchTip, qui dédoublonne, compte les utilisateurs touchés et relie l'erreur à la version du logiciel.

### 4.8 Grafana Faro, l'expérience réelle côté web

**Rôle et place.** Faro mesure l'expérience réelle dans le navigateur, au niveau des sources, côté client. Il capte les temps de chargement, les indicateurs Core Web Vitals, les erreurs JavaScript et les traces des appels du frontend.

**Pourquoi ce choix.** Faro est le SDK web de Grafana, gratuit, qui envoie ses données dans les mêmes bases que le reste. Le frontend se retrouve donc corrélé au backend dans le même Grafana, ce qui évite un outil séparé pour la vue client.

**Fonctionnement.** Le SDK s'ajoute à l'application web et envoie ses données à un récepteur dédié porté par Grafana Alloy. Quand une trace démarre dans le navigateur, elle se relie à la trace du backend grâce à la propagation de contexte, ce qui donne une seule trace du clic de l'utilisateur jusqu'à la base de données.

### 4.9 Uptime Kuma et Blackbox, la vue de l'extérieur

**Rôle et place.** Ces outils testent le service depuis l'extérieur, en continu, dans la couche d'alerte au sens large. Ils vérifient qu'un point d'entrée répond et qu'un certificat n'expire pas.

**Pourquoi ce choix.** Uptime Kuma est très populaire, simple à installer, propose des sondes variées, des pages de statut et des notifications. Le Blackbox Exporter complète en exposant ses sondes sous forme de métriques Prometheus, ce qui unifie alertes et tableaux de bord. Cette vue extérieure détecte les pannes avant les utilisateurs et reste utile même quand toute l'infrastructure interne est à l'arrêt.

**Fonctionnement.** Une sonde interroge périodiquement une adresse publique et vérifie la réponse. Une bonne pratique consiste à héberger cette surveillance ailleurs que sur l'infrastructure surveillée, pour qu'elle voie la panne de l'extérieur.

### 4.10 Grafana, le cockpit

**Rôle et place.** Grafana est l'interface unique, dans la couche de visualisation. Il interroge toutes les bases, affiche les tableaux de bord et permet la navigation d'un signal à l'autre.

**Pourquoi ce choix.** C'est le standard de la visualisation open source. Il se connecte à toutes les bases de la plateforme, propose un écosystème énorme de tableaux de bord prêts à l'emploi, et surtout offre nativement la corrélation entre métrique, trace et log. Un point d'entrée unique évite de jongler entre dix onglets pendant un incident.

**Fonctionnement.** Grafana s'appuie sur des sources de données déclarées en configuration. Ces sources décrivent aussi les liens de corrélation, par exemple le passage d'un log vers sa trace. Tout est versionné en code, ce qui rend la plateforme reproductible.

### 4.11 Alertmanager et l'astreinte

**Rôle et place.** L'alerte se joue en deux temps, dans la dernière couche. D'abord la détection, assurée par Alertmanager et par les règles d'alerte de Grafana. Ensuite le routage vers la bonne personne, assuré par un outil d'astreinte.

**Pourquoi ce choix.** Alertmanager est le standard pour regrouper, dédoublonner et router les alertes issues des métriques. Pour l'astreinte, la plateforme vise OneUptime, un outil libre et activement maintenu qui gère les gardes, les escalades et les notifications par appel ou message, avec en prime la gestion d'incidents et les pages de statut. À noter, l'ancien choix naturel de l'écosystème Grafana pour l'astreinte a été archivé au premier trimestre 2026, il n'est donc plus retenu pour un nouveau déploiement.

**Fonctionnement.** Les règles évaluent les données en continu et lèvent une alerte quand un symptôme apparaît. La bonne pratique consiste à alerter sur les symptômes vécus par l'utilisateur, définis par des objectifs de fiabilité, plutôt que sur chaque cause technique, sous peine de noyer l'équipe sous des alertes ignorées. Chaque alerte porte une fiche d'action, pour savoir quoi faire.

### 4.12 Sloth, les objectifs de fiabilité

**Rôle et place.** Sloth définit les objectifs de fiabilité et le budget d'erreur associé, au-dessus de Prometheus et de Grafana.

**Pourquoi ce choix.** Sloth génère les règles et les alertes à partir d'une simple description en YAML. Il traduit la technique en langage produit, en répondant à la question de savoir si l'on tient sa promesse de fiabilité. Il permet d'alerter sur la vitesse de consommation du budget d'erreur, une approche bien plus fine qu'un seuil arbitraire.

**Fonctionnement.** On décrit un objectif, par exemple un certain pourcentage de requêtes réussies sur une période. Sloth en déduit les règles Prometheus et les tableaux de bord qui suivent le budget d'erreur restant.

## 5. Référence des points d'entrée

Cette section décrit les points d'entrée publics de la plateforme, à la manière d'une référence d'API. Un projet qui respecte ces contrats est branché correctement. Les noms d'hôte donnés supposent que le projet joint la plateforme par le réseau interne (voir la section 6). En publication sur l'hôte, on remplace le nom d'hôte par celui de la machine.

### 5.1 Traces, métriques et logs (OTLP)

C'est le point d'entrée principal, servi par le Collector.

| Élément | Valeur |
|---|---|
| Protocole HTTP | Port 4318, chemins `/v1/traces`, `/v1/metrics`, `/v1/logs` |
| Protocole gRPC | Port 4317 |
| En-tête de contenu HTTP | `application/x-protobuf` ou `application/json` |
| Attribut requis | `service.name`, le nom du service émetteur |
| Attributs recommandés | `deployment.environment` (par exemple `dev` ou `prod`), `service.version`, `service.namespace` (le projet, voir section 7) |

La façon propre de configurer un service consiste à renseigner des variables d'environnement, sans rien coder en dur.

```
OTEL_SERVICE_NAME=nom-du-service
OTEL_RESOURCE_ATTRIBUTES=service.namespace=mon-projet,deployment.environment=dev
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_SDK_DISABLED=false
```

Pour vérifier que le chemin fonctionne, on peut envoyer une trace de démonstration. Elle est marquée en erreur et volontairement lente, afin de traverser l'échantillonnage à coup sûr.

```bash
TID=$(openssl rand -hex 16); NOW=$(date +%s)000000000
curl -s -o /dev/null -w "TraceID=$TID HTTP %{http_code}\n" \
  http://localhost:4318/v1/traces -H 'Content-Type: application/json' \
  -d '{"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"demo"}}]},"scopeSpans":[{"spans":[{"traceId":"'"$TID"'","spanId":"'"$(openssl rand -hex 8)"'","name":"demo","kind":2,"startTimeUnixNano":"'"$NOW"'","endTimeUnixNano":"'"$((NOW+600000000))"'","status":{"code":2}}]}]}]}'
```

La réponse attendue est un code 200. La trace apparaît dans Grafana au bout d'une vingtaine de secondes, le temps que l'échantillonnage rende sa décision.

### 5.2 Expérience réelle web (Faro)

| Élément | Valeur |
|---|---|
| Point d'entrée | Port 12347, récepteur Faro porté par Alloy |
| Émetteur | SDK Grafana Faro dans l'application web |
| Données envoyées | Erreurs JavaScript, indicateurs Core Web Vitals, traces des appels du frontend |

Le SDK se configure avec l'adresse du récepteur, le nom de l'application et sa version. La propagation de contexte relie la trace du navigateur à celle du backend.

### 5.3 Profils (Pyroscope)

| Élément | Valeur |
|---|---|
| Point d'entrée | Port 4040 |
| Émetteur | SDK Pyroscope dans l'application |
| Réglage | Nom de l'application et adresse du serveur |

### 5.4 Erreurs (GlitchTip)

| Élément | Valeur |
|---|---|
| Interface | Port 8000 |
| Émetteur | SDK compatible Sentry |
| Réglage | Une adresse de connexion, le DSN, propre à chaque projet |

Le DSN se crée dans GlitchTip, un par projet. Le SDK l'utilise pour envoyer les exceptions. Comme les SDK sont ceux de Sentry, aucune adhérence de code n'est créée.

### 5.5 Récapitulatif des ports

| Service | Port | Usage |
|---|---|---|
| Collector OTLP HTTP | 4318 | Traces, métriques, logs envoyés par les applications |
| Collector OTLP gRPC | 4317 | Même usage, en gRPC |
| Alloy, récepteur Faro | 12347 | Expérience réelle web |
| Pyroscope | 4040 | Profils |
| GlitchTip | 8000 | Erreurs et interface de triage |
| Grafana | 3000 | Cockpit de visualisation |
| Prometheus | 9090 | Métriques |
| Loki | 3100 | Logs |
| Tempo | 3200 | Traces |
| Alertmanager | 9093 | Routage des alertes |
| Uptime Kuma | 3001 | Surveillance externe et page de statut |

## 6. Brancher un projet sur la plateforme

La plateforme et le projet à observer sont deux projets distincts. La seule question technique est la manière dont les conteneurs du projet joignent les points d'entrée de la plateforme. Trois méthodes existent. Elles ne s'excluent pas, elles correspondent à des moments différents.

### 6.1 Méthode 1, par les ports publiés sur l'hôte

Le projet pointe vers la machine qui héberge la plateforme, par exemple `host.docker.internal` sous Docker Desktop, sur le port 4318.

| Avantages | Inconvénients |
|---|---|
| Immédiat, aucune configuration réseau | Dépend de la machine hôte |
| Utile pour un premier essai | Le nom d'hôte varie selon le système et n'est pas stable |
| | Convient mal au-delà d'un poste de développement |

### 6.2 Méthode 2, par un réseau Docker partagé

Les deux projets rejoignent un même réseau Docker déclaré à part. Le projet joint alors le collecteur par son nom de service, par exemple `otel-collector`, sur le port 4318, sans passer par l'hôte.

| Avantages | Inconvénients |
|---|---|
| Nom d'hôte stable, par nom de service | Demande de créer le réseau et de l'attacher aux deux projets |
| Découplé de la machine | Suppose que les deux projets tournent sur le même hôte Docker |
| Proche du fonctionnement de production | |

### 6.3 Méthode 3, par un point d'entrée stable derrière un proxy

À l'échelle, la plateforme expose un point d'entrée stable, protégé par un proxy avec chiffrement et authentification, ou par un service et une entrée réseau côté Kubernetes. Les projets pointent vers cette adresse, où qu'ils tournent.

| Avantages | Inconvénients |
|---|---|
| Fonctionne entre machines et entre clusters | Demande un proxy et la gestion des certificats |
| Chiffrement et authentification au point d'entrée | Un peu plus d'infrastructure à opérer |
| C'est la vraie cible de production, compatible avec le cloisonnement par projet | |

### 6.4 Recommandation

Pour éviter les tracasseries, la recommandation est claire. En développement local, choisissez la méthode 2, le réseau Docker partagé. Elle est stable, propre, indépendante de la machine, et prépare déjà le modèle de production. En production et à l'échelle, passez à la méthode 3, le point d'entrée stable derrière un proxy. La méthode 1 reste pratique pour un tout premier essai, sans plus.

Le point important est que ce choix ne touche jamais le code des applications. Il se résume à une adresse dans une variable d'environnement.

## 7. L'espace dédié par projet

La plateforme est partagée par plusieurs projets. Il faut donc garantir que les données d'un projet ne se mélangent pas avec celles d'un autre. Le modèle retenu est le cloisonnement par tenant.

### 7.1 Le principe

Chaque projet reçoit un identifiant de tenant. À l'écriture comme à la lecture, la plateforme ne présente à un projet que les données de son tenant. La séparation agit donc dès l'entrée et jusqu'aux requêtes, pas seulement à l'affichage. En pratique, cet identifiant voyage dans un en-tête, `X-Scope-OrgID`, que les bases Loki, Tempo et Mimir comprennent nativement.

### 7.2 Pourquoi ce modèle

Trois raisons motivent ce choix. D'abord, c'est le seul modèle qui empêche vraiment les données de se mélanger, car la séparation est portée par le stockage lui-même. Ensuite, il permet de fixer des quotas et une durée de conservation par projet, si bien qu'un projet très bavard ne pénalise pas les autres. Enfin, il est natif à la pile retenue, ce qui évite d'inventer quoi que ce soit. Les autres options ont été écartées. Une pile complète par projet coûterait beaucoup en ressources et en exploitation pour un résultat équivalent. Une simple étiquette de projet, sans cloisonnement de stockage, n'offrirait qu'une séparation logique, exposée aux fuites entre projets et sans quota.

### 7.3 L'état actuel et la cible

Une nuance honnête s'impose. Le cloisonnement dur des métriques suppose Mimir, qui entre en scène avec la topologie Kubernetes. Sur le serveur unique d'aujourd'hui, où Prometheus fonctionne seul, on applique une étape intermédiaire. Chaque projet reçoit un attribut de projet sur toute sa télémétrie, porté par l'attribut `service.namespace`, et dispose de son propre dossier dans Grafana. Le collecteur associe cet attribut au tenant. Quand Mimir arrive, on passe au cloisonnement dur des métriques sans rien changer au code des applications, puisque tout repose sur des attributs et de la configuration.

Concrètement, un projet renseigne dès aujourd'hui son `service.namespace`, et c'est ce même attribut qui deviendra son tenant à l'échelle. Le geste est fait une fois pour toutes.

## 8. Émettre une télémétrie propre

Une observabilité propre tient à quelques règles simples. Elles évitent les deux principaux écueils, à savoir le coût qui dérape et les données qui deviennent illisibles.

### 8.1 Nommer avec discipline

| Élément | Règle | Exemple |
|---|---|---|
| Nom de service | Un nom clair et stable par service | `gateway-graphql` |
| Nom d'un span | Le nom de l'opération, jamais une valeur qui change | `creerTicket` |
| Métrique métier | Un préfixe propre à votre projet, un vocabulaire cohérent | `monprojet_commandes_total` |
| Attribut | Un nom simple et borné | `projet`, `utilisateur_id` |

### 8.2 La règle numéro un, la cardinalité

C'est le piège le plus courant. Ne placez jamais une valeur très variée, comme un identifiant d'utilisateur, un identifiant de requête ou un identifiant unique, en étiquette de métrique. Chaque valeur crée une nouvelle série et fait exploser le stockage. Ces valeurs se rangent dans les attributs de trace ou dans les métadonnées structurées des logs, où elles restent consultables sans coût de cardinalité. Les étiquettes de métrique doivent rester bornées, par exemple le service, le code de retour ou le résultat.

### 8.3 Des logs structurés

Émettez des logs au format JSON, une ligne par événement, avec l'identifiant de trace injecté automatiquement. C'est ce qui rend le passage du log vers la trace immédiat dans Grafana.

### 8.4 Comprendre l'échantillonnage

La plateforme ne conserve pas toutes les traces. Elle garde la totalité des traces en erreur ou lentes, et seulement une part des traces normales. Deux conséquences pratiques en découlent. Une trace de test banale a peu de chances d'être conservée, il faut donc la marquer en erreur ou la rendre lente pour la retrouver à coup sûr. Et il existe un petit délai avant qu'une trace apparaisse, le temps que la décision d'échantillonnage soit rendue.

### 8.5 Masquer les données sensibles

Les champs sensibles, comme les en-têtes d'autorisation ou les données personnelles, ne doivent jamais atteindre le stockage. Le masquage se fait au collecteur, qui est le point de conformité de la plateforme.

## 9. Enquêter dans Grafana

Le but de la plateforme est de répondre vite à une question d'incident. Voici le trajet type, qui va de la vue d'ensemble à la cause précise.

On part d'un tableau de bord et l'on repère une latence qui grimpe sur une opération. On clique sur un exemplar de la courbe, ce qui ouvre une trace représentative. La trace montre l'étape qui prend du temps, par exemple une écriture en base dans un service donné. Depuis cette étape, on ouvre les logs corrélés, qui partagent le même identifiant de trace, et l'on y lit la cause exacte, par exemple un verrou en base. Un tableau de bord dédié confirme alors le contexte. Le diagnostic se fait ainsi en quelques minutes, sans se connecter aux serveurs.

Quelques gestes utiles. Dans l'exploration, on filtre les traces par nom de service. On passe d'une trace à ses logs par un bouton dédié, et d'un log à sa trace par le lien de corrélation. On veille à régler la fenêtre de temps sur une plage récente, sans quoi une trace récente n'apparaît pas dans la recherche.

## 10. Alerte et objectifs de fiabilité

La détection s'appuie sur des règles évaluées en continu par Prometheus et Grafana. Le routage confie ensuite chaque alerte à la bonne personne, avec gardes et escalades, via l'outil d'astreinte. La règle de bon sens est d'alerter sur ce que vit l'utilisateur, défini par des objectifs de fiabilité, et non sur chaque cause technique. Chaque alerte porte une fiche d'action. Une alerte qui sonne sans action possible se supprime ou se reclasse, afin d'éviter la fatigue d'alerte.

Les objectifs de fiabilité se décrivent en code avec Sloth, qui en déduit les règles et suit le budget d'erreur restant. On alerte alors sur la vitesse de consommation de ce budget, une approche bien plus fine qu'un seuil brut.

## 11. Coût et rétention

Même gratuite, l'observabilité a un coût de stockage. Ce coût se pilote à l'entrée, pas à l'affichage. Trois leviers agissent. Le premier, le plus puissant, est l'échantillonnage des traces, qui garde le signal utile et jette le bruit. Le deuxième est la rétention par niveau, avec des données récentes rapides et des données anciennes sur stockage bon marché. La rétention est le premier facteur de coût. Le troisième est la discipline de cardinalité, déjà décrite, qui évite l'explosion du nombre de séries.

À titre indicatif, une conservation de trente jours pour les métriques et les logs, et de quinze jours pour les traces, offre un bon équilibre. Ces durées s'ajustent selon l'espace disque du serveur.

## 12. Sécurité et durcissement

Les réglages de départ sont volontairement simples et pédagogiques, sans chiffrement ni authentification entre services. C'est acceptable pour un laboratoire ou un réseau strictement privé, jamais pour une exposition réelle. Avant une mise en production, quatre chantiers s'imposent, dans cet ordre.

1. **Réduire l'exposition réseau.** Seuls Grafana, la page de statut et les points d'entrée d'ingestion réellement nécessaires sortent du réseau interne. Tout le reste ne publie aucun port et se joint par le réseau Docker interne.
2. **Chiffrer partout.** Un proxy inverse, par exemple Traefik ou Caddy avec des certificats automatiques, se place devant chaque interface et chaque point d'entrée exposé.
3. **Authentifier et attribuer des rôles.** Grafana reçoit des mots de passe forts, des rôles, et de préférence une authentification unique. Les bases sans authentification propre se protègent par le réseau ou par le proxy, et par l'identifiant de tenant en mode cloisonné.
4. **Gérer les secrets et la conformité.** Les secrets vivent hors de Git, dans un fichier local au minimum, puis dans un gestionnaire de secrets quand l'équipe grandit. Le masquage des champs sensibles se fait au collecteur.

Une question mérite d'être posée avant le premier incident. Que se passe-t-il si le serveur d'observabilité tombe pendant la panne qu'il devait montrer ? La parade principale est une sonde externe indépendante, hébergée ailleurs que sur l'infrastructure surveillée, qui garde un œil sur les applications et sur la plateforme elle-même. Bonne nouvelle, perdre la télémétrie ne veut pas dire perdre le service. Les SDK sont non bloquants et le collecteur amortit les coupures courtes, donc les applications continuent de tourner, on est seulement aveugle un instant.

## 13. Évolutions futures

La plateforme est conçue pour grandir sans réécriture, grâce au principe d'une instrumentation unique et de configurations en code.

1. **Passage à Kubernetes.** Le motif standard place un collecteur agent sur chaque nœud et un collecteur passerelle centralisé qui applique l'échantillonnage avant l'écriture. Les mêmes images servent, seule l'orchestration change.
2. **Cloisonnement dur par projet avec Mimir.** À l'échelle, Mimir apporte la rétention longue et le cloisonnement par tenant pour les métriques, ce qui complète le modèle décrit en section 7.
3. **Astreinte complète.** L'outil d'astreinte gère alors les gardes, les escalades et les notifications par appel, avec la gestion d'incidents et les pages de statut.
4. **Haute disponibilité.** Les bases passent en mode distribué avec plusieurs réplicas, et l'alerte fonctionne en grappe pour éviter tout point unique de défaillance.
5. **Documentation interactive.** Ce guide est écrit en Markdown pour être facilement porté, plus tard, vers un site de documentation navigable, dans l'esprit des sites de documentation que l'on consulte au quotidien.

## 14. Dépannage

| Symptôme | Cause probable | Que faire |
|---|---|---|
| Une trace envoyée n'apparaît pas | Échantillonnage, ou délai de décision | Marquer la trace en erreur ou lente, patienter une vingtaine de secondes, réessayer |
| Le collecteur signale un refus de connexion vers Tempo | Tempo écoute sur une adresse locale au lieu de toutes les interfaces | Forcer l'écoute sur toutes les interfaces dans la configuration de Tempo, puis redémarrer |
| Un montage de fichier échoue sous macOS | Docker n'a pas accès au dossier | Accorder l'accès au disque à Docker, ou déplacer la pile hors d'un dossier protégé |
| Le service de migration d'un composant est arrêté avec un code de succès | Comportement normal d'un travail unique | Aucune action |
| Une source de données ne répond pas | Conteneur pas encore prêt, ou adresse interne erronée | Vérifier l'état des conteneurs et l'adresse interne |
| Un envoi renvoie un succès mais rien n'arrive | Variables vides dans la charge utile | Vérifier que les identifiants et les horodatages sont bien renseignés |

Trois commandes de diagnostic rendent service. La première liste l'état et la santé des conteneurs. La deuxième filtre les journaux du collecteur pour repérer un refus d'export. La troisième interroge directement Tempo par identifiant de trace, ce qui écarte l'interface de visualisation.

## 15. Référence rapide et glossaire

### 15.1 Variables d'environnement principales

| Variable | Rôle |
|---|---|
| `OTEL_SERVICE_NAME` | Nom du service émetteur |
| `OTEL_RESOURCE_ATTRIBUTES` | Attributs communs, dont le projet et l'environnement |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Adresse du collecteur |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Protocole d'envoi, HTTP ou gRPC |
| `OTEL_SDK_DISABLED` | Interrupteur pour démarrer sans la plateforme |

### 15.2 Glossaire

| Terme | Définition |
|---|---|
| OTLP | Le protocole standard d'OpenTelemetry pour transporter la télémétrie |
| Span | Une étape d'une requête. Une trace est le parcours complet, fait de plusieurs spans |
| Exemplar | Un point de métrique qui pointe vers une trace représentative, le lien entre la vue d'ensemble et le détail |
| Cardinalité | Le nombre de combinaisons uniques d'étiquettes, principal facteur de coût des métriques |
| Objectif de fiabilité | Une cible de qualité de service, par exemple un pourcentage de requêtes réussies sur une période |
| Budget d'erreur | La part d'indisponibilité tolérée par l'objectif de fiabilité |
| Échantillonnage sélectif | La décision de conserver une trace après l'avoir vue en entier, pour garder les erreurs et les traces lentes |
| Tenant | L'identifiant qui cloisonne les données d'un projet dans le stockage partagé |
| Expérience réelle | La mesure de ce que vit l'utilisateur dans son navigateur ou son téléphone |

### 15.3 Pour aller plus loin

Le document maître d'architecture explique les choix de fond et le comparatif complet des technologies. Le README de la pile détaille la mise en route et la structure des fichiers de configuration. Ce guide se concentre, lui, sur l'usage et le branchement d'un projet.

# Parcours d'expertise en observabilité et monitoring

Ce parcours a un double objectif : connaître ce projet dans ses moindres détails, et devenir par la même occasion un praticien expert de l'observabilité et du monitoring. Il ordonne la lecture des documents déjà présents dans le dépôt, mais il ne se contente pas de renvoyer vers eux. Pour chaque notion et chaque technologie, il précise le rôle tenu, l'endroit exact où le sujet est traité dans nos documents, les concepts standards à maîtriser, une référence canonique externe reconnue par la profession, et un exercice concret à réaliser sur la pile en marche. La compétence en observabilité ne s'acquiert pas en lisant seulement ; elle s'acquiert en interrogeant un système réel, et vous en avez un.

## Comment suivre ce parcours

Progressez dans l'ordre des étapes. Chacune suppose la précédente. À chaque module, respectez la même discipline : lisez la section indiquée de nos documents, assimilez le concept standard, confrontez le à la référence externe, puis faites l'exercice sur votre propre stack et vérifiez le résultat dans Grafana. Un module n'est acquis que lorsque l'exercice réussit et que vous sauriez l'expliquer à quelqu'un d'autre.

Les documents de référence du dépôt, cités tout au long, sont les suivants : le document maître `Architecture_Observabilite_Universelle-2.md` (le quoi et le pourquoi, avec le code du socle en section 10), le document compagnon `Architecture_CICD_Universelle.md`, le guide d'intégration `docs/Guide_Utilisation_Plateforme_Observabilite.md`, le triptyque de gouvernance `README.md`, `CONTEXT.md`, `MEMORY.md`, les README de composants sous `observability/` et `demo/`, et le bilan `docs/Bilan_Maturite_Conformite.md`.

## Étape 0. Orientation : le projet, son but et ses règles

Avant la technique, comprenez le cadre. Lisez dans l'ordre imposé `README.md`, puis `CONTEXT.md`, puis `MEMORY.md`. Le premier fixe les règles Git et la manière de contribuer, le deuxième donne le contexte durable et les décisions actées, le troisième raconte l'état courant, le backlog et l'historique des sessions. Terminez par le bilan de maturité, qui vous dit franchement où en est le projet, ce qui est solide et ce qui manque.

À la fin de cette étape, vous devez savoir répondre à trois questions : quel problème cette plateforme résout, quelles briques la composent, et à quel stade elle se trouve aujourd'hui.

## Étape 1. Les fondations conceptuelles

C'est le socle intellectuel. Sans lui, les outils ne sont que des boîtes.

**Monitoring et observabilité.** Le monitoring répond à des questions connues d'avance à l'aide de tableaux de bord et de seuils. L'observabilité vise à répondre à des questions que l'on ne s'était pas posées, en explorant les signaux bruts émis par le système. Notre document maître pose cette distinction en introduction et la file rouge de la section 5 la met en scène sur un incident type.

**Les signaux.** Trois signaux fondent l'observabilité. Les métriques sont des séries temporelles numériques agrégées, peu coûteuses, idéales pour les tendances et les alertes. Les logs sont des événements horodatés, riches en contexte, utiles pour comprendre un cas précis. Les traces suivent une requête à travers les services et révèlent où le temps se passe. À ces trois signaux, la plateforme ajoute trois compléments que vous rencontrerez plus loin : les profils de performance, l'expérience réelle des utilisateurs dans le navigateur, et le suivi des erreurs applicatives. Le guide d'intégration décrit ces signaux et la manière dont un projet les émet.

**Les méthodes RED et USE.** Ce sont les deux grilles de lecture universelles. La méthode RED observe un service par son débit, son taux d'erreur et sa durée, autrement dit du point de vue de l'utilisateur. La méthode USE observe une ressource par son utilisation, sa saturation et ses erreurs, autrement dit du point de vue de la machine. La section 5 du document maître construit l'écran RED, et le tableau de bord Node Exporter illustre l'approche USE.

**SLI, SLO et budget d'erreur.** Un indicateur de niveau de service mesure la qualité vécue, par exemple la proportion de requêtes servies correctement. Un objectif de niveau de service fixe une cible sur cet indicateur, par exemple 99,9 pour cent sur trente jours. Le budget d'erreur est la part d'échecs tolérée avant de rater l'objectif, et le rythme auquel on le consomme, le burn rate, déclenche des alertes proportionnées. La section 10.6 du document maître et le lot d'alerting du dépôt mettent cela en œuvre concrètement.

Référence canonique. Le livre Site Reliability Engineering de Google et son cahier d'exercices, disponibles librement sur sre.google, pour les SLO et le budget d'erreur. Les écrits d'origine de Tom Wilkie pour la méthode RED et de Brendan Gregg pour la méthode USE.

Exercice. Sans regarder le code, écrivez sur papier les trois indicateurs RED de `units-service` et les trois indicateurs USE de la machine hôte. Vous les vérifierez à l'étape 3.

## Étape 2. La chaîne de collecte : OpenTelemetry et le Collector

Tout part de là. Comprendre la collecte, c'est comprendre pourquoi les données arrivent propres et corrélées.

**OpenTelemetry.** C'est le standard ouvert d'instrumentation, indépendant du fournisseur. Il définit des SDK par langage, une instrumentation automatique qui capte les bibliothèques courantes sans toucher au code métier, un protocole de transport unique appelé OTLP, des conventions sémantiques qui nomment les attributs de façon uniforme, et un mécanisme de propagation de contexte qui transmet l'identifiant de trace d'un service à l'autre au format W3C. La section 10.1 du document maître et le README de `units-service` montrent l'instrumentation Python sans une ligne d'instrumentation dans le code applicatif. La section 10.2 et le README de `mir-webapp` montrent la propagation du navigateur jusqu'au backend.

**Le Collector.** C'est le pivot de l'architecture. Aucune application ne parle directement aux backends ; toutes envoient à un Collector central qui reçoit, transforme et route. Sa configuration s'articule en récepteurs, processeurs, exportateurs et connecteurs. Deux points le rendent remarquable dans ce projet. D'abord l'échantillonnage par la queue, qui décide de garder ou non une trace une fois qu'elle est complète, ce qui permet de conserver toutes les erreurs et toutes les traces lentes tout en jetant une partie du trafic normal. Ensuite les connecteurs qui dérivent des métriques à partir des traces avant cet échantillonnage, si bien que les taux d'erreur et les latences restent exacts même quand des traces sont ensuite écartées. La section 10.3 du document maître détaille ce pipeline, et le fichier `observability/otel-collector-config.yaml` en est la mise en œuvre.

Référence canonique. La documentation officielle sur opentelemetry.io, en particulier les pages sur le Collector, les conventions sémantiques et la propagation de contexte.

Exercice. Ouvrez `otel-collector-config.yaml` et suivez le chemin d'une trace : quel récepteur la reçoit, quels processeurs la traitent, par quel connecteur naissent les métriques dérivées, vers quel exportateur elle part. Puis expliquez en une phrase pourquoi les métriques dérivées sont calculées avant l'échantillonnage et pas après.

## Étape 3. Les backends, technologie par technologie

C'est le cœur technique. Traitez chaque brique de la même façon : son rôle, sa place dans la chaîne, où l'étudier, ce qu'il faut maîtriser, une référence, un exercice.

### Prometheus et le langage PromQL

Rôle. Base de données de séries temporelles et moteur d'alerte pour les métriques. Il collecte en tirant les cibles, reçoit aussi les métriques du Collector en remote write, stocke, et évalue les règles.

À maîtriser. Le modèle de données, une métrique plus des étiquettes ; les quatre types, compteur, jauge, histogramme, résumé ; le langage PromQL, avec les sélecteurs, `rate` sur les compteurs, l'agrégation par étiquette, et `histogram_quantile` pour les centiles ; les exemplars qui relient un point de métrique à une trace ; les règles d'enregistrement et d'alerte. Nos règles RED vivent dans `observability/prometheus/rules/red.yml`, la collecte dans `observability/prometheus/prometheus.yml`.

Référence. La documentation prometheus.io, sections sur PromQL et sur les histogrammes.

Exercice. Dans Grafana, écrivez la requête du taux d'erreur de `units-service` à partir des spanmetrics, puis celle du 99e centile de latence. Comparez avec vos indicateurs RED de l'étape 1.

### Loki et le langage LogQL

Rôle. Agrégation de logs, économe car il n'indexe que des étiquettes et pas le contenu. Notre Collector et Alloy y envoient les logs.

À maîtriser. La différence entre une étiquette, indexée et à faible cardinalité, et le contenu du log ; le langage LogQL, sélection par étiquettes puis filtrage ; le fait qu'un log applicatif porte l'identifiant de trace, ce qui permet le saut vers la trace. Le README de `units-service` montre le log JSON structuré avec l'identifiant de trace.

Référence. La documentation grafana.com sur Loki et LogQL.

Exercice. Écrivez une requête LogQL qui isole les logs de `units-service`, puis ouvrez un log et sautez vers sa trace dans Tempo.

### Tempo et le langage TraceQL

Rôle. Stockage et recherche de traces. Il reçoit du Collector.

À maîtriser. La notion de trace et de span, la relation parent enfant, les attributs de span où l'on met les identifiants à forte cardinalité ; le langage TraceQL pour rechercher par service, par durée, par attribut ; le fait que l'échantillonnage par la queue explique qu'une recherche par identifiant au hasard renvoie souvent rien, d'où la recherche par service. Le journal de `MEMORY.md` documente précisément ce comportement.

Référence. La documentation grafana.com sur Tempo et TraceQL.

Exercice. Recherchez en TraceQL les traces de `units-service` de durée supérieure à un seuil, ouvrez en une, et retrouvez le span où le temps se concentre.

### Grafana

Rôle. La fenêtre unique. Il interroge toutes les sources et surtout il les corrèle.

À maîtriser. Les sources de données et leur provisionnement par fichier ; la construction d'un tableau de bord ; et surtout les liens de corrélation configurés dans `observability/grafana/provisioning/datasources/datasources.yaml`, qui font passer d'une métrique à une trace par exemplar, d'une trace à ses logs, d'un log à sa trace, d'une trace à un profil.

Référence. La documentation grafana.com, sections exploration et corrélation.

Exercice. Rechargez le tableau de bord Node Exporter, repérez les exemplars sur une courbe de latence, cliquez en un pour atterrir sur une trace.

### node-exporter

Rôle. Expose les métriques de la machine hôte, matière première de la méthode USE.

À maîtriser. Les familles de métriques processeur, mémoire, disque, réseau ; leur lecture en termes d'utilisation et de saturation.

Référence. Le dépôt et la documentation de node_exporter sur prometheus.io.

Exercice. Construisez trois panneaux, utilisation processeur, mémoire disponible, saturation disque, et reliez les à vos indicateurs USE de l'étape 1.

### Pyroscope

Rôle. Profilage continu. Il montre, fonction par fonction, où le processeur et la mémoire sont consommés, sous forme de graphe de flammes, et se relie aux traces.

À maîtriser. La lecture d'un graphe de flammes ; l'idée du lien trace vers profil, qui répond non seulement à quelle requête est lente mais à quelle ligne de code la ralentit. C'est le lot de backlog dédié au SDK Pyroscope.

Référence. La documentation grafana.com sur Pyroscope.

Exercice. Une fois le SDK branché, ouvrez un graphe de flammes et identifiez la fonction la plus coûteuse.

### GlitchTip

Rôle. Suivi des erreurs applicatives, compatible avec le protocole Sentry. Il regroupe les exceptions, garde la trace d'appel et le contexte.

À maîtriser. La différence entre une erreur suivie ici et un log ; le regroupement des occurrences d'une même erreur ; le lien avec la version déployée.

Référence. La documentation glitchtip.com et les SDK Sentry.

Exercice. Depuis `mir-webapp`, déclenchez une erreur et retrouvez la dans GlitchTip avec sa trace d'appel.

### Grafana Alloy et Grafana Faro

Rôle. Alloy est l'agent qui collecte les logs des conteneurs et qui héberge le récepteur des données du navigateur. Faro est le SDK web qui mesure l'expérience réelle des utilisateurs, les Web Vitals, les erreurs de page et les traces côté navigateur, avec propagation vers le backend.

À maîtriser. Le rôle d'agent d'Alloy et son fichier de configuration `observability/alloy-config.alloy` ; l'étiquette qui rend les événements du navigateur filtrables dans Loki ; la propagation de trace du navigateur jusqu'à Django, qui fait de deux traces une seule. La section 10.2 et le README de `mir-webapp` détaillent tout cela.

Référence. La documentation grafana.com sur Alloy et sur Faro.

Exercice. Filtrez les événements du navigateur dans Loki, puis ouvrez une trace qui commence dans le navigateur et se poursuit dans le backend.

## Étape 4. La corrélation, signature d'une plateforme mûre

Une plateforme se juge à sa capacité à passer d'un signal à l'autre sans friction. Étudiez la section 10.5 du document maître et la section correspondante du guide d'intégration. Quatre ponts existent : l'exemplar relie une métrique à une trace, l'identifiant de trace dans le log relie le log à la trace et inversement, le lien trace vers profil relie une trace à son profil de performance, et les métriques dérivées des spans font le lien entre le monde des traces et celui des métriques. Maîtriser la corrélation, c'est savoir partir d'une alerte sur un symptôme et descendre jusqu'à la ligne de code fautive en quelques clics.

Exercice complet. Provoquez une dégradation, partez de l'alerte, ouvrez la métrique, sautez à une trace par exemplar, lisez les logs du span fautif, puis, quand le profilage sera en place, descendez jusqu'au profil. Chronométrez vous. Un expert fait ce trajet en moins d'une minute.

## Étape 5. Alerting, objectifs de service et exploitation

**Alertmanager.** Reçoit les alertes de Prometheus et décide quoi en faire. À maîtriser : le routage par étiquettes, le regroupement pour éviter le bruit, l'inhibition qui tait une alerte mineure quand une majeure la couvre, et les récepteurs, dont Slack dans notre cas. La configuration est dans `observability/alertmanager/`.

**Sloth.** Traduit un objectif de service décrit simplement en un jeu complet de règles Prometheus, dont les alertes multi burn rate à double fenêtre qui évitent les fausses alertes. Le fichier `observability/slo/units-service.yml` en est l'exemple, et le journal explique pourquoi l'alerte de budget se déclenche vite en cas d'erreurs massives et lentement en cas de dégradation légère.

**Blackbox et Uptime Kuma.** Deux vues de l'extérieur. Blackbox sonde les endpoints en HTTP depuis l'intérieur du réseau et alimente Prometheus. Uptime Kuma sonde depuis une machine indépendante et reste debout quand le serveur surveillé tombe. Les fichiers de sondes et le README d'Uptime Kuma expliquent la complémentarité.

**k6.** Génère un trafic synthétique pour valider les seuils de latence et d'erreur, en recette comme en intégration continue. Le script `observability/k6/smoke.js` en est la base.

Référence. Le cahier d'exercices SRE de Google pour les alertes multi fenêtres multi burn rate, la documentation prometheus.io pour Alertmanager, le dépôt de Sloth, la documentation k6.io.

Exercice. Reproduisez l'alerte du lot d'alerting, faites varier un seuil de burn rate et observez l'effet sur le délai de déclenchement, puis ajoutez une cible de sonde et vérifiez qu'une coupure lève bien une alerte jusqu'à Slack.

## Étape 6. Mise à l'échelle et production

Vous saurez le projet de bout en bout quand vous saurez aussi comment il grandit et ce qui lui manque pour la production. Étudiez la section 7 du document maître : le mono serveur et ses limites en 7.1, le passage à Kubernetes et à Mimir pour la rétention longue et le multi locataire en 7.2, la rétention et la discipline de cardinalité en 7.3, le durcissement avant exposition en 7.4, la résilience et la question du surveillant du surveillant en 7.5. Terminez par le bilan de maturité, qui liste les écarts restants et l'ordre pour les combler. Le plan de correction en cours dans le dépôt suit précisément cette liste.

## Jalons d'expertise

Vous pouvez vous considérer expert de ce projet et solide en observabilité lorsque, sans aide, vous savez faire ce qui suit. Expliquer la chaîne complète, de l'émission par l'application jusqu'à l'affichage corrélé dans Grafana, en nommant chaque brique et son rôle. Écrire à la volée une requête PromQL de taux d'erreur et de centile de latence, une requête LogQL corrélée à une trace, une requête TraceQL par service et par durée. Justifier pourquoi les métriques dérivées sont calculées avant l'échantillonnage. Concevoir un objectif de service, en déduire un budget d'erreur, et régler une alerte multi burn rate qui ne réveille personne pour rien. Distinguer une sonde interne d'une sonde externe et dire pourquoi la seconde doit vivre ailleurs. Faire le trajet complet d'une alerte jusqu'à la cause en moins d'une minute. Enfin, dire ce qui manque à la plateforme pour être exposable et dans quel ordre le corriger.

## Ressources canoniques externes

Pour aller au delà du projet et asseoir une expertise générale, appuyez vous sur les sources reconnues de la profession. Le livre Site Reliability Engineering et son cahier d'exercices, sur sre.google, pour les SLO, le budget d'erreur et l'alerting. Les documentations officielles opentelemetry.io, prometheus.io et grafana.com, qui font autorité sur la collecte, les métriques et la visualisation. Les écrits fondateurs sur les méthodes RED et USE. L'ouvrage Observability Engineering, chez O'Reilly, pour la vision d'ensemble et la culture de l'observabilité. La lecture régulière des notes de version de ces outils, car le domaine évolue vite.

## Laboratoires pratiques guidés

Rien ne remplace la manipulation. Voici trois laboratoires à faire sur votre pile, du plus simple au plus complet.

Premier laboratoire, le trajet d'une requête. Démarrez la démo, envoyez du trafic sur `units-service`, puis retrouvez la même requête sous ses trois formes : la métrique dans Prometheus, le log dans Loki, la trace dans Tempo. Prouvez que les trois parlent bien de la même requête grâce à l'identifiant de trace.

Deuxième laboratoire, du symptôme à la cause. Provoquez des erreurs, laissez l'alerte se déclencher, et descendez de l'alerte à la trace fautive puis au log, en notant chaque pont de corrélation emprunté.

Troisième laboratoire, la vue de l'extérieur. Coupez un service, observez la sonde Blackbox passer au rouge et l'alerte remonter jusqu'à Slack, puis raisonnez sur ce qu'une sonde hébergée hors infrastructure aurait vu de plus si c'était le serveur entier qui était tombé.

Quand ces trois laboratoires vous sembleront évidents, vous ne connaîtrez plus seulement le projet, vous penserez en praticien de l'observabilité.

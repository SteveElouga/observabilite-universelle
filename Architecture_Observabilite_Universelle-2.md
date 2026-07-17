# Architecture d'une stack d'observabilité universelle

### Document d'architecture — vue macro & micro, écrans clés, et stack finale 100 % gratuite

> **Portée** : ce document décrit une stack d'observabilité *universelle*, applicable à n'importe quel logiciel — backend, web ou mobile — quel que soit le langage ou l'hébergement. Il donne l'architecture cible, les signaux à collecter, les écrans (dashboards) à construire et *pourquoi*, un comparatif technologique pour chaque brique (le meilleur, le moins cher, le plus cher, le plus utilisé — avec les raisons), et se termine par une **stack finale entièrement gratuite et auto-hébergeable**.
>
> **Note sur les prix** : les tarifs cités sont des **prix catalogue indicatifs de 2026** et servent uniquement de repère de comparaison. Ils évoluent régulièrement ; vérifiez toujours sur le site de l'éditeur avant toute décision.
>
> **Révision — 17 juillet 2026** : ① l'astreinte passe de Grafana OnCall (OSS **archivé le 24/03/2026**) à **OneUptime** (§4.11) ; ② les métriques de la carte des services sont désormais générées **au Collector, avant échantillonnage** (§10.3) ; ③ **Pyroscope** rejoint le compose mono-serveur (§10.4) ; ④ nouvelles sous-sections **durcissement pré-production (§7.4)** et **« qui surveille le surveillant ? » (§7.5)** ; ⑤ les chiffres d'adoption sont attribués à leurs sources (§9.4).

---

## Sommaire

1. [Pourquoi l'observabilité : monitoring ≠ observabilité](#1)
2. [Les signaux : les piliers de l'observabilité](#2)
3. [L'architecture globale : le schéma directeur](#3)
4. [Comparatif technologique, couche par couche](#4)
   - 4.1 Instrumentation — OpenTelemetry
   - 4.2 Collecte & pipeline — le Collector
   - 4.3 Métriques
   - 4.4 Logs
   - 4.5 Traces distribuées
   - 4.6 Suivi d'erreurs & crash
   - 4.7 RUM (web & mobile)
   - 4.8 Uptime & monitoring synthétique
   - 4.9 Profiling continu
   - 4.10 Visualisation
   - 4.11 Alerte & astreinte (on-call)
   - 4.12 SLO / SLI
5. [Les écrans qui comptent (et pourquoi)](#5)
6. [La stack finale 100 % gratuite](#6)
7. [Déploiement, topologies & maîtrise des coûts](#7)
8. [Modèle de maturité : par où commencer](#8)
9. [Annexes : checklist, anti-patterns, glossaire, sources](#9)
10. [Mise en œuvre : le code complet de la stack gratuite](#10)

---

<a name="1"></a>
## 1. Pourquoi l'observabilité : monitoring ≠ observabilité

Le **monitoring** répond à une question que vous avez anticipée : « le CPU dépasse-t-il 80 % ? », « le site répond-il ? ». Vous savez à l'avance quoi surveiller. C'est nécessaire, mais insuffisant : en production, les pannes viennent presque toujours de ce que vous **n'aviez pas prévu**.

L'**observabilité** est la capacité à répondre à des questions que vous ne vous étiez *pas* posées à l'avance, en interrogeant les données émises par le système — sans avoir à redéployer du code pour ajouter une sonde. On dit qu'un système est observable quand, à partir de ses sorties (métriques, logs, traces), on peut reconstituer son état interne.

```mermaid
flowchart LR
  subgraph MON["MONITORING (questions connues)"]
    M1["Le service est-il UP ?"]
    M2["CPU > 80 % ?"]
    M3["Erreur 5xx ?"]
  end
  subgraph OBS["OBSERVABILITÉ (questions inconnues)"]
    O1["POURQUOI cette requête<br/>est-elle lente<br/>seulement pour<br/>les clients EU en 4G ?"]
  end
  MON -->|"ne suffit pas"| OBS
```

### Vue MACRO vs vue MICRO

Tout l'enjeu d'une bonne stack est de couvrir deux échelles et de permettre de **naviguer instantanément de l'une à l'autre**.

| | Vue **MACRO** | Vue **MICRO** |
|---|---|---|
| **Question** | « Est-ce que ça va, globalement ? » | « Que s'est-il passé exactement, pour *cette* requête ? » |
| **Public** | Direction, astreinte, NOC, product | Développeur en train de déboguer |
| **Granularité** | Agrégats : taux d'erreur, latence p95, disponibilité, budget d'erreur | Une trace, une ligne de log, un profil CPU |
| **Signaux dominants** | Métriques, SLO | Traces, logs, profils, erreurs |
| **Horizon** | Tendances (jours, semaines) | Instant précis (la seconde de l'incident) |

Le signe d'une stack mature : depuis un pic de latence sur un graphique **macro**, on clique et on arrive en **deux sauts** sur la trace exacte puis sur la ligne de log fautive. C'est le fil rouge de tout ce document.

### Ce que ça rapporte

Deux métriques justifient l'investissement (les enquêtes du secteur situent le budget observabilité autour de ~15 à 20 % du budget d'infrastructure dans les organisations matures — voir §9.4) :

- **MTTD** (*Mean Time To Detect*) — temps moyen avant de *détecter* un incident.
- **MTTR** (*Mean Time To Recover/Resolve*) — temps moyen avant de le *résoudre*.

Une stack d'observabilité fait chuter ces deux chiffres : on détecte avant les clients (via SLO et alertes), et on répond vite (via corrélation métrique → trace → log). Chaque minute de panne évitée a un coût direct.

---

<a name="2"></a>
## 2. Les signaux : les piliers de l'observabilité

Historiquement on parle des **trois piliers** ; en pratique, une stack complète en 2026 en manipule six. On les résume par l'acronyme **MELT** (Metrics, Events, Logs, Traces), enrichi de **Profils** et **RUM**.

```mermaid
flowchart TB
  subgraph SIGNALS["Les 6 signaux"]
    A["MÉTRIQUES<br/>séries temporelles chiffrées<br/>→ vue MACRO, tendances, alertes"]
    B["LOGS<br/>événements textuels horodatés<br/>→ vue MICRO, contexte détaillé"]
    C["TRACES<br/>parcours d'une requête entre services<br/>→ le pont macro ↔ micro"]
    D["ÉVÉNEMENTS<br/>déploiements, changements, incidents<br/>→ mise en contexte"]
    E["PROFILS<br/>consommation CPU/mémoire au code<br/>→ optimisation fine"]
    F["RUM & CRASH<br/>expérience réelle utilisateur<br/>→ vue côté client web/mobile"]
  end
```

**Métriques.** Des nombres agrégés dans le temps : requêtes/seconde, latence p99, taux d'erreur, mémoire utilisée. Peu coûteuses à stocker, idéales pour les tableaux de bord temps réel et les alertes. **Faiblesse** : elles disent *qu'*un problème existe, pas *pourquoi*. Attention à la **cardinalité** (voir §7) : une métrique déclinée par `user_id` explose le stockage.

**Logs.** Des lignes horodatées décrivant un événement précis. Riches en contexte, indispensables au débogage. **Faiblesse** : volumineux et coûteux. La bonne pratique moderne est le **log structuré** (JSON) plutôt que le texte libre.

**Traces distribuées.** Le signal le plus important dans une architecture répartie (microservices, serverless). Une trace suit une requête *de bout en bout* : chaque étape est un **span** (portant `trace_id`, `span_id`, durée, service). C'est **le pont** entre macro et micro — on part d'une latence agrégée et on descend jusqu'à la sous-opération lente.

**Événements.** Déploiements, changements de config, ouvertures d'incident. Superposés aux courbes, ils répondent à « qu'est-ce qui a changé juste avant que ça casse ? » — souvent, un déploiement.

**Profils (continuous profiling).** Échantillonnage de la pile d'appels : quelle *fonction* consomme le CPU/la mémoire. Complète la trace (qui pointe le *service* lent) en désignant la *ligne de code* coûteuse.

**RUM & crash reporting.** *Real User Monitoring* : ce que vit réellement l'utilisateur dans son navigateur ou son app mobile — temps de chargement, Core Web Vitals, erreurs JS, plantages (crashes) mobiles, rage-clicks. C'est la seule vue « côté client » ; tout le reste est « côté serveur ».

### La corrélation : le vrai super-pouvoir

Collecter les six signaux ne suffit pas : leur **valeur vient de leur mise en relation**. On y parvient en propageant des identifiants communs — le `trace_id` injecté dans les logs, les **exemplars** attachés aux métriques (un point de métrique qui pointe vers une trace représentative).

```mermaid
flowchart LR
  M["1 · MÉTRIQUE<br/>latence p99 en hausse"] -->|"exemplar → trace_id"| T["2 · TRACE<br/>la requête lente est isolée"]
  T -->|"span_id"| L["3 · LOGS<br/>les lignes exactes de l'erreur"]
  T -->|"même fenêtre"| P["4 · PROFIL<br/>la fonction qui brûle le CPU"]
  L --> E["5 · ERREUR<br/>groupée & priorisée (Sentry)"]
```

**Règle d'or d'architecture** : choisissez des outils qui partagent ces identifiants et se laissent naviguer les uns vers les autres. C'est précisément la promesse de l'écosystème **OpenTelemetry + Grafana** retenu plus bas.
---

<a name="3"></a>
## 3. L'architecture globale : le schéma directeur

Toute stack d'observabilité, quelle que soit la techno, suit le même **pipeline en 5 couches**. Retenez ce schéma : c'est la colonne vertébrale du reste du document.

```mermaid
flowchart LR
  subgraph SRC["1 · SOURCES instrumentées"]
    direction TB
    A1["Backend<br/>(SDK OpenTelemetry)"]
    A2["Front web<br/>(Faro / OTel-JS)"]
    A3["App mobile<br/>(SDK OTel / crash)"]
    A4["Infra · OS · Kubernetes<br/>(exporters)"]
    A5["Bases de données · files<br/>(exporters)"]
  end

  subgraph COL["2 · COLLECTE & pipeline"]
    C1["OpenTelemetry Collector<br/>reçoit · filtre · échantillonne<br/>enrichit · route"]
  end

  subgraph STO["3 · STOCKAGE par signal"]
    direction TB
    S1["Métriques<br/>Prometheus / Mimir"]
    S2["Logs<br/>Loki"]
    S3["Traces<br/>Tempo"]
    S4["Profils<br/>Pyroscope"]
    S5["Erreurs & crash<br/>Sentry / GlitchTip"]
  end

  subgraph VIS["4 · VISUALISATION"]
    V1["Grafana<br/>dashboards · exploration<br/>corrélation entre signaux"]
  end

  subgraph ACT["5 · ALERTE & RÉPONSE"]
    direction TB
    AL1["Règles d'alerte<br/>Alertmanager / Grafana"]
    AL2["Astreinte<br/>OneUptime"]
    AL3["Canaux<br/>Slack · e-mail · téléphone"]
  end

  A1 --> C1
  A2 --> C1
  A3 --> C1
  A4 --> S1
  A5 --> S1
  C1 --> S1
  C1 --> S2
  C1 --> S3
  C1 --> S4
  A1 -.->|SDK direct| S5
  A2 -.-> S5
  A3 -.-> S5
  S1 --> V1
  S2 --> V1
  S3 --> V1
  S4 --> V1
  S5 --> V1
  S1 --> AL1
  V1 --> AL1
  AL1 --> AL2
  AL2 --> AL3
```

### Rôle de chaque couche

**Couche 1 — Instrumentation (les sources).** Le code et l'infrastructure doivent *émettre* les signaux. Deux modes : l'**auto-instrumentation** (un agent injecte des sondes sans toucher au code — parfait pour démarrer) et l'**instrumentation manuelle** (le développeur ajoute des spans et métriques métier — indispensable pour le sens business). Côté infra, des **exporters** exposent l'état des machines, conteneurs et bases. *La règle universelle : instrumenter avec **OpenTelemetry**, pour ne jamais dépendre d'un fournisseur (voir §4.1).*

**Couche 2 — Collecte & pipeline.** Un **collecteur** central se place entre les applications et le stockage. Il reçoit la télémétrie (protocole **OTLP**), la **filtre** (jette le bruit), l'**échantillonne** (garde un sous-ensemble représentatif des traces pour maîtriser le volume), l'**enrichit** (ajoute des attributs : environnement, région, version) et la **route** vers un ou plusieurs backends. C'est aussi le point qui **découple** vos apps du backend : changer de stockage = changer une config du collecteur, pas le code.

**Couche 3 — Stockage.** Chaque signal a une base spécialisée : une **base de séries temporelles** (TSDB) pour les métriques, un **magasin de logs** indexé, un **magasin de traces** sur stockage objet, etc. C'est ici que se joue l'essentiel du **coût** : volume ingéré × durée de rétention.

**Couche 4 — Visualisation.** Une **interface unique** interroge tous les backends, affiche les tableaux de bord et — surtout — permet de **naviguer d'un signal à l'autre** (d'un pic de métrique vers la trace, puis les logs). Un point d'entrée unique évite de jongler entre dix onglets pendant un incident.

**Couche 5 — Alerte & réponse.** Des règles évaluent en continu les données et déclenchent des **alertes** ; un système d'**astreinte (on-call)** route la bonne alerte vers la bonne personne, gère les escalades et les gardes, et permet la **réponse à incident**.

### Principes d'architecture transverses

1. **Vendor-neutralité par défaut.** On instrumente une seule fois avec OpenTelemetry ; on reste libre de changer de backend. C'est *le* choix stratégique qui protège contre le verrouillage et l'inflation tarifaire.
2. **Le collecteur au centre.** Ne jamais brancher les apps en direct sur le stockage propriétaire. Toujours passer par un collecteur : c'est votre point de contrôle du volume, du coût et de la conformité (masquage des données sensibles).
3. **Corrélation par identifiants partagés.** `trace_id` dans les logs, exemplars sur les métriques : sans cela, on a trois silos, pas une stack.
4. **Le coût est piloté à l'ingestion, pas à l'affichage.** On maîtrise la facture (ou l'usage disque) en amont : échantillonnage, filtrage, rétention par niveau (§7).
5. **Convention de nommage & labels disciplinés.** Des labels cohérents (`service`, `env`, `version`, `region`) rendent chaque dashboard réutilisable et évitent l'explosion de cardinalité.
---

<a name="4"></a>
## 4. Comparatif technologique, couche par couche

Pour chaque brique : son **rôle**, la **vue** qu'elle apporte, un **comparatif** (le plus utilisé / le meilleur / le moins cher / le plus cher — avec les raisons), puis **le choix gratuit** retenu pour la stack finale.

> **Légende des colonnes** — *Le plus utilisé* : ce que la majorité des équipes déploie (adoption). *Le meilleur* : le plus abouti fonctionnellement, budget non limité. *Le moins cher* : le meilleur rapport coût/valeur, gratuit inclus. *Le plus cher* : le haut de gamme premium (repère de coût maximal).

---

### 4.1 Instrumentation — le standard : OpenTelemetry

**Rôle.** Faire *émettre* les signaux par le code : métriques, logs, traces. C'est la fondation ; tout le reste en dépend.

**Le débat est clos en 2026 : c'est OpenTelemetry (OTel).** C'est un standard ouvert, neutre, gouverné par la CNCF — devenu, selon les mesures de vélocité de la CNCF elle-même, le **2ᵉ plus gros projet de la fondation après Kubernetes**. D'après les enquêtes CNCF/OpenTelemetry (§9.4), environ la moitié à deux tiers des organisations l'utilisent ou le déploient, avec la plus forte dynamique de croissance du secteur. **Tous** les grands éditeurs (Datadog, New Relic, Grafana, Dynatrace, Splunk, Honeycomb, les hyperscalers) acceptent nativement son protocole **OTLP**.

**Pourquoi c'est non négociable.** Vous instrumentez votre code **une seule fois** avec des API qui ne mentionnent aucun fournisseur. Changer de backend = changer une config, pas réécrire l'application. C'est *la* protection anti-verrouillage et anti-inflation tarifaire. Un agent propriétaire (Datadog, New Relic…) fait l'inverse : il vous lie à vie.

| Option | Verdict | Pourquoi |
|---|---|---|
| **OpenTelemetry** *(le plus utilisé + le meilleur choix)* | **Standard retenu** | Neutre, universel, gratuit, supporté partout. Auto-instrumentation pour la plupart des langages (Java, .NET, Node, Python, Go…) + API manuelle. Un seul apprentissage, portable à vie. |
| Agents propriétaires (Datadog Agent, New Relic Agent) | À éviter comme socle | Souvent plus « clé en main » au départ, mais **verrouillage total** : migrer implique de tout réinstrumenter. Ils supportent désormais OTLP — utilisez OTel *à travers* eux si besoin. |
| SDK maison / logs bruts uniquement | Insuffisant | Pas de traces ni de corrélation ; dette technique garantie. |

**Le choix gratuit :** **OpenTelemetry SDK + auto-instrumentation** (gratuit, open source). Pour le web, **Grafana Faro** (SDK JS, gratuit) ; pour le mobile, les SDK OTel/Sentry (gratuits).

---

### 4.2 Collecte & pipeline — le Collector

**Rôle.** Recevoir la télémétrie des apps, la **traiter** (filtrer, échantillonner, enrichir, masquer les données sensibles) et la **router** vers les backends. C'est le point de contrôle du **volume** et donc du **coût**.

**Vue apportée.** Indirecte mais critique : c'est ici qu'on décide *quoi* garder. Un bon pipeline = des dashboards nets et une facture (ou un disque) maîtrisée.

| Option | Positionnement | Pourquoi / quand |
|---|---|---|
| **OpenTelemetry Collector** *(le plus utilisé + le meilleur)* | **Retenu** | Neutre, gratuit, une multitude de *receivers/processors/exporters*. Gère l'**échantillonnage tail-based** (garder les traces en erreur ou lentes), le batching, la transformation. Peut router vers plusieurs backends à la fois (utile en migration). |
| **Grafana Alloy** | Excellent en stack Grafana | Distribution d'agent (compatible OTel) de Grafana, gratuite ; pratique si tout le backend est LGTM. |
| **Vector** (Datadog, OSS) | Très performant pour les logs | Gratuit, ultra-rapide, langage de transformation (VRL) puissant, surtout orienté logs/métriques. |
| **Fluent Bit / Fluentd** | Standard historique des logs | Gratuits, légers, omniprésents sur Kubernetes pour la collecte de logs. |
| Agents propriétaires | Repère « cher » | Inclus dans les licences Datadog/New Relic ; renforcent le verrouillage. |

**Le choix gratuit :** **OpenTelemetry Collector** (+ **Alloy** ou **Fluent Bit** pour la collecte de logs sur les nœuds si besoin). 100 % gratuit et open source.

---

### 4.3 Métriques — la couche MACRO

**Rôle.** Stocker et interroger des **séries temporelles** : req/s, latences (p50/p95/p99), taux d'erreur, saturation ressources. C'est le socle des dashboards temps réel et des alertes.

**Vue apportée.** **Macro** par excellence : tendances, agrégats, seuils. Le premier écran qu'on regarde.

Le standard de fait est **Prometheus** : dans les enquêtes CNCF sur l'observabilité (§9.4), environ trois quarts des organisations investissent dessus (~77 %) et deux tiers l'exploitent en production (~67 %). Son langage **PromQL** est la lingua franca des métriques. Autour, plusieurs moteurs répondent au passage à l'échelle (Prometheus seul ne fait pas de stockage longue durée distribué nativement).

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Prometheus** *(le plus utilisé)* | **Retenu (base)** | **Gratuit** (OSS) | Standard incontesté sur Kubernetes/cloud-native. Modèle *pull*, PromQL, immense écosystème d'exporters. Pour la longue rétention, on l'associe à Mimir/Thanos. |
| **Grafana Mimir** ou **Thanos** / **Cortex** | Le plus abouti à grande échelle | **Gratuit** (OSS) | Rétention longue durée, multi-tenant, haute dispo, stockage objet bon marché (S3/GCS). **Mimir** = extension naturelle de Prometheus, retenu pour la stack finale. |
| **VictoriaMetrics** | Le moins cher à l'échelle | **Gratuit** (OSS) ; cloud payant | Très économe en RAM/disque, compatible PromQL, excellent quand les métriques sont votre signal dominant et que Prometheus sature. |
| **Datadog Metrics** | **Le plus cher** (premium) | ~15 $/hôte/mois + surcoût *custom metrics* (au-delà de 100/hôte) | Le plus « clé en main » et intégré, mais coût qui grimpe vite avec la **cardinalité** ; factures souvent 2–3× l'estimation. |
| New Relic (modèle ingestion) | Alternative premium | 100 Go/mois gratuits, puis ~0,30–0,40 $/Go | Facturé au volume ingéré, pas à l'hôte ; simple mais imprévisible en cas de pic. |

**Le choix gratuit :** **Prometheus** (collecte + PromQL) **+ Grafana Mimir** pour la rétention longue et l'échelle. Exporters gratuits : **Node Exporter** (OS), **cAdvisor** (conteneurs), **kube-state-metrics** (Kubernetes), plus les exporters par techno (Postgres, Redis, Nginx…).

---

### 4.4 Logs — la couche MICRO textuelle

**Rôle.** Centraliser tous les logs applicatifs et système, les indexer et permettre la recherche. Le premier réflexe de débogage.

**Vue apportée.** **Micro** : le détail exact d'un événement, le message d'erreur complet, la stack trace.

Deux philosophies s'affrontent : **indexation par labels** (Loki — on n'indexe que des métadonnées, le corps reste compressé sur stockage objet → très bon marché) vs **indexation plein-texte** (Elasticsearch/OpenSearch — recherche full-text puissante mais coûteuse en stockage et en RAM).

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Grafana Loki** *(retenu)* | Le moins cher / cloud-native | **Gratuit** (OSS) | Inspiré de Prometheus : indexe des *labels*, stocke le reste sur objet (S3/GCS). Coût de stockage très bas, intégration Grafana native, langage **LogQL** proche de PromQL. Idéal pour corréler logs ↔ métriques ↔ traces. |
| **OpenSearch** (fork libre d'Elasticsearch) / **ELK** | Le meilleur pour la recherche | **Gratuit** (OSS) ; lourd à opérer | Recherche plein-texte et analytique très puissantes (Kibana). Plus gourmand en ressources ; pertinent si l'analyse de logs est centrale. |
| **OpenObserve** | Le moins cher à l'échelle | **Gratuit** (OSS) | Natif stockage objet, requêtes **SQL**, TCO très bas sur gros volumes ; alternative montante. |
| **Datadog Logs** | **Le plus cher** (premium) | 0,10 $/Go ingéré **+** ~1,70 $/M d'événements *indexés* | Découplage ingestion/indexation puissant mais piégeux : l'indexation domine la facture. Un microservice en DEBUG peut coûter très cher. |
| **Splunk** | Le plus cher historiquement | Licence entreprise (au volume, très élevée) | Référence du log analytics en entreprise/sécurité ; capacités énormes, coût parmi les plus hauts du marché. |

**Le choix gratuit :** **Grafana Loki**, alimenté via l'**OTel Collector** (ou **Alloy/Fluent Bit**). Règle d'or : **logs structurés en JSON** et **`trace_id` injecté** dans chaque log pour la corrélation. Gardez peu de labels (sinon explosion de cardinalité) et mettez les champs à forte cardinalité (request_id, user_id) en *structured metadata*, pas en labels.
---

### 4.5 Traces distribuées — le pont MACRO ↔ MICRO

**Rôle.** Suivre une requête *de bout en bout* à travers tous les services. Chaque étape est un **span** (`trace_id`, `span_id`, service, durée). Indispensable dès qu'il y a plus d'un service (microservices, serverless, files de messages).

**Vue apportée.** **Le lien** entre les deux échelles : d'une latence agrégée (macro), on descend à la sous-opération exacte qui coince (micro). Sans traces, un ralentissement dans un système réparti est quasi indébogable.

```mermaid
sequenceDiagram
  autonumber
  participant U as Utilisateur
  participant F as Frontend
  participant API as API Gateway
  participant SVC as Service Commande
  participant DB as Base de données
  U->>F: clic "Payer"
  F->>API: POST /checkout  (trace_id créé)
  API->>SVC: appel gRPC  (span enfant)
  SVC->>DB: requête SQL  (span enfant)
  DB-->>SVC: résultat  (⚠ 220 ms — le goulot !)
  SVC-->>API: réponse
  API-->>F: 200 OK
  F-->>U: confirmation
```

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Grafana Tempo** *(retenu)* | Le moins cher / cloud-native | **Gratuit** (OSS) | N'indexe que le `trace_id`, stocke tout sur objet → **très** économique. Recherche **TraceQL**, intégration Grafana native, exemplars depuis les métriques. |
| **Jaeger** | Le plus éprouvé (OSS) | **Gratuit** (OSS) | Standard historique du tracing, natif OTel, backends multiples (Cassandra, ES, ClickHouse). Excellent si le tracing est isolé du reste. |
| **Grafana Beyla** / **Pixie** (eBPF) | Le plus « zéro-effort » | **Gratuit** (OSS) | Auto-instrumentation via **eBPF** : des traces sans toucher au code. Complément idéal d'OTel. |
| **Datadog APM** | **Le plus cher** (premium) | ~31 $/hôte/mois (**+** infra obligatoire ≈ 46 $/hôte) ; 150 Go de spans inclus puis surcoût | Cartes de services et *flame graphs* superbes, très intégrés — mais coût élevé et lié à l'agent propriétaire. |
| New Relic / Dynatrace | Alternatives premium | Ingestion / hôte | APM matures, IA d'analyse ; verrouillage et coût à l'échelle. |

**Le choix gratuit :** **Grafana Tempo**, alimenté par **OTel Collector** avec **échantillonnage tail-based** (on garde 100 % des traces en erreur/lentes, un faible pourcentage du reste) pour maîtriser le volume. Option **Beyla (eBPF)** pour instrumenter sans code.

---

### 4.6 Suivi d'erreurs & crash — la couche « qualité applicative »

**Rôle.** Capturer les **exceptions** (backend, JS navigateur, crashes mobiles), les **regrouper** intelligemment (dédoublonnage), les prioriser par impact utilisateur, et alerter le développeur avec la stack trace, les *breadcrumbs* et la version fautive. C'est distinct des logs : c'est un **workflow de triage de bugs**.

**Vue apportée.** **Micro**, orientée développeur : « quelle erreur, combien d'utilisateurs touchés, depuis quelle release, avec quelle pile d'appels ».

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Sentry (auto-hébergé)** *(le meilleur + le plus utilisé)* | **Retenu (si ressources)** | **Gratuit** en self-host (licence BSL) ; SaaS dès ~26–31 $/mois | Standard de fait. Support de dizaines de langages, symbolication native (iOS/Android/C++), *session replay*, profiling, tracing. Contrepartie self-host : **lourd** (ClickHouse, Kafka, Redis, 20+ conteneurs, 8+ Go RAM). |
| **GlitchTip** *(retenu si l'on veut léger)* | Le moins cher / le plus simple | **Gratuit** en self-host ; SaaS dès ~15 $/mois | **Drop-in** compatible SDK Sentry (on change juste la DSN, zéro code). ~4 conteneurs, tourne sous 512 Mo–2 Go RAM. Inclut un uptime monitoring basique. Pas de session replay ni tracing profond. |
| **Bugsink** | Le plus léger | **Gratuit** (self-host) | Encore plus minimaliste, compatible SDK Sentry ; idéal solo/petite équipe. |
| **Sentry SaaS** | Repère « payant » | Free 5 000 erreurs/1 user ; Team ~31 $/siège | Zéro ops, mais quota par événement : un pic d'erreurs peut consommer le forfait en une heure. |
| Intégré à l'APM (Datadog/New Relic Error Tracking) | Le plus cher globalement | Inclus dans l'APM premium | Pratique si vous êtes déjà chez eux ; sinon surcoût et verrouillage. |

**Le choix gratuit :** **GlitchTip** (léger, drop-in Sentry) pour démarrer ; **Sentry self-hosted** si vous voulez session replay + profiling et disposez des ressources. Les deux réutilisent les **SDK Sentry** (gratuits) côté web, mobile et backend.

---

### 4.7 RUM — Real User Monitoring (web & mobile)

**Rôle.** Mesurer l'expérience **réelle côté client** : temps de chargement, **Core Web Vitals** (LCP, INP, CLS), erreurs JS, plantages mobiles, parcours et *rage-clicks*. Seule vue « depuis le navigateur/le téléphone de l'utilisateur ».

**Vue apportée.** **Macro & micro côté client** : macro (la perf perçue par segment : pays, appareil, réseau), micro (la session d'un utilisateur qui a planté).

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Grafana Faro** *(retenu web)* | Le moins cher / natif stack | **Gratuit** (OSS) | SDK web open source qui envoie erreurs, Web Vitals et traces frontend dans Loki/Tempo/Prometheus. Corrèle le front avec le back **dans le même Grafana**. |
| **SDK OpenTelemetry (browser/mobile)** | Le plus neutre | **Gratuit** | RUM basé sur le standard OTel, portable. |
| **Sentry (web + mobile)** *(retenu mobile)* | Le meilleur pour le crash + replay | **Gratuit** self-host | Excellent *crash reporting* mobile (symbolication iOS/Android), *session replay* web, erreurs corrélées aux releases. |
| **PostHog** | Le plus « produit » | Free 100 000 erreurs/mois | Combine RUM/erreurs, *session replay*, analytics produit, feature flags — utile en startup. |
| **Datadog RUM / New Relic Browser** | **Le plus cher** (premium) | Facturé par **session** (p. ex. RUM Datadog par tranche de 10 000 sessions) | Très complet ; coût par session qui grimpe sur une app grand public. |

**Le choix gratuit :** **Grafana Faro** (web, pour rester dans l'écosystème Grafana) **+ Sentry SDK** (mobile, pour le crash reporting et le replay). Tout est gratuit et corrélé au reste.

---

### 4.8 Uptime & monitoring synthétique — la vue « de l'extérieur »

**Rôle.** Tester le service **depuis l'extérieur**, en continu : le endpoint répond-il ? le certificat TLS expire-t-il ? le parcours de connexion fonctionne-t-il ? (*synthetic* = on simule un utilisateur/robot). Détecte les pannes **avant** que les vrais utilisateurs ne les subissent, et alimente une **page de statut** publique.

**Vue apportée.** **Macro externe** : disponibilité perçue de l'extérieur, indépendante de vos serveurs (donc utile même si toute votre infra est down).

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Uptime Kuma** *(retenu)* | Le plus utilisé (self-host) | **Gratuit** (OSS) | Ultra-populaire, interface soignée, sondes HTTP(s)/TCP/ping/keyword, **pages de statut**, notifications (Slack, Telegram, e-mail…). Installation en minutes. |
| **Prometheus Blackbox Exporter** *(complément)* | Le plus intégré | **Gratuit** (OSS) | Sondes HTTP/TCP/ICMP/DNS exposées en métriques Prometheus → alertes et dashboards Grafana unifiés. |
| **Gatus** | Le plus « as-code » | **Gratuit** (OSS) | Sondes déclarées en YAML, léger, page de statut ; idéal GitOps. |
| **Grafana Synthetic Monitoring / k6** | Parcours scriptés | **Gratuit** (OSS) pour k6 ; cloud avec quota | Tests de parcours et de charge scriptés (k6), sondes multi-régions côté cloud. |
| **Datadog Synthetics / Pingdom / Better Uptime** | Repère « payant » | Par test/checks (souvent des centaines de $/mois) | Sondes multi-régions clé en main, pratiques mais payantes. |

**Le choix gratuit :** **Uptime Kuma** (uptime + page de statut) **+ Blackbox Exporter** (sondes intégrées à Prometheus/Grafana) **+ k6** pour les parcours scriptés.

---

### 4.9 Profiling continu — l'optimisation au niveau du code

**Rôle.** Échantillonner en continu la pile d'appels pour savoir **quelle fonction** consomme CPU, mémoire ou temps. Là où la trace pointe le *service* lent, le profil pointe la *ligne de code*.

**Vue apportée.** **Micro extrême**, orientée performance/coût. Signal encore émergent (adoption à un chiffre, ~9 %, dans les enquêtes OpenTelemetry — §9.4), mais très rentable pour réduire la facture cloud.

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Grafana Pyroscope** *(retenu)* | Le plus utilisé (OSS) | **Gratuit** (OSS) | Profiling continu intégré à Grafana, *flame graphs*, corrélation traces ↔ profils. |
| **Parca** / **eBPF profilers** | Le plus « zéro-effort » | **Gratuit** (OSS) | Profiling système via eBPF, sans instrumentation. |
| **Datadog Continuous Profiler** | **Le plus cher** (premium) | ~19 $/hôte/mois | Intégré à l'APM Datadog ; efficace mais payant et verrouillé. |

**Le choix gratuit :** **Grafana Pyroscope**. Le serveur est inclus dans le compose (§10.4) et le SDK s'active en deux lignes (§10.1) — mais gardez-le pour la phase de maturité (§8), il n'est pas indispensable au démarrage.

---

### 4.10 Visualisation — le point d'entrée unique

**Rôle.** Une **seule interface** pour interroger tous les backends, afficher les dashboards, explorer et **naviguer d'un signal à l'autre**. C'est le « cockpit ».

**Vue apportée.** Les deux : macro (dashboards de synthèse) et micro (exploration, corrélation).

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Grafana** *(le plus utilisé + retenu)* | **Retenu** | **Gratuit** (OSS, self-host) ; Grafana Cloud avec offre gratuite | Standard de la visualisation. Se connecte à **tout** (Prometheus, Loki, Tempo, Pyroscope, OpenSearch, bases SQL…). Écosystème de plugins et de dashboards prêts à l'emploi immense. Corrélation native métrique → trace → log. |
| **Kibana** | Le meilleur pour ELK/logs | **Gratuit** (OSS) | Excellent si votre socle est OpenSearch/Elastic ; centré sur les logs. |
| **Perses** | Le plus « dashboards-as-code » | **Gratuit** (OSS) | Projet CNCF émergent, dashboards versionnés (GitOps). |
| Interfaces intégrées (Datadog, New Relic) | Repère « payant » | Incluses dans la licence | Très soignées et unifiées, mais indissociables de la facture et du verrouillage. |

**Le choix gratuit :** **Grafana** (OSS, auto-hébergé). C'est le cœur visible de la stack.

---

### 4.11 Alerte & astreinte (on-call) — de la donnée à l'action

**Rôle.** Deux étapes distinctes : (1) **détecter** — des règles évaluent les données et lèvent une alerte ; (2) **router** — un système d'astreinte envoie la bonne alerte à la bonne personne, gère les **escalades**, les **gardes** (qui est de permanence), le *silencing*, et la **réponse à incident**. Sans la 2ᵉ étape, les alertes se noient (*alert fatigue*).

**Vue apportée.** Opérationnelle : c'est ce qui réveille (ou non) quelqu'un à 3 h du matin. **Alerter sur les symptômes utilisateur (SLO), pas sur chaque cause** — sinon bruit et fatigue.

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Prometheus Alertmanager** *(retenu — détection)* | Le plus utilisé (OSS) | **Gratuit** (OSS) | Standard pour router/dédupliquer/regrouper les alertes issues de PromQL. Intégrations Slack, e-mail, webhooks. |
| **Grafana Alerting** *(retenu — détection)* | Unifié | **Gratuit** (OSS) | Règles d'alerte multi-sources (métriques *et* logs) directement dans Grafana. |
| **OneUptime** *(retenu — astreinte)* | Le plus « tout-en-un » (OSS) | **Gratuit** (self-host) | Gardes, escalades, notifications (appel/SMS/push/e-mail), et en bonus uptime + page de statut + gestion d'incidents dans un seul produit open source activement maintenu. Contrepartie : plateforme complète (plusieurs conteneurs), à héberger de préférence sur une machine **séparée** — bonne pratique de toute façon (§7.5 : le surveillant ne doit pas tomber avec le surveillé). |
| ~~Grafana OnCall OSS~~ | ⚠ **Archivé** | — | Ex-choix évident de la stack Grafana, passé en maintenance le 11/03/2025 puis **archivé le 24/03/2026**. Le code AGPLv3 fonctionne encore mais ne reçoit plus ni correctifs ni patchs de CVE : à ne plus retenir pour un nouveau déploiement. Grafana pousse vers son offre SaaS payante « Grafana Cloud IRM ». |
| **PagerDuty / Opsgenie** | **Le plus cher** (premium) | ~21–41 $/utilisateur/mois | Références de l'astreinte d'entreprise (analytics, intégrations, fiabilité éprouvée) ; efficaces mais payants. |

**Le choix gratuit :** **Alertmanager + Grafana Alerting** (détection) **+ OneUptime** (astreinte : gardes, escalades, appels/SMS — via son intégration webhook Alertmanager). 100 % gratuit et auto-hébergé. *(Grafana OnCall, l'ancien choix naturel de cette stack, est archivé depuis mars 2026 — voir le tableau.)*

---

### 4.12 SLO / SLI — piloter la fiabilité par les objectifs

**Rôle.** Définir des **SLI** (indicateurs : % de requêtes réussies, % sous 300 ms) et des **SLO** (objectifs : 99,9 % sur 30 jours). En découle le **budget d'erreur** (l'indispo « autorisée ») : tant qu'il reste du budget, on livre vite ; s'il s'épuise, on gèle et on stabilise. La grande majorité des organisations interrogées par les rapports SRE annuels déclarent utiliser des SLO (~86 % — §9.4).

**Vue apportée.** **Macro-business** : traduit la technique en langage produit/direction (« tenons-nous notre promesse de fiabilité ? »). Base des **alertes intelligentes** : on alerte sur la **vitesse de consommation** du budget d'erreur (*burn rate*), pas sur des seuils CPU arbitraires.

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Sloth** *(retenu)* | Le plus simple (OSS) | **Gratuit** (OSS) | Génère règles Prometheus + alertes multi-*burn-rate* + dashboards Grafana à partir d'une définition YAML de SLO. |
| **Pyrra** | Le plus visuel (OSS) | **Gratuit** (OSS) | UI de gestion des SLO au-dessus de Prometheus, suivi du budget d'erreur en temps réel. |
| **Grafana SLO** / éditeurs APM | Repère « payant » | Inclus dans les offres commerciales | SLO clé en main, mais liés à la plateforme et à sa facture. |

**Le choix gratuit :** **Sloth** (SLO-as-code) et/ou **Pyrra** (UI), au-dessus de Prometheus + Grafana. À mettre en place en phase de maturité (§8).
---

<a name="5"></a>
## 5. Les écrans qui comptent (et pourquoi)

Collecter des signaux ne sert à rien sans les **bons écrans**. Un piège classique : cent dashboards que personne ne regarde. La règle est **hiérarchique** — on part d'une vue macro unique et on **descend** (*drill-down*) jusqu'au détail micro. Chaque écran a **un public** et **un moment d'usage** précis.

```mermaid
flowchart TB
  D0["NIVEAU 0 · MACRO<br/>Santé globale / NOC<br/><i>« Est-ce que ça va ? »</i>"]
  D4["SLO & BUDGET D'ERREUR<br/>Tenons-nous nos promesses ?"]
  D5["RUM / PARCOURS UTILISATEUR<br/>Que vit le client ?"]
  D6["BUSINESS / KPI PRODUIT<br/>Impact métier"]
  D1["NIVEAU 1 · SERVICE (RED)<br/>Débit · Erreurs · Latence<br/>par service"]
  D2["NIVEAU 2 · RESSOURCE (USE)<br/>Infra · conteneurs · bases<br/>Utilisation · Saturation · Erreurs"]
  D3["NIVEAU 3 · MICRO<br/>Trace + Logs + Profil<br/><i>« Que s'est-il passé exactement ? »</i>"]

  D0 --> D1
  D0 --> D4
  D0 --> D5
  D0 --> D6
  D1 --> D2
  D1 --> D3
  D2 --> D3
  D4 -.-> D1
  D5 -.-> D3
```

### Les trois méthodes qui structurent les écrans

Avant les écrans, trois cadres éprouvés disent **quoi mettre dessus** :

- **Four Golden Signals** (Google SRE) — pour tout service orienté requêtes : **Latence**, **Trafic**, **Erreurs**, **Saturation**. Le point de départ le plus universel.
- **Méthode RED** — pour les **services** : **R**ate (débit, req/s), **E**rrors (taux d'erreur), **D**uration (latence, p50/p95/p99). Idéale pour un dashboard par microservice.
- **Méthode USE** — pour les **ressources** (CPU, RAM, disque, réseau, pools de connexions) : **U**tilization, **S**aturation, **E**rrors. Idéale pour l'infrastructure et les bases.

Retenez : **RED pour le code, USE pour la machine, Golden Signals pour cadrer l'ensemble.**

### Le catalogue des écrans

| # | Écran | Public | Quand on le regarde | Vue | Panneaux clés | Pourquoi il existe |
|---|---|---|---|---|---|---|
| 0 | **Santé globale / NOC** | Direction, astreinte | En permanence (écran mural), 1ᵉʳ coup d'œil | MACRO | Feu tricolore par service, dispo globale, taux d'erreur & latence agrégés, incidents ouverts, carte des dépendances | Répondre en 3 s à « tout va bien ? » et servir de porte d'entrée vers le drill-down |
| 1 | **Service (RED)** | Dev, SRE | Quand un service est suspect | MACRO→micro | Req/s, % erreurs, latence p50/p95/p99, top endpoints lents, exemplars → traces | Isoler *quel* service souffre et *à quel point*, puis plonger dans une trace |
| 2 | **Infra / ressources (USE)** | SRE, ops | Suspicion de saturation | MACRO | CPU/RAM/disque/réseau par nœud & conteneur, saturation, redémarrages, pods en *pending* | Distinguer « le code est lent » de « la machine est saturée » |
| 3 | **Base de données** | Dev, DBA | Latence liée aux données | MACRO→micro | Requêtes lentes, connexions actives vs pool, cache hit ratio, verrous, réplication | La base est la cause n°1 de latence ; écran dédié indispensable |
| 4 | **SLO & budget d'erreur** | SRE, product, direction | Hebdo + décision de release | MACRO-business | SLO par service, budget d'erreur restant, *burn rate* multi-fenêtres, historique | Piloter la fiabilité par objectif ; décider *livrer vite* vs *stabiliser* |
| 5 | **Investigation / trace** | Dev en debug | Pendant un incident | MICRO | *Flame graph* de la trace, cascade des spans, logs corrélés (`trace_id`), profil CPU | Trouver la cause racine exacte d'une requête lente/en erreur |
| 6 | **RUM — parcours utilisateur** | Front, product | Perf/plaintes côté client | Client (macro+micro) | Core Web Vitals (LCP/INP/CLS), erreurs JS, chargement par pays/appareil/réseau, replay de session | Voir ce que vit *l'utilisateur réel*, pas seulement le serveur |
| 7 | **Mobile / crash** | Mobile, QA | Après release mobile | Client | Taux de sessions sans crash, crashes par version/OS/appareil, ANR, adoption des versions | Un crash mobile ne se voit pas côté serveur ; suivi dédié |
| 8 | **Erreurs (Sentry/GlitchTip)** | Dev | Quotidien (triage) | MICRO | Nouvelles erreurs, fréquence, utilisateurs touchés, release fautive, stack trace | Transformer les exceptions en tâches de correction priorisées |
| 9 | **Uptime & page de statut** | Support, externe/public | Continu + comm. de crise | MACRO externe | Dispo par sonde, latence externe, expiration TLS, historique d'incidents | Vue « de l'extérieur » + transparence vis-à-vis des clients |
| 10 | **Alertes & astreinte** | Astreinte | Pendant l'incident | Opérationnel | Alertes actives, qui est de garde, escalades, MTTA/MTTR, alertes les plus bruyantes | Piloter la réponse et **réduire le bruit** (fatigue d'alerte) |
| 11 | **Business / KPI produit** | Product, direction | Quotidien/hebdo | MACRO-business | Commandes/min, tunnel de conversion, paiements OK/KO, signups, chiffre par minute | Relier la technique à l'impact métier ; détecter une panne *silencieuse* (technique verte mais ventes en chute) |
| 12 | **Coût / capacité** | Platform, finance | Mensuel | MACRO | Volume ingéré par signal, top services émetteurs, cardinalité, tendance de rétention | Maîtriser le coût (ou le disque) de l'observabilité elle-même |

### Le scénario type d'un incident (le fil rouge)

C'est l'enchaînement d'écrans qui prouve la valeur de la stack :

```mermaid
flowchart LR
  S0["Écran 0 · NOC<br/>Service Paiement<br/>passe au rouge"] --> S4["Écran 4 · SLO<br/>budget d'erreur<br/>brûle vite"]
  S4 --> S1["Écran 1 · RED<br/>latence p99 x5<br/>sur /checkout"]
  S1 -->|"clic exemplar"| S5["Écran 5 · Trace<br/>span DB = 220 ms"]
  S5 -->|"trace_id"| L["Logs corrélés<br/>'lock wait timeout'"]
  S5 --> S3["Écran 3 · DB<br/>connexions saturées<br/>après le déploiement 14h02"]
  L --> FIX["Cause racine → rollback / correctif"]
```

De la vue **macro** (un feu rouge) à la **cause racine** (un verrou de base après un déploiement) en **quelques clics**, sans changer d'outil. **C'est l'objectif de toute l'architecture.**

### Principes de conception des écrans

1. **Un écran = une question.** S'il faut expliquer un dashboard, il en fait trop.
2. **Du général au particulier.** Toujours un point d'entrée macro qui *descend* vers le micro (liens de drill-down entre panneaux).
3. **Alerter sur les symptômes (SLO), enquêter avec les causes.** Les seuils CPU font du bruit ; le budget d'erreur fait du sens.
4. **Superposer les événements** (déploiements, changements) sur les courbes : « qu'est-ce qui a changé juste avant ? » est la question la plus rentable.
5. **Dashboards-as-code** (JSON versionné, provisionnés par Grafana) : reproductibles, revus, non « cassés » manuellement.
6. **Cohérence des variables** (`$service`, `$env`, `$region`) pour qu'un même dashboard serve tous les services.
---

<a name="6"></a>
## 6. La stack finale 100 % gratuite

Voici la synthèse : une stack **entièrement gratuite, open source et auto-hébergeable**, cohérente de bout en bout. Son ossature est le **stack LGTM de Grafana** — **L**oki (logs), **G**rafana (visualisation), **T**empo (traces), **M**imir (métriques) — le socle open source d'observabilité **le plus déployé en production**, complété par OpenTelemetry, le suivi d'erreurs, l'uptime, le profiling et l'astreinte.

```mermaid
flowchart TB
  subgraph INST["① INSTRUMENTATION (universelle, gratuite)"]
    direction LR
    I1["OpenTelemetry SDK<br/>+ auto-instrumentation<br/>(backend)"]
    I2["Grafana Faro<br/>(web / RUM)"]
    I3["Sentry SDK<br/>(mobile / crash)"]
  end

  subgraph AGE["② AGENTS & EXPORTERS (gratuits)"]
    direction LR
    G1["Node Exporter · cAdvisor<br/>kube-state-metrics"]
    G2["Blackbox Exporter<br/>Uptime Kuma (sondes externes)"]
    G3["Exporters DB<br/>(Postgres, Redis, Nginx…)"]
  end

  subgraph PIPE["③ PIPELINE (gratuit)"]
    OC["OpenTelemetry Collector<br/>+ Grafana Alloy / Fluent Bit (logs)<br/>filtrage · échantillonnage · enrichissement"]
  end

  subgraph BACK["④ BACKENDS OPEN SOURCE"]
    direction LR
    B1["Prometheus + Mimir<br/>MÉTRIQUES"]
    B2["Loki<br/>LOGS"]
    B3["Tempo<br/>TRACES"]
    B4["Pyroscope<br/>PROFILS"]
    B5["Sentry / GlitchTip<br/>ERREURS & CRASH"]
  end

  subgraph FRONT["⑤ UI UNIQUE"]
    GR["GRAFANA<br/>dashboards · exploration · corrélation<br/>Sloth / Pyrra (SLO)"]
  end

  subgraph ALERT["⑥ ALERTE & ASTREINTE (gratuit)"]
    AM["Alertmanager + Grafana Alerting<br/>→ OneUptime (gardes, escalades)<br/>→ Slack · e-mail · téléphone"]
  end

  I1 --> OC
  I2 --> OC
  I3 -.-> B5
  I2 -.-> B5
  G1 --> B1
  G2 --> B1
  G3 --> B1
  OC --> B1
  OC --> B2
  OC --> B3
  I1 -.->|"SDK Pyroscope"| B4
  I1 -.-> B5
  B1 --> GR
  B2 --> GR
  B3 --> GR
  B4 --> GR
  B5 --> GR
  B1 --> AM
  GR --> AM
```

### Composant par composant — et pourquoi ce choix

| Rôle | Outil gratuit retenu | Pourquoi lui | Équivalent payant remplacé |
|---|---|---|---|
| **Instrumentation** | **OpenTelemetry** (+ Faro web, Sentry SDK mobile) | Standard neutre universel, aucun verrouillage, supporté partout | Agents Datadog / New Relic |
| **Pipeline** | **OpenTelemetry Collector** (+ Alloy/Fluent Bit) | Point unique de contrôle du volume/coût, route vers tout | Agents propriétaires |
| **Métriques** | **Prometheus + Grafana Mimir** | Standard de fait (PromQL) + rétention longue à bas coût sur objet | Datadog Metrics (~15 $/hôte + custom) |
| **Logs** | **Grafana Loki** | Indexation par labels → stockage objet très économique, corrélation native | Datadog Logs / Splunk |
| **Traces** | **Grafana Tempo** | N'indexe que le `trace_id`, stockage objet, TraceQL, exemplars | Datadog APM (~46 $/hôte) |
| **Erreurs / crash** | **GlitchTip** (léger) ou **Sentry** self-host | Drop-in SDK Sentry, triage de bugs, symbolication mobile | Sentry SaaS (~31 $/siège) |
| **RUM web** | **Grafana Faro** | Front corrélé au back dans le même Grafana | Datadog RUM (par session) |
| **Crash mobile** | **Sentry SDK** | Symbolication iOS/Android, sessions sans crash | New Relic Mobile / Firebase |
| **Uptime / statut** | **Uptime Kuma** (+ Blackbox Exporter) | Populaire, sondes + page de statut, alertes | Pingdom / Datadog Synthetics |
| **Parcours scriptés** | **k6** | Tests de parcours et de charge open source | Datadog / Grafana Cloud Synthetics |
| **Profiling** | **Grafana Pyroscope** | Flame graphs continus, corrélés aux traces | Datadog Profiler (~19 $/hôte) |
| **Visualisation** | **Grafana** | Se connecte à tout, corrélation native, écosystème énorme | UI Datadog / New Relic |
| **Alerte** | **Alertmanager + Grafana Alerting** | Standard, multi-sources | Intégré aux offres premium |
| **Astreinte (on-call)** | **OneUptime** | Gardes, escalades, appels/SMS + incidents & statut — libre et maintenu (OnCall OSS est archivé depuis 03/2026) | PagerDuty / Opsgenie (~21–41 $/user) |
| **SLO / budget d'erreur** | **Sloth** / **Pyrra** | SLO-as-code + budget d'erreur au-dessus de Prometheus | SLO des plateformes commerciales |

### Deux façons d'exploiter cette stack gratuitement

1. **100 % auto-hébergé (le vrai gratuit total, retenu ici).** Tous les composants ci-dessus tournent sur **votre** infrastructure (un serveur, du Docker, ou Kubernetes). Le logiciel est gratuit ; vous ne payez que vos propres machines (que vous avez déjà). **Aucun coût de licence, aucune donnée qui sort de chez vous, aucune limite de rétention imposée.**

2. **Offres gratuites managées (pour démarrer sans rien opérer).** Utile pour un POC : **Grafana Cloud Free** (10 000 séries de métriques, 50 Go de logs, 50 Go de traces, 50 Go de profils, 3 utilisateurs, 14 jours de rétention) et **New Relic Free** (100 Go/mois ingérés + 1 utilisateur) sont des offres gratuites *permanentes*. Limites : rétention et volumes plafonnés — on les dépasse vite en production. **Le self-host reste la seule voie « full gratuit » sans plafond.**

> **Alternatives « tout-en-un » gratuites à connaître** : si vous préférez *un seul binaire* plutôt qu'assembler des briques, **SigNoz** (natif OpenTelemetry : métriques + logs + traces + APM dans une UI) et **OpenObserve** (natif stockage objet, requêtes SQL) sont d'excellents choix open source auto-hébergeables. Ils simplifient l'exploitation au prix d'un écosystème plus restreint que Grafana. **OneUptime**, retenu ici pour l'astreinte (§4.11), joue lui aussi cette carte tout-en-un côté réponse à incident : il peut à terme absorber les rôles d'Uptime Kuma (sondes + page de statut) si vous voulez réduire le nombre de briques.
---

<a name="7"></a>
## 7. Déploiement, topologies & maîtrise des coûts

### 7.1 Petite échelle — Docker Compose (un serveur)

Pour une petite/moyenne application, tout tient sur **une seule machine** via Docker Compose. C'est la façon la plus simple de démarrer « full gratuit ».

```mermaid
flowchart TB
  subgraph HOST["Un serveur (Docker Compose)"]
    APP["Vos applis<br/>(SDK OTel)"]
    OC["OTel Collector"]
    subgraph LGTM["Stack LGTM + profils"]
      P["Prometheus"]
      L["Loki"]
      T["Tempo"]
      PY["Pyroscope"]
    end
    SN["GlitchTip / Sentry"]
    UK["Uptime Kuma"]
    GR["Grafana"]
    APP --> OC
    OC --> P
    OC --> L
    OC --> T
    APP -.->|SDK profils| PY
    APP -.-> SN
    P --> GR
    L --> GR
    T --> GR
    PY --> GR
    SN --> GR
  end
  OBJ["Stockage objet<br/>(S3/GCS/MinIO, gratuit avec MinIO)"]
  L --> OBJ
  T --> OBJ
```

**Bon à savoir** : Loki et Tempo écrivent leur volume sur du **stockage objet** ; en auto-hébergé gratuit, utilisez **MinIO** (S3 open source) ou un simple disque local pour démarrer. À cette échelle, **Mimir est volontairement absent** : Prometheus seul (rétention 15 j) suffit largement sur un mono-serveur ; Mimir n'entre en scène qu'avec la topologie Kubernetes (§7.2, §10.8) pour la rétention longue et le multi-tenant. Le `docker-compose.yml` complet et toutes les configurations de cette topologie sont fournis en **§10**.

### 7.2 Grande échelle — Kubernetes (agent + gateway)

À l'échelle, le motif standard est : un **collecteur-agent** sur chaque nœud (en *DaemonSet*) qui capte tout localement, puis un **collecteur-gateway** centralisé qui applique l'**échantillonnage tail-based** et le batching avant d'écrire dans les backends.

```mermaid
flowchart TB
  subgraph NODES["Sur chaque nœud Kubernetes"]
    direction TB
    APP["Pods applicatifs (SDK OTel)"]
    DS["OTel Collector — AGENT (DaemonSet)<br/>+ Node Exporter + cAdvisor"]
    APP --> DS
  end
  subgraph CLUSTER["Passerelle (déploiement dédié)"]
    GC["OTel Collector — GATEWAY<br/>échantillonnage tail-based · batching · enrichissement"]
  end
  subgraph OBS["Namespace observabilité"]
    direction LR
    M["Mimir"]
    L["Loki"]
    T["Tempo"]
    PY["Pyroscope"]
    GR["Grafana"]
  end
  OBJ["Stockage objet (S3 / GCS)"]

  DS --> GC
  GC --> M
  GC --> L
  GC --> T
  GC --> PY
  M --> OBJ
  L --> OBJ
  T --> OBJ
  M --> GR
  L --> GR
  T --> GR
  PY --> GR
```

**Astuce d'installation** : les charts Helm **`kube-prometheus-stack`** (Prometheus + Alertmanager + Grafana + exporters) et **`loki` / `tempo` / `mimir` / `pyroscope`** de Grafana déploient l'essentiel en quelques commandes. **OpenTelemetry Operator** gère l'auto-instrumentation et les collecteurs.

### 7.3 Maîtriser le coût (ou le disque) — c'est *ici* que ça se joue

Même « gratuit », l'observabilité a un coût **de stockage et d'exploitation**. Le volume est piloté **à l'ingestion**, pas à l'affichage. Trois leviers :

- **Échantillonnage des traces (le plus puissant).** *Tail-based sampling* dans le Gateway : garder **100 %** des traces en **erreur** ou **lentes**, et seulement **1–20 %** des traces normales. On garde le signal utile, on jette le bruit. *Attention* : toute métrique dérivée des spans (carte des services, RED par span) doit être calculée **avant** cet échantillonnage, sinon elle est biaisée — c'est le rôle des connecteurs du Collector (§10.3).
- **Rétention par niveau.** Chaud (récent, rapide, sur disque) vs froid (ancien, sur objet bon marché). Ex. : métriques 13 mois, logs 30 jours, traces 7–15 jours. La rétention est le **premier** facteur de coût.
- **Discipline de cardinalité (le piège n°1).** Ne **jamais** mettre un identifiant à forte cardinalité (`user_id`, `request_id`, UUID, nom de pod éphémère) en **label** de métrique ou de log : chaque valeur crée une nouvelle série et fait exploser le stockage. Ces champs vont dans les **attributs de trace** ou en *structured metadata* Loki, où ils restent interrogeables sans coût de cardinalité.

```mermaid
flowchart LR
  RAW["Télémétrie brute<br/>(100 % du volume)"] --> F["Filtrer<br/>(jeter health-checks, DEBUG en prod)"]
  F --> S["Échantillonner traces<br/>(garder erreurs + lentes)"]
  S --> R["Rétention par niveau<br/>(chaud court / froid long)"]
  R --> STORE["Stockage maîtrisé<br/>(objet bon marché)"]
```

**Autres bonnes pratiques** : agréger les métriques haute fréquence avant stockage ; désactiver les logs DEBUG en production ; définir des quotas par équipe/tenant ; surveiller l'observabilité elle-même (écran 12 « Coût/capacité »).

### 7.4 Avant la prod : durcissement

Les configurations de la §10 sont volontairement **minimales et pédagogiques** (`auth_enabled: false` sur Loki, `tls: insecure` entre Collector et Tempo, secrets en variables d'environnement). C'est acceptable pour un lab ou un réseau strictement privé — pas pour une exposition réelle. Avant la mise en production, quatre chantiers, dans cet ordre :

1. **Exposition réseau minimale.** Seuls Grafana, la page de statut et les endpoints publics indispensables (Collector OTLP si des clients externes émettent, récepteur Faro) sortent du réseau interne. Tout le reste — Prometheus, Loki, Tempo, Pyroscope, Alertmanager — ne publie **aucun port** : retirez les `ports:` du compose (les conteneurs se joignent par le réseau Docker interne) et fermez le pare-feu par défaut.
2. **TLS partout, via un reverse proxy.** Placez un **Caddy**, **Traefik** ou **nginx** (gratuits, certificats Let's Encrypt automatiques) devant chaque UI/endpoint exposé : Grafana, GlitchTip, Uptime Kuma, OneUptime, le récepteur Faro et l'endpoint OTLP (le Collector supporte aussi le TLS natif sur 4317/4318). En interne, activez le TLS inter-composants dès que le trafic quitte une seule machine.
3. **Authentification et rôles.** Grafana : mots de passe forts, rôles Viewer/Editor/Admin, et idéalement SSO (OAuth/OIDC — gratuit dans Grafana OSS). Loki/Tempo/Mimir n'ont **pas d'authentification propre** en mode mono-tenant : ils se protègent par le réseau ou derrière le proxy (basic auth / en-tête `X-Scope-OrgID` en multi-tenant). Les endpoints d'ingestion (OTLP, Faro) exposés publiquement se protègent par clé/token au niveau du proxy.
4. **Secrets et conformité.** Les secrets (`GRAFANA_ADMIN_PASSWORD`, `GT_SECRET_KEY`, webhooks Slack…) vivent dans un `.env` **hors Git** au minimum — Docker secrets, SOPS ou Vault dès que l'équipe grandit. Côté données : le masquage des champs sensibles se fait **au Collector** (`attributes/redact`, §10.3), c'est votre point de conformité RGPD — les en-têtes d'autorisation et identifiants personnels ne doivent jamais atteindre le stockage.

### 7.5 Qui surveille le surveillant ?

Question à se poser *avant* le premier incident : **que se passe-t-il si le serveur d'observabilité tombe — précisément pendant la panne qu'il devait vous montrer ?**

- **Une sonde externe indépendante.** C'est la parade principale, déjà dans la stack : **Uptime Kuma** (ou les sondes OneUptime) doit tourner **ailleurs** que sur l'infra qu'il surveille — petit VPS à part, autre région, autre fournisseur. Il surveille vos applications *et* la stack d'observabilité elle-même (Grafana, Prometheus, le Collector). Même logique pour l'astreinte : OneUptime héberge les escalades téléphoniques, il ne doit pas partager le sort du serveur surveillé.
- **L'auto-surveillance est déjà câblée.** Prometheus scrape sa propre santé et celle du Collector (`otel-collector:8888`, §10.4) ; l'écran 12 suit volume et cardinalité. Ajoutez une alerte « heartbeat » inversée (un signal périodique dont l'*absence* alerte via la sonde externe) pour détecter un pipeline silencieusement mort.
- **Sauvegardes.** L'as-code (dashboards JSON, datasources provisionnées, règles d'alerte, SLO Sloth — tout est dans Git) est votre première sauvegarde : la stack se reconstruit par `docker compose up`. Restent les **données** : sauvegardez `grafana-data` (dashboards créés à la main, utilisateurs), `gt-db` (historique GlitchTip) et `kuma-data` — un simple snapshot/rsync nocturne des volumes suffit à cette échelle. Les données de télémétrie (métriques, logs, traces) sont généralement **acceptables à perdre** — décision à acter explicitement ; sinon, snapshots du stockage objet.
- **Perdre la télémétrie n'est pas perdre le service.** Les SDK OTel sont non-bloquants et le Collector amortit les coupures courtes (retry/queue) : si la stack d'observabilité tombe, vos applications continuent de tourner — vous êtes juste aveugle. D'où la sonde externe, qui, elle, voit tout de l'extérieur.
- **À l'échelle (Kubernetes, §7.2).** La HA devient native : Mimir/Loki/Tempo en mode distribué (réplicas multiples sur stockage objet), **2 réplicas Prometheus** identiques, **Alertmanager en cluster** (3 instances qui dédupliquent entre elles). Le mono-serveur de la §7.1 assume, lui, un SPOF — compensé par la sonde externe.

---

<a name="8"></a>
## 8. Modèle de maturité : par où commencer

N'installez pas tout d'un coup. Déployez **par phases**, chacune apportant une valeur immédiate. Une petite app peut s'arrêter à la phase 2 ; une plateforme critique ira jusqu'à la 4.

```mermaid
flowchart LR
  P0["PHASE 0 · Aveugle<br/>logs bruts + ping<br/>MTTD/MTTR élevés"]
  P1["PHASE 1 · Voir<br/>Prometheus + Grafana<br/>+ Uptime Kuma<br/>→ dashboards RED/USE + alertes de base"]
  P2["PHASE 2 · Contextualiser<br/>+ Loki (logs centralisés)<br/>+ GlitchTip (erreurs)<br/>→ débogage rapide"]
  P3["PHASE 3 · Corréler<br/>+ OTel + Tempo (traces)<br/>+ Faro (RUM)<br/>→ macro ↔ micro en 2 clics"]
  P4["PHASE 4 · Piloter<br/>+ SLO (Sloth/Pyrra)<br/>+ OneUptime + Pyroscope<br/>→ fiabilité pilotée par objectifs"]
  P0 --> P1 --> P2 --> P3 --> P4
```

| Phase | Objectif | On ajoute | Valeur obtenue |
|---|---|---|---|
| **1 · Voir** | Sortir de l'aveugle | Prometheus, Grafana, exporters, Uptime Kuma, Alertmanager | Dashboards macro (RED/USE) + savoir quand c'est down |
| **2 · Contextualiser** | Déboguer vite | Loki (logs), GlitchTip/Sentry (erreurs) | Retrouver *pourquoi* dans les logs et les exceptions |
| **3 · Corréler** | Relier les échelles | OpenTelemetry, Tempo (traces), Faro (RUM web) | Naviguer métrique → trace → log ; voir le client réel |
| **4 · Piloter** | Fiabilité proactive | SLO (Sloth/Pyrra), OneUptime (astreinte), Pyroscope (SDK) | Alertes intelligentes (burn rate), astreinte, optimisation code |

**Conseil** : commencez **petit et transverse** plutôt que « parfait sur un seul service ». Trois signaux basiques bien corrélés valent mieux qu'un seul signal parfait isolé.

---

<a name="9"></a>
## 9. Annexes

### 9.1 Checklist de mise en place

- [ ] Instrumenter **une seule fois** avec OpenTelemetry (auto puis manuel pour le métier).
- [ ] Convention de labels commune : `service`, `env`, `version`, `region`.
- [ ] Injecter le **`trace_id` dans tous les logs** ; logs en **JSON structuré**.
- [ ] Tout passe par l'**OTel Collector** (jamais d'app branchée en direct sur le backend).
- [ ] **Échantillonnage tail-based** activé (100 % des erreurs/lentes).
- [ ] Politique de **rétention par niveau** et **quotas** définis.
- [ ] Écran 0 (NOC) + un dashboard **RED par service** + **USE** infra.
- [ ] Alertes basées sur **SLO / burn rate**, pas sur des seuils CPU arbitraires.
- [ ] **Astreinte** configurée (gardes, escalades) avant d'en avoir besoin.
- [ ] Dashboards et alertes **versionnés (as-code)**.
- [ ] Un écran surveille le **coût/volume** de l'observabilité elle-même.
- [ ] **Durcissement fait (§7.4)** : ports internes non publiés, TLS + auth devant chaque UI/endpoint exposé, secrets hors Git, masquage des données sensibles au Collector.
- [ ] **Sonde externe hébergée hors de l'infra** surveillée (§7.5) — y compris sur la stack d'observabilité elle-même.
- [ ] **Sauvegarde** des volumes à état (Grafana, GlitchTip, Kuma) + décision explicite sur la perte acceptable de télémétrie (§7.5).

### 9.2 Anti-patterns à éviter

- **Verrouillage fournisseur** : instrumenter avec un agent propriétaire → migration = tout réécrire. *Toujours OTel.*
- **Explosion de cardinalité** : mettre `user_id`/UUID en label → facture/disque hors de contrôle.
- **Fatigue d'alerte** : alerter sur chaque cause/seuil → tout le monde ignore les alertes. *Alerter sur les symptômes (SLO).*
- **Trois silos non corrélés** : métriques, logs, traces sans `trace_id` commun → on ne peut pas naviguer.
- **Cimetière de dashboards** : 100 écrans que personne ne regarde. *Un écran = une question.*
- **Tout collecter sans filtrer** : 100 % des traces et logs DEBUG en prod → coût inutile.
- **Brancher les apps en direct sur le stockage** : plus de point de contrôle du volume ni du masquage des données sensibles.

### 9.3 Glossaire express

- **OTLP** — protocole standard d'OpenTelemetry pour transporter la télémétrie.
- **Span / Trace** — une étape / le parcours complet d'une requête entre services.
- **Exemplar** — point de métrique qui pointe vers une trace représentative (le lien macro→micro).
- **Cardinalité** — nombre de combinaisons uniques de labels ; principal facteur de coût des métriques.
- **SLI / SLO / budget d'erreur** — indicateur / objectif de fiabilité / indispo « autorisée ».
- **Burn rate** — vitesse de consommation du budget d'erreur ; base des alertes intelligentes.
- **RED / USE / Golden Signals** — cadres pour choisir *quoi* mettre sur un dashboard (services / ressources / général).
- **Tail-based sampling** — décider de garder une trace *après* l'avoir vue en entier (pour garder les erreurs/lentes).
- **RUM** — *Real User Monitoring* : mesure de l'expérience réelle côté navigateur/mobile.
- **LGTM** — Loki, Grafana, Tempo, Mimir : le socle open source retenu.
- **MTTD / MTTR** — temps moyen de détection / de résolution d'un incident.

### 9.4 Sources des chiffres

Les chiffres d'adoption et ordres de grandeur cités dans ce document (part du budget infra en §1 ; classement et adoption d'OpenTelemetry en §4.1 ; adoption de Prometheus en §4.3 ; adoption du profiling en §4.9 ; usage des SLO en §4.12) proviennent des sources publiques suivantes, à revérifier à date : les **enquêtes annuelles de la CNCF** (*Cloud Native Survey* et volets observabilité) et son **programme de mesure de vélocité des projets** ; les **enquêtes de la communauté OpenTelemetry** ; les **rapports SRE annuels** (Catchpoint/Google, *The SRE Report*) ; et les **études d'éditeurs** sur le coût de l'observabilité (Grafana Labs, New Relic *Observability Forecast*). Ce sont des enquêtes déclaratives : retenez les **ordres de grandeur** et les tendances, pas les décimales. Les statuts produits (ex. l'archivage de Grafana OnCall OSS au 24/03/2026) sont vérifiables dans les annonces officielles des éditeurs.

---

### En une phrase

**Instrumentez une fois avec OpenTelemetry, faites tout transiter par un collecteur, stockez chaque signal dans le stack LGTM (Prometheus/Mimir, Loki, Tempo) complété de Sentry/GlitchTip, Pyroscope et Uptime Kuma, visualisez et corrélez le tout dans Grafana, et alertez via Alertmanager relayé par l'astreinte OneUptime en pilotant par des SLO — le tout gratuit, open source et auto-hébergé, avec une navigation fluide de la vue macro à la cause racine micro.**
---

<a name="10"></a>
## 10. Mise en œuvre : le code complet de la stack gratuite

Cette section rend le document exécutable : instrumentation de **vos** technologies (Django, Angular), configuration du Collector, `docker-compose.yml` du socle §7.1, la **corrélation Grafana** (le fil rouge du document, en code), alertes/SLO, et sondes externes. Les versions sont épinglées à la date du document — actualisez-les via **Renovate** (document CI/CD, §4.10). Les jobs CI qui accompagnent tout ceci (annotations de déploiement, upload des source maps) sont déjà dans le document CI/CD, §10.

### 10.1 Backend Django — instrumentation OpenTelemetry + logs corrélés

**Dépendances** (à ajouter au `requirements.txt`) :

```text
opentelemetry-distro==0.50b0
opentelemetry-exporter-otlp==1.29.0
python-json-logger==3.2.1
```

Puis, une fois dans l'image (Dockerfile) : `opentelemetry-bootstrap -a install` — détecte Django, psycopg/pyodbc, redis, grpcio, requests… et installe les instrumentations correspondantes.

**Lancement auto-instrumenté** — zéro ligne de code applicatif, tout passe par l'environnement :

```bash
# Variables d'environnement (conteneur / values Helm)
OTEL_SERVICE_NAME=units-service
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod,service.version=${APP_VERSION}
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317   # jamais le backend en direct (§3)
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=none          # les logs partent par stdout JSON (voir plus bas)

# Commande de démarrage
opentelemetry-instrument gunicorn units_project.wsgi -b 0.0.0.0:8000 --workers 3
```

> ⚠ **gunicorn multi-workers** : les exporters OTel n'aiment pas le fork. Si vous constatez des spans manquants, initialisez le SDK dans le hook `post_fork` de `gunicorn.conf.py` plutôt que via le wrapper (pattern documenté par OTel Python). Avec uvicorn/daphne mono-process ou `runserver`, le wrapper suffit tel quel.

**Logs structurés avec `trace_id` dans le corps** — c'est ce qui rend le lien log → trace cliquable dans Grafana (§10.5) :

```python
# units_project/logging_utils.py
import logging
from opentelemetry import trace

class TraceContextFilter(logging.Filter):
    """Injecte trace_id/span_id du span courant dans chaque log."""
    def filter(self, record):
        ctx = trace.get_current_span().get_span_context()
        record.trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else ""
        record.span_id  = format(ctx.span_id,  "016x") if ctx.is_valid else ""
        return True
```

```python
# settings.py — extrait
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"trace": {"()": "units_project.logging_utils.TraceContextFilter"}},
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "filters": ["trace"], "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

**Avant / après** — le même événement, vu dans Loki :

```text
AVANT (texte libre, incorrélable) :
    Checkout failed for user 42: timeout

APRÈS (JSON structuré + trace_id → clic direct vers la trace) :
    {"asctime":"2026-07-09 14:02:31","levelname":"ERROR","name":"orders",
     "message":"checkout failed","reason":"timeout","order_id":"A-1289",
     "trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","span_id":"00f067aa0ba902b7"}
```

**Métrique métier + la règle de cardinalité (§7.3) en code** :

```python
from opentelemetry import metrics, trace

meter = metrics.get_meter("units-service")

# ❌ AVANT — user_id en label : une série PAR utilisateur → explosion du stockage
# orders_counter = meter.create_counter("orders_total")
# orders_counter.add(1, {"user_id": user.id, "status": "paid"})

# ✅ APRÈS — labels à faible cardinalité sur la métrique…
orders_counter = meter.create_counter("orders_total", description="Commandes créées")
orders_counter.add(1, {"status": "paid", "payment_method": "card"})

# …et l'identifiant à forte cardinalité en ATTRIBUT DE SPAN (gratuit côté cardinalité,
# retrouvable via TraceQL : { .user.id = "42" })
trace.get_current_span().set_attribute("user.id", str(user.id))
```

**Profiling continu (Pyroscope, §4.9)** — optionnel au démarrage (phase 4, §8), le serveur est déjà dans le compose (§10.4). Deux lignes suffisent côté Django (`pip install pyroscope-io`) :

```python
# settings.py — le SDK échantillonne la pile et pousse vers Pyroscope
import pyroscope
pyroscope.configure(
    application_name="units-service",
    server_address="http://pyroscope:4040",
    tags={"env": "prod", "version": APP_VERSION},
)
```

> Pour le lien **trace → profil** dans Grafana (`tracesToProfiles`, §10.5), ajoutez le *span processor* du paquet `pyroscope-otel` : chaque span porte alors l'ID de son profil, et le flame graph CPU s'ouvre depuis la trace (corrélation n°4 du §2).

### 10.2 Frontend Angular — Faro (RUM) + GlitchTip (erreurs)

```bash
npm i @grafana/faro-web-sdk @grafana/faro-web-tracing @sentry/angular
```

```ts
// main.ts — avant bootstrapApplication()
import { initializeFaro, getWebInstrumentations } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';

initializeFaro({
  url: 'https://obs.example.com/faro/collect',   // récepteur Faro d'Alloy (§10.4)
  app: { name: 'mir-webapp', version: APP_VERSION, environment: 'prod' },
  instrumentations: [
    ...getWebInstrumentations(),        // Web Vitals, erreurs JS, logs console, sessions
    new TracingInstrumentation(),       // traces fetch/XHR → propagées jusqu'à Django
  ],
});
```

```ts
// app.config.ts — GlitchTip via le SDK Sentry (drop-in, §4.6)
import * as Sentry from '@sentry/angular';

Sentry.init({
  dsn: 'https://<clé>@glitchtip.example.com/1',
  release: APP_VERSION,                 // = tag/SHA du pipeline → lien avec les source maps
  environment: 'prod',
  tracesSampleRate: 0,                  // le tracing est déjà porté par Faro
});

export const appConfig = {
  providers: [
    { provide: ErrorHandler, useValue: Sentry.createErrorHandler() },
    // ...
  ],
};
```

La `TracingInstrumentation` propage le contexte W3C (`traceparent`) sur les appels HTTP : **la trace frontend et la trace Django ne font qu'une** — on voit le clic utilisateur et la requête SQL dans le même flame graph. Côté mobile, le SDK Sentry (Android/iOS) s'initialise de la même façon (DSN GlitchTip + `release`), avec upload des symboles dans le pipeline.

### 10.3 Le pipeline — `otel-collector-config.yaml`

Le point de contrôle central (§3) : réception OTLP, nettoyage, **génération des métriques dérivées des spans (avant échantillonnage)**, échantillonnage tail-based, routage.

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  memory_limiter: { check_interval: 1s, limit_mib: 512 }

  # Enrichissement commun (labels disciplinés, §3.5)
  resource:
    attributes:
      - { key: deployment.environment, value: "${env:DEPLOY_ENV}", action: upsert }

  # Hygiène : jeter le bruit et les données sensibles AVANT stockage
  filter/drop_noise:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.route"] == "/health/"'    # adapter à vos routes
        - 'attributes["http.route"] == "/ready/"'
  attributes/redact:
    actions:
      - { key: http.request.header.authorization, action: delete }
      - { key: enduser.id, action: hash }

  # Échantillonnage tail-based (§7.3) : 100 % des erreurs et des lentes, 10 % du reste
  tail_sampling:
    decision_wait: 10s
    policies:
      - { name: errors,  type: status_code,  status_code: { status_codes: [ERROR] } }
      - { name: slow,    type: latency,      latency: { threshold_ms: 500 } }
      - { name: baseline, type: probabilistic, probabilistic: { sampling_percentage: 10 } }

  batch: { timeout: 5s }

# Métriques dérivées des spans — calculées sur 100 % du trafic, AVANT le tail sampling
connectors:
  spanmetrics: {}      # RED (débit/erreurs/latence) par service & route, sans instrumentation métrique
  servicegraph: {}     # nourrit la carte des services de Grafana (écran 0)

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls: { insecure: true }
  prometheusremotewrite:
    endpoint: http://prometheus:9090/api/v1/write   # Mimir à l'échelle (§7.2)
    resource_to_telemetry_conversion: { enabled: true }
  otlphttp/loki:
    endpoint: http://loki:3100/otlp                 # ingestion OTLP native de Loki 3

service:
  pipelines:
    traces/derive:                                   # ① 100 % des spans → métriques dérivées (PAS d'échantillonnage ici)
      receivers:  [otlp]
      processors: [memory_limiter, resource, filter/drop_noise, attributes/redact]
      exporters:  [spanmetrics, servicegraph]
    traces/store:                                    # ② échantillonnage tail-based, PUIS stockage dans Tempo
      receivers:  [otlp]
      processors: [memory_limiter, resource, filter/drop_noise, attributes/redact, tail_sampling, batch]
      exporters:  [otlp/tempo]
    metrics:
      receivers:  [otlp, spanmetrics, servicegraph]  # métriques SDK + métriques dérivées des spans
      processors: [memory_limiter, resource, batch]
      exporters:  [prometheusremotewrite]
    logs:                                            # utilisé surtout en K8s ;
      receivers:  [otlp]                             # en compose, les logs passent par Alloy (§10.4)
      processors: [memory_limiter, resource, batch]
      exporters:  [otlphttp/loki]
```

> ⚠ **Pourquoi deux pipelines de traces ?** Si les métriques dérivées (carte des services, RED par span) étaient calculées *après* le tail sampling — par exemple par le `metrics_generator` de Tempo, qui ne voit que les traces stockées — elles seraient **biaisées** : trafic sous-compté (~10 % du volume normal conservé), erreurs et requêtes lentes massivement surreprésentées (conservées à 100 %). En les générant au Collector **avant** l'échantillonnage, la carte des services et ses taux restent exacts ; le sampling ne s'applique plus qu'au *stockage* des traces. Les chiffres de référence des alertes (§10.6) restent, eux, les métriques SDK (`http_server_request_duration_*`), jamais échantillonnées.
### 10.4 Le socle mono-serveur — `docker-compose.yml` (§7.1 exécutable)

Arborescence attendue :

```text
observability/
├── docker-compose.yml
├── otel-collector-config.yaml        (§10.3)
├── alloy-config.alloy                (logs Docker + récepteur Faro)
├── prometheus/
│   ├── prometheus.yml
│   └── rules/  (red.yml, rules-slo.yml — §10.6)
├── alertmanager/alertmanager.yml     (§10.6)
├── loki-config.yaml
├── tempo-config.yaml
├── blackbox.yml                      (§10.7)
└── grafana/provisioning/datasources/datasources.yaml   (§10.5)
```

```yaml
# docker-compose.yml — stack LGT(M) + Pyroscope, 100 % gratuite
# NB : pas de Mimir à cette échelle — Prometheus seul suffit sur un mono-serveur ;
# Mimir (rétention longue, multi-tenant) arrive avec Kubernetes (§7.2, §10.8).
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.116.1
    command: ["--config=/etc/otelcol/config.yaml"]
    environment: { DEPLOY_ENV: "prod" }
    volumes: ["./otel-collector-config.yaml:/etc/otelcol/config.yaml:ro"]
    ports: ["4317:4317", "4318:4318"]        # OTLP gRPC / HTTP (vos apps pointent ici)
    depends_on: [tempo, loki, prometheus]

  prometheus:
    image: prom/prometheus:v3.1.0
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=15d
      - --web.enable-remote-write-receiver     # reçoit les métriques du Collector
      - --enable-feature=exemplar-storage      # les exemplars = lien métrique → trace
    volumes: ["./prometheus:/etc/prometheus:ro", "prom-data:/prometheus"]
    ports: ["9090:9090"]

  loki:
    image: grafana/loki:3.3.2
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes: ["./loki-config.yaml:/etc/loki/config.yaml:ro", "loki-data:/loki"]
    ports: ["3100:3100"]

  tempo:
    image: grafana/tempo:2.7.0
    command: ["-config.file=/etc/tempo/config.yaml"]
    volumes: ["./tempo-config.yaml:/etc/tempo/config.yaml:ro", "tempo-data:/var/tempo"]
    ports: ["3200:3200"]

  pyroscope:                                   # profiling continu (§4.9) — config par défaut suffisante
    image: grafana/pyroscope:1.10.0
    volumes: ["pyro-data:/data"]
    ports: ["4040:4040"]                       # les SDK poussent ici (§10.1)

  grafana:
    image: grafana/grafana:11.4.0
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_FEATURE_TOGGLES_ENABLE: traceqlEditor
    volumes: ["./grafana/provisioning:/etc/grafana/provisioning:ro", "grafana-data:/var/lib/grafana"]
    ports: ["3000:3000"]

  alertmanager:
    image: prom/alertmanager:v0.27.0
    volumes: ["./alertmanager:/etc/alertmanager:ro"]
    ports: ["9093:9093"]

  alloy:                                       # 2 rôles : logs des conteneurs + récepteur Faro
    image: grafana/alloy:v1.6.1
    command: ["run", "/etc/alloy/config.alloy"]
    volumes:
      - ./alloy-config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports: ["12347:12347"]                     # endpoint Faro (§10.2)

  node-exporter:
    image: prom/node-exporter:v1.8.2
    pid: host
    volumes: ["/:/host:ro,rslave"]
    command: ["--path.rootfs=/host"]

  blackbox-exporter:
    image: prom/blackbox-exporter:v0.25.0
    volumes: ["./blackbox.yml:/etc/blackbox_exporter/config.yml:ro"]

  uptime-kuma:
    image: louislam/uptime-kuma:1
    volumes: ["kuma-data:/app/data"]
    ports: ["3001:3001"]

  # ---- GlitchTip (erreurs & crash, §4.6) — pile minimale ----
  glitchtip-db:
    image: postgres:16-alpine
    environment: { POSTGRES_PASSWORD: "${GT_DB_PASSWORD}", POSTGRES_DB: glitchtip }
    volumes: ["gt-db:/var/lib/postgresql/data"]
  glitchtip-redis:
    image: redis:7-alpine
  glitchtip:
    image: glitchtip/glitchtip:v4.2
    environment: &gt_env
      DATABASE_URL: postgres://postgres:${GT_DB_PASSWORD}@glitchtip-db:5432/glitchtip
      REDIS_URL: redis://glitchtip-redis:6379/0
      SECRET_KEY: ${GT_SECRET_KEY}
      GLITCHTIP_DOMAIN: https://glitchtip.example.com
    ports: ["8000:8000"]
    depends_on: [glitchtip-db, glitchtip-redis]
  glitchtip-worker:
    image: glitchtip/glitchtip:v4.2
    command: ./bin/run-celery-with-beat.sh
    environment: *gt_env
    depends_on: [glitchtip-db, glitchtip-redis]

volumes:
  prom-data: {}
  loki-data: {}
  tempo-data: {}
  pyro-data: {}
  grafana-data: {}
  kuma-data: {}
  gt-db: {}
```

Les trois configurations backend, minimales et commentées :

```yaml
# prometheus/prometheus.yml
global: { scrape_interval: 15s, evaluation_interval: 15s }
rule_files: ["rules/*.yml"]
alerting:
  alertmanagers: [{ static_configs: [{ targets: ["alertmanager:9093"] }] }]
scrape_configs:
  - job_name: prometheus
    static_configs: [{ targets: ["localhost:9090"] }]
  - job_name: node
    static_configs: [{ targets: ["node-exporter:9100"] }]
  - job_name: otel-collector           # santé du pipeline lui-même (écran 12)
    static_configs: [{ targets: ["otel-collector:8888"] }]
  - job_name: blackbox                 # sondes externes (§10.7)
    metrics_path: /probe
    params: { module: [http_2xx] }
    static_configs:
      - targets: ["https://app.example.com/health", "https://api.example.com/health"]
    relabel_configs:
      - { source_labels: [__address__], target_label: __param_target }
      - { source_labels: [__param_target], target_label: instance }
      - { target_label: __address__, replacement: "blackbox-exporter:9115" }
```

```yaml
# loki-config.yaml — mono-nœud, stockage local (S3/MinIO à l'échelle)
auth_enabled: false
server: { http_listen_port: 3100 }
common:
  path_prefix: /loki
  replication_factor: 1
  ring: { kvstore: { store: inmemory } }
  storage: { filesystem: { chunks_directory: /loki/chunks, rules_directory: /loki/rules } }
schema_config:
  configs:
    - from: "2026-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index: { prefix: index_, period: 24h }
limits_config:
  allow_structured_metadata: true      # requis pour l'ingestion OTLP (trace_id & co.)
  retention_period: 720h               # 30 jours (§7.3 : rétention par niveau)
```

```yaml
# tempo-config.yaml — mono-nœud (stockage pur des traces)
# NB : pas de metrics_generator ici — la carte des services est alimentée par les
# connecteurs du Collector (§10.3), calculés sur 100 % des traces AVANT échantillonnage.
# Activer en plus le metrics_generator de Tempo ferait double emploi (double comptage).
server: { http_listen_port: 3200 }
distributor:
  receivers: { otlp: { protocols: { grpc: {}, http: {} } } }
storage:
  trace:
    backend: local
    local: { path: /var/tempo/blocks }
    wal:   { path: /var/tempo/wal }
compactor:
  compaction: { block_retention: 360h }          # 15 jours de traces
```

```alloy
// alloy-config.alloy — logs des conteneurs → Loki, et récepteur Faro → Loki/Tempo
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}
loki.source.docker "apps" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.docker.containers.targets
  forward_to = [loki.write.default.receiver]
}
faro.receiver "web" {
  server {
    listen_address       = "0.0.0.0"
    listen_port          = 12347
    cors_allowed_origins = ["*"]
  }
  output {
    logs   = [loki.write.default.receiver]
    traces = [otelcol.exporter.otlp.tempo.input]
  }
}
loki.write "default" {
  endpoint { url = "http://loki:3100/loki/api/v1/push" }
}
otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
    tls { insecure = true }
  }
}
```

### 10.5 La corrélation — `datasources.yaml` (le fil rouge, en code)

C'est **le fichier le plus important de la section** : il câble la navigation métrique → trace → log → métrique promise depuis le §1.

```yaml
# grafana/provisioning/datasources/datasources.yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      httpMethod: POST
      # MÉTRIQUE → TRACE : chaque exemplar devient un bouton "voir la trace"
      exemplarTraceIdDestinations:
        - { name: trace_id, datasourceUid: tempo }

  - name: Loki
    uid: loki
    type: loki
    url: http://loki:3100
    jsonData:
      # LOG → TRACE : le trace_id du JSON (§10.1) devient un lien cliquable
      derivedFields:
        - name: TraceID
          matcherRegex: '"trace_id":"(\w+)"'
          url: '$${__value.raw}'          # $$ = échappement du provisioning Grafana
          datasourceUid: tempo
          urlDisplayLabel: "Voir la trace"

  - name: Tempo
    uid: tempo
    type: tempo
    url: http://tempo:3200
    jsonData:
      # TRACE → LOGS : bouton "logs de ce span" (fenêtre ±5 min, filtrée par trace_id)
      tracesToLogsV2:
        datasourceUid: loki
        spanStartTimeShift: "-5m"
        spanEndTimeShift: "5m"
        filterByTraceID: true
      # TRACE → CARTE DES SERVICES : nourrie par les connecteurs du Collector (§10.3)
      serviceMap: { datasourceUid: prometheus }
      nodeGraph: { enabled: true }
      lokiSearch: { datasourceUid: loki }
      # TRACE → PROFIL : bouton "profil de ce span" (requiert le SDK Pyroscope, §10.1)
      tracesToProfiles:
        datasourceUid: pyroscope
        profileTypeId: "process_cpu:cpu:nanoseconds:cpu:nanoseconds"

  - name: Pyroscope
    uid: pyroscope
    type: grafana-pyroscope-datasource
    url: http://pyroscope:4040
```

Pour les **dashboards**, même mécanique de provisioning (`provisioning/dashboards/`) ; démarrez avec les dashboards communautaires éprouvés — *Node Exporter Full* (ID **1860**) pour l'écran USE — puis construisez vos écrans RED (§5) avec les variables `$service`/`$env`, versionnés en JSON dans Git (dashboards-as-code).

### 10.6 Alertes & SLO — symptômes, pas causes

**Avant / après** — la règle du §5.3 en code :

```yaml
# ❌ AVANT — alerte sur une CAUSE : bruyante (le CPU peut monter sans impact),
# muette sur les vrais problèmes (une API down ne consomme pas de CPU)
- alert: HighCPU
  expr: 100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100 > 80
  for: 10m

# ✅ APRÈS — alerte sur le SYMPTÔME utilisateur (méthode RED)
```

```yaml
# prometheus/rules/red.yml — noms de métriques OTel ; adaptez aux vôtres
groups:
  - name: service-red
    rules:
      - alert: HighErrorRate
        expr: |
          sum by (service_name) (rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m]))
          /
          sum by (service_name) (rate(http_server_request_duration_seconds_count[5m])) > 0.05
        for: 5m
        labels: { severity: page }
        annotations:
          summary: "{{ $labels.service_name }} : {{ $value | humanizePercentage }} d'erreurs 5xx"
      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99, sum by (le, service_name)
            (rate(http_server_request_duration_seconds_bucket[5m]))) > 0.5
        for: 10m
        labels: { severity: ticket }
        annotations:
          summary: "{{ $labels.service_name }} : p99 > 500 ms"
```

**Le SLO en 15 lignes** — Sloth (§4.12) génère les règles multi-burn-rate et le dashboard :

```yaml
# slo/units-service.yml
version: prometheus/v1
service: units-service
slos:
  - name: requests-availability
    objective: 99.9                      # → budget d'erreur : 43 min / 30 jours
    sli:
      events:
        error_query: sum(rate(http_server_request_duration_seconds_count{service_name="units-service",http_response_status_code=~"5.."}[{{.window}}]))
        total_query: sum(rate(http_server_request_duration_seconds_count{service_name="units-service"}[{{.window}}]))
    alerting:
      name: UnitsServiceAvailability
      page_alert:   { labels: { severity: page } }     # burn rate rapide → réveil
      ticket_alert: { labels: { severity: ticket } }   # burn rate lent → ticket
```

```bash
sloth generate -i slo/units-service.yml -o prometheus/rules/rules-slo.yml
```

**Routage** — Alertmanager vers Slack ; en phase 4 (§8), ajoutez un *receiver* **webhook vers OneUptime** (intégration Alertmanager entrante) pour les gardes, escalades et appels :

```yaml
# alertmanager/alertmanager.yml
route:
  receiver: slack
  group_by: [alertname, service_name]
  routes:
    - { matchers: ['severity="page"'],   receiver: slack, repeat_interval: 1h }
    - { matchers: ['severity="ticket"'], receiver: slack, repeat_interval: 24h }
inhibit_rules:              # un "page" actif fait taire les "ticket" du même service
  - source_matchers: ['severity="page"']
    target_matchers: ['severity="ticket"']
    equal: [service_name]
receivers:
  - name: slack
    slack_configs:
      - api_url: ${SLACK_WEBHOOK_URL}
        channel: "#alertes"
        send_resolved: true
```

### 10.7 Sondes externes — Blackbox + k6

```yaml
# blackbox.yml — la vue "de l'extérieur" (§4.8) ; cibles déclarées dans prometheus.yml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http: { fail_if_not_ssl: true, preferred_ip_protocol: ip4 }
```

```javascript
// k6/smoke.js — parcours minimal, exécutable en CI (job planifié) ou à la main
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5, duration: '1m',
  thresholds: { http_req_duration: ['p(95)<500'], http_req_failed: ['rate<0.01'] },
};
export default function () {
  const res = http.get('https://app.example.com/health');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
```

**Uptime Kuma** se configure via son interface (http://localhost:3001) : sondes HTTP/TCP, notifications, et la **page de statut** publique — rien à coder.

### 10.8 Passage à l'échelle — Kubernetes (§7.2)

Les mêmes briques, installées par Helm ; les configurations ci-dessus se transposent en `values.yaml` :

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts

# Métriques + Alertmanager + Grafana + exporters K8s, en une commande
helm install kps prometheus-community/kube-prometheus-stack -n observability --create-namespace

# Logs, traces, profils — backends sur stockage objet (S3/GCS/MinIO)
helm install loki  grafana/loki  -n observability -f loki-values.yaml
helm install tempo grafana/tempo -n observability -f tempo-values.yaml
helm install pyro  grafana/pyroscope -n observability

# Collecte sur chaque nœud (logs pods + OTLP) — remplace le rôle d'Alloy du compose
helm install alloy grafana/alloy -n observability -f alloy-values.yaml
```

Le motif agent/gateway du §7.2 s'obtient en déployant l'**OTel Collector** deux fois (DaemonSet + Deployment via l'OpenTelemetry Operator) ; le tail-sampling **et** les connecteurs `spanmetrics`/`servicegraph` (§10.3) vivent dans la gateway — les connecteurs toujours en amont de l'échantillonnage.

### 10.9 Ordre de mise en route

| Étape | Action | Vérification |
|---|---|---|
| 1 | `docker compose up -d` | `docker compose ps` : tout *healthy* |
| 2 | Ouvrir Grafana (`:3000`) → Explore | Les 3 datasources répondent |
| 3 | Démarrer un service instrumenté (§10.1) et générer du trafic | Une trace apparaît dans Tempo |
| 4 | Depuis la trace, cliquer « logs de ce span » ; depuis un log, « Voir la trace » | **La corrélation fonctionne dans les deux sens** |
| 5 | Charger le dashboard 1860, créer l'écran RED du service (§5) | Exemplars visibles (points sur les courbes de latence) |
| 6 | `sloth generate` + recharger Prometheus ; couper le service 2 min | L'alerte burn-rate part vers Slack |
| 7 | Configurer Uptime Kuma + brancher les jobs CI (annotations, source maps — doc CI/CD §10) | Trait « deploy » visible sur les courbes |
| 8 | *(phase 4)* Activer le SDK Pyroscope (§10.1) et brancher Alertmanager sur OneUptime (§10.6) | Flame graph continu visible ; alerte test escaladée jusqu'au téléphone |

---

### Ports de référence (compose §10.4)

Grafana **3000** · Prometheus **9090** · Alertmanager **9093** · Loki **3100** · Tempo **3200** (OTLP interne 4317) · Pyroscope **4040** · Collector **4317/4318** · Alloy/Faro **12347** · Uptime Kuma **3001** · GlitchTip **8000**.

# Architecture d'un pipeline CI/CD universel

### Document d'architecture — standards de l'industrie, vue macro & micro, spécificités Angular / Django / microservices, et stack finale 100 % gratuite

> **Portée** : ce document décrit un pipeline CI/CD *universel* (applicable à tout logiciel), puis le **spécialise** pour votre architecture réelle : frontend **Angular** (monorepo Nx), backend **Django** en **microservices** (gRPC/protobuf), forge **GitLab**, déploiement **Ansible** vers **AKS**. Comme pour l'observabilité : architecture cible, comparatif technologique par brique (le meilleur / le moins cher / le plus cher / le plus utilisé — avec les pourquoi), les écrans utiles, et une **stack finale entièrement gratuite**.
>
> **Hypothèse** : « Ensile » est lu comme **Ansible** (présent dans vos deux pipelines). Me corriger si ce n'est pas le cas.
>
> **Note sur les prix** : tarifs catalogue indicatifs 2026, repères de comparaison uniquement.

---

## Sommaire

1. [Philosophie : CI, CD, et les métriques DORA](#1)
2. [Anatomie du pipeline universel : les étapes standard](#2)
3. [L'architecture globale : le schéma directeur](#3)
4. [Comparatif technologique, couche par couche](#4)
   - 4.1 Forge & moteur CI
   - 4.2 Runners (exécuteurs)
   - 4.3 Build & cache
   - 4.4 Qualité : lint, tests, couverture
   - 4.5 Chaîne DevSecOps (SAST, secrets, SCA, conteneurs, SBOM, DAST)
   - 4.6 Registre d'artefacts & d'images
   - 4.7 Livraison continue : push (Ansible) vs GitOps pull (Argo CD)
   - 4.8 Stratégies de déploiement & environnements
   - 4.9 Gestion des secrets
   - 4.10 Mises à jour de dépendances automatisées
   - 4.11 Versioning & releases
5. [Les écrans qui comptent (et pourquoi)](#5)
6. [La stack finale 100 % gratuite](#6)
7. [Spécifique à votre architecture : Angular, Django, microservices, Ansible/AKS](#7)
   - 7.1 Frontend Angular — les différences qui comptent
   - 7.2 Backend Django — les différences qui comptent
   - 7.3 Microservices — templates, contrats, protobuf
   - 7.4 Analyse de vos pipelines actuels : forces & axes d'amélioration
   - 7.5 Cible recommandée : Ansible + GitOps
   - 7.6 Corrections avant / après (code)
8. [Modèle de maturité : par où commencer](#8)
9. [Annexes : checklist, anti-patterns, glossaire](#9)
10. [Les pipelines à jour — versions finales complètes](#10)

---

<a name="1"></a>
## 1. Philosophie : CI, CD, et les métriques DORA

Trois termes souvent confondus, qui forment en réalité une **progression** :

- **CI — Intégration continue** : chaque commit déclenche automatiquement build + tests + analyses. Objectif : détecter les régressions en **minutes**, pas en semaines. La branche principale est *toujours* dans un état sain.
- **CD — Livraison continue (*Delivery*)** : chaque commit validé produit un **artefact déployable** (image Docker taguée, testée, scannée). Le déploiement en production reste un **choix humain** (bouton).
- **CD — Déploiement continu (*Deployment*)** : le déploiement en production est lui aussi **automatique** dès que le pipeline est vert. Réservé aux équipes matures (tests + observabilité + rollback solides).

```mermaid
flowchart LR
  A["Commit"] --> B["CI<br/>build + tests + scans<br/>automatiques"]
  B --> C["Livraison continue<br/>artefact prêt à déployer<br/>(déploiement = bouton)"]
  C --> D["Déploiement continu<br/>prod automatique<br/>si pipeline vert"]
```

### Vue MACRO vs vue MICRO

Le même fil rouge que pour l'observabilité s'applique au pipeline :

| | Vue **MACRO** | Vue **MICRO** |
|---|---|---|
| **Question** | « Livre-t-on vite et bien, globalement ? » | « Pourquoi *ce* pipeline / *ce* job a échoué ? » |
| **Public** | Direction, lead, platform team | Développeur devant sa MR |
| **Granularité** | Métriques DORA, taux de succès des pipelines, durée moyenne, vulnérabilités ouvertes | Un job, un log de build, un test rouge, un scan |
| **Horizon** | Tendances (semaines, trimestres) | L'instant du push |

### Les métriques DORA : le « SLO » du delivery

Les **4 métriques DORA** (issues de la recherche *DevOps Research & Assessment* de Google) sont le standard mondial pour mesurer la performance d'une chaîne de livraison — l'équivalent des SLO pour l'observabilité :

| Métrique | Question | Élite (repère) |
|---|---|---|
| **Deployment Frequency** | À quelle fréquence déploie-t-on en prod ? | À la demande (plusieurs fois/jour) |
| **Lead Time for Changes** | Combien de temps entre commit et prod ? | < 1 jour |
| **Change Failure Rate** | Quel % de déploiements cause un incident ? | < 15 % |
| **MTTR (Time to Restore)** | Combien de temps pour rétablir après incident ? | < 1 heure |

**Pourquoi c'est central** : ces 4 chiffres arbitrent *tous* les choix du pipeline. Un scan de sécurité qui ajoute 20 min ? Il dégrade le *Lead Time* — on le rend parallèle ou asynchrone. Pas de smoke test ? Le *Change Failure Rate* monte. C'est aussi le pont naturel avec la stack d'observabilité : le **MTTR se mesure avec Grafana**, et les **déploiements s'annotent** sur les dashboards (les « événements » du document précédent).

### Les principes non négociables

1. **Tout est code, tout est versionné** : le pipeline (`.gitlab-ci.yml`), l'infra (Ansible/Terraform), la config de déploiement. Un changement = un commit = une revue = un audit trail.
2. **Un artefact, immuable, promu** : on construit l'image **une seule fois**, on la teste/scanne, puis on **promeut le même binaire** de dev → staging → prod (jamais de rebuild par environnement). Vos pipelines appliquent déjà ce principe (tag `tmp-<sha>` → scan → smoke → promotion) : c'est exactement le standard.
3. **Échouer vite, échouer tôt** (*shift-left*) : les vérifications les moins chères (lint, secrets) tournent en premier ; les plus lourdes (E2E, DAST) en dernier ou en asynchrone.
4. **La sécurité est dans le pipeline, pas après** (*DevSecOps*) : chaque MR est scannée ; une vulnérabilité se découvre avant le merge, pas en audit annuel.
5. **Reproductibilité** : mêmes versions d'outils épinglées (vous épinglez Trivy/Gitleaks avec SHA256 vérifié — pratique exemplaire), caches déterministes, `npm ci` et non `npm install`.

---

<a name="2"></a>
## 2. Anatomie du pipeline universel : les étapes standard

Quel que soit le langage (Angular, Django ou autre), le pipeline de l'industrie suit la même **séquence logique en 8 étapes**. Frontend et backend ne diffèrent que par le *contenu* des étapes, jamais par leur *structure* — c'est ce qui rend le modèle universel et vos deux fichiers si semblables.

```mermaid
flowchart LR
  subgraph FAST["Rapide (secondes) — feedback immédiat"]
    A["1 · LINT<br/>style, qualité<br/>statique"]
    B["2 · BUILD<br/>compilation,<br/>artefacts"]
  end
  subgraph SEC["Parallèle — sécurité shift-left"]
    C["3 · SECURITY<br/>SAST · secrets · SCA"]
  end
  subgraph PROOF["Preuve (minutes)"]
    D["4 · TEST<br/>unitaires · intégration<br/>couverture · E2E"]
  end
  subgraph SHIP["Emballage"]
    E["5 · PACKAGE<br/>image Docker tmp<br/>scan conteneur · SBOM"]
    F["6 · VALIDATE<br/>smoke test<br/>de l'image"]
    G["7 · PROMOTE<br/>tags finaux<br/>vers le registre"]
  end
  H["8 · DEPLOY<br/>dev → staging → prod<br/>(CD)"]

  A --> B
  A --> C
  B --> D
  C -.->|"informatif"| E
  D --> E
  E --> F
  F --> G
  G --> H
```

**Le rôle de chaque étape** (et la logique de leur ordre) :

1. **Lint** — la vérification la moins chère : formatage, erreurs évidentes, typage statique. Échec en 30 s plutôt qu'en 15 min.
2. **Build** — prouver que ça compile et produire les artefacts (bundle Angular `dist/`, stubs protobuf générés côté Django).
3. **Security (en parallèle)** — SAST (code dangereux), secrets (clés commitées), SCA (dépendances vulnérables). Non bloquant au départ, durci avec la maturité — exactement votre choix `allow_failure: true` documenté [C3].
4. **Test** — unitaires (rapides, isolés), intégration (avec vraies dépendances — votre MSSQL/Redis en conteneurs isolés par job), seuil de couverture, E2E (Playwright) sur les parcours critiques.
5. **Package** — construire **une** image Docker taguée temporairement (`tmp-<sha>`), la scanner (CVE des couches), générer le **SBOM** (inventaire des composants — exigence croissante de conformité).
6. **Validate** — *smoke test* : l'image démarre-t-elle et répond-elle sur `/health` ? Le dernier filet avant publication.
7. **Promote** — re-taguer la même image avec les tags définitifs (`<sha>`, version). L'image publiée est *exactement* celle qui a été testée.
8. **Deploy** — la CD prend le relais : dev automatique, staging sur validation, prod sur approbation manuelle ou tag de version.

**La pyramide des tests** — la règle de répartition de l'effort :

```mermaid
flowchart TB
  E2E["E2E / UI (Playwright)<br/>peu nombreux · lents · fragiles<br/>parcours critiques uniquement"]
  INT["Intégration / API / contrats<br/>quelques dizaines · vraies dépendances"]
  UNIT["Unitaires (Jest · pytest)<br/>des centaines · millisecondes · la base"]
  E2E --- INT --- UNIT
```

Beaucoup d'unitaires (rapides, stables), moins d'intégration, très peu d'E2E. Inverser la pyramide = pipelines lents et *flaky* qui finissent ignorés.
---

<a name="3"></a>
## 3. L'architecture globale : le schéma directeur

Comme pour l'observabilité, toute chaîne CI/CD suit le même **pipeline en 5 couches**. C'est la colonne vertébrale du document.

```mermaid
flowchart LR
  subgraph SRC["1 · SOURCE & FORGE"]
    direction TB
    A1["Dépôts Git<br/>(code + pipeline as-code)"]
    A2["Merge Requests<br/>revue · approbations<br/>branches protégées"]
    A3["Templates CI partagés<br/>(include: — mutualisation<br/>entre microservices)"]
  end

  subgraph CI["2 · MOTEUR CI & RUNNERS"]
    direction TB
    C1["Orchestrateur<br/>(GitLab CI)"]
    C2["Runners auto-hébergés<br/>(shell / Docker / K8s)"]
    C3["Caches & artefacts<br/>(pip · npm · Nx · Trivy DB)"]
  end

  subgraph GATE["3 · PORTES QUALITÉ & SÉCURITÉ"]
    direction TB
    G1["Lint · typage · tests<br/>couverture ≥ seuil"]
    G2["SAST · secrets · SCA<br/>scan conteneur · SBOM"]
    G3["Smoke test image"]
  end

  subgraph REG["4 · REGISTRES"]
    direction TB
    R1["Registre d'images<br/>(GitLab Registry / Harbor)"]
    R2["Registre de paquets<br/>(npm · PyPI privés)"]
    R3["Artefacts & rapports<br/>(SBOM, couverture)"]
  end

  subgraph CD["5 · LIVRAISON (CD)"]
    direction TB
    D1["Moteur de déploiement<br/>Ansible (push)<br/>ou Argo CD (GitOps pull)"]
    D2["Environnements<br/>dev → staging → prod<br/>approbations · protections"]
    D3["Stratégies<br/>rolling · blue/green · canary<br/>+ rollback"]
  end

  OBS["OBSERVABILITÉ<br/>(document précédent)<br/>annotations de déploiement<br/>DORA · vérification post-deploy"]

  A1 --> C1
  A2 --> C1
  A3 --> C1
  C1 --> C2
  C2 --> G1
  G1 --> G2
  G2 --> G3
  G3 --> R1
  C2 --> R3
  R1 --> D1
  D1 --> D2
  D2 --> D3
  D3 --> OBS
  OBS -.->|"rollback si SLO dégradé"| D3
```

### Rôle de chaque couche

**Couche 1 — Source & forge.** Le dépôt Git est la **source unique de vérité** : code, pipeline (`.gitlab-ci.yml`), config de déploiement. La **Merge Request** est le point de contrôle humain (revue, approbations obligatoires, pipeline vert requis). En microservices, des **templates CI partagés** (via `include:`) évitent de dupliquer le pipeline dans chaque dépôt — un correctif de pipeline se fait *une fois* pour tous les services (voir §7.3).

**Couche 2 — Moteur CI & runners.** L'orchestrateur lit le pipeline-as-code et distribue les jobs à des **runners**. Le choix des runners (mutualisés cloud vs auto-hébergés) est le principal levier de **coût** et de **sécurité**. Les **caches** (pip, npm, Nx, bases Trivy) sont le principal levier de **vitesse**.

**Couche 3 — Portes qualité & sécurité.** Les *quality gates* : ce qui doit être vert pour merger/publier. C'est ici que se joue le compromis vitesse ↔ rigueur : chaque porte bloquante ajoute de la sûreté et du délai. La bonne pratique : commencer **informatif** (`allow_failure: true`), durcir progressivement.

**Couche 4 — Registres.** L'image Docker validée est l'**artefact de vérité** — immuable, taguée par SHA, accompagnée de son SBOM. Les environnements ne consomment *que* le registre, jamais un build local.

**Couche 5 — Livraison (CD).** Deux philosophies : **push** (le pipeline pousse vers l'environnement — votre modèle Ansible actuel) vs **pull/GitOps** (un agent dans le cluster tire l'état désiré depuis Git — Argo CD/Flux, devenu le standard Kubernetes). Comparées en §4.7. S'y ajoutent la **gestion des environnements** (protections, approbations) et les **stratégies** (rolling, blue/green, canary).

**La boucle avec l'observabilité.** Le pipeline **annote** chaque déploiement dans Grafana (les « événements » du document observabilité), et la vérification post-déploiement s'appuie sur les **SLO** : si le taux d'erreur monte après un deploy, rollback — automatisable en canary. **CI/CD et observabilité sont les deux moitiés d'une même boucle.**

### Principes d'architecture transverses

1. **Pipeline-as-code, mutualisé.** En microservices, le pipeline vit dans un dépôt de templates central, chaque service l'inclut en 5 lignes. Sinon : N copies divergentes impossibles à maintenir.
2. **Build once, promote everywhere.** Un seul build, promotion du même artefact — jamais de rebuild par environnement.
3. **Le runner est votre point de contrôle coût/sécurité.** Auto-hébergé = minutes illimitées gratuites + le code ne quitte pas votre infra.
4. **Isolation des jobs.** Réseaux Docker dédiés par job, nettoyage en `after_script` (votre pattern [P3]/[P4]) : pas d'interférence entre pipelines concurrents.
5. **Épinglage & intégrité.** Versions d'outils fixées, checksums vérifiés (votre pattern [P1]), `lock files` respectés : un pipeline doit donner le même résultat dans six mois.
6. **Le secret n'est jamais dans le code.** Variables CI protégées/masquées, et à terme un coffre (§4.9).
---

<a name="4"></a>
## 4. Comparatif technologique, couche par couche

> **Légende** — *Le plus utilisé* : adoption majoritaire. *Le meilleur* : le plus abouti, budget non limité. *Le moins cher* : meilleur rapport coût/valeur, gratuit inclus. *Le plus cher* : repère haut de gamme.

---

### 4.1 Forge & moteur CI — le cœur de la chaîne

**Rôle.** Héberger le code, les MR, et orchestrer les pipelines. Le choix structure tout le reste.

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **GitHub Actions** *(le plus utilisé)* | Standard de marché | Free : 2 000 min/mois (repos privés), illimité en public ; Team ~4 $/user ; Linux ~0,006 $/min au-delà | Première part de marché CI, écosystème de *actions* réutilisables inégalé, intégré à la plus grande communauté de code. Moins « plateforme DevOps complète » que GitLab (sécurité et gestion de projet en add-ons). |
| **GitLab CI** *(retenu — votre forge)* | **Le meilleur tout-en-un** | **Free : gratuit** (SaaS 400 min/mois **ou self-managed CE illimité**) ; Premium 29 $/user ; Ultimate sur devis (~60–99 $/user) — **runners auto-hébergés illimités et gratuits sur tous les plans** | La plateforme DevSecOps la plus intégrée : code + CI + registre + environnements + rapports sécurité **dans les MR** en un produit. Pipeline-as-code puissant (`include:`, `needs:`, templates) — idéal microservices. Avec **runners auto-hébergés, la CI est gratuite en minutes illimitées même en tier Free** : c'est votre situation actuelle. |
| **Jenkins** | Le vétéran self-host | **Gratuit** (OSS) ; coût réel = maintenance (~des heures/mois + serveurs) | Ultra-flexible (plugins infinis), toujours massivement présent en entreprise. Contrepartie : dette de plugins, config lourde (Groovy), sécurité à votre charge. À choisir seulement si déjà en place. |
| **CircleCI / Buildkite** | Spécialistes CI | CircleCI ~15 $/mois + crédits (~0,03–0,06 $/min) | Très bonnes performances, mais outil *CI seul* : il faut assembler forge + sécurité + CD à côté. |
| **Azure DevOps / Bitbucket** | Écosystèmes | Par user | Pertinents si déjà dans l'écosystème Microsoft/Atlassian. |
| **Harness / GitLab Ultimate** | **Le plus cher** (premium) | Ultimate sur devis ; Harness : plateforme entreprise sur devis | Gouvernance, conformité, DAST intégré, vérification IA des déploiements — le haut de gamme quand la conformité prime. |

**Le choix gratuit :** **GitLab** (votre forge actuelle) — soit **GitLab.com tier Free + runners auto-hébergés** (minutes illimitées gratuites), soit **GitLab CE self-managed** (tout gratuit, y compris > 5 utilisateurs privés). Les fonctions payantes (approbations multiples, dashboards sécurité Ultimate) sont **reconstituées gratuitement** par les briques ci-dessous : c'est tout l'objet de ce document.

---

### 4.2 Runners — où s'exécutent les jobs

**Rôle.** Exécuter les jobs. Détermine le coût (minutes), la vitesse (matériel, caches locaux) et la sécurité (où passe le code).

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **Runners auto-hébergés** *(retenu)* | **Le moins cher + le plus sûr** | **Gratuit** (vos machines ; une VM basique ~5–50 €/mois si louée) | Minutes **illimitées**, matériel au choix, caches chauds persistants (vos images MSSQL pré-tirées), le code reste chez vous. C'est votre modèle actuel (`tags: mirweb-vm-shell`). |
| Runners SaaS GitLab | Le plus simple | 400 min/mois gratuites puis 0,01 $/min | Zéro maintenance, élastique ; devient coûteux et lent (caches froids) à volume soutenu. |
| Runners GitHub hébergés | Repère marché | Linux 0,006 $/min ; macOS 0,048 $/min (8×) | Le piège classique : macOS/Windows multiplient la facture. |
| **Executor Docker / Kubernetes** *(cible)* | Le meilleur techniquement | **Gratuit** | Par rapport à votre executor *shell* : chaque job dans un conteneur propre → isolation totale, environnements reproductibles, plus de bricolage `DOCKER_CONFIG` WSL. L'executor **Kubernetes** sur AKS met les runners à l'échelle automatiquement. |

**Le choix gratuit :** **GitLab Runner auto-hébergé en executor Docker** (évolution recommandée de votre shell/WSL), puis **executor Kubernetes sur AKS** à l'échelle. Gratuit, illimité.

---

### 4.3 Build & cache — la vitesse du pipeline

**Rôle.** Compiler vite et de façon reproductible. Un pipeline lent est un pipeline contourné : viser **< 10 min** du push au feedback.

Les standards (tous gratuits) :

- **Docker BuildKit + cache de registre** — `--cache-from` d'une image de cache (votre pattern `CACHE_IMAGE`), builds **multi-stage** (une étape *builder* lourde, une image finale minimale), images de base **slim/alpine** épinglées par digest.
- **Caches par gestionnaire de paquets** — clé composite sur le *lock file* (votre pattern : `requirements.txt`, `package-lock.json` + `nx.json`) : cache invalidé exactement quand il le faut.
- **Cache de build incrémental** — **Nx** (votre monorepo Angular) ne rebuild/reteste que ce qui est **affecté** par le commit (`nx affected`) : sur un monorepo, c'est le levier n°1 (voir §7.1).
- **`npm ci` / `pip install` verrouillés** — jamais `npm install` en CI ; `--prefer-offline --ignore-scripts` (votre pattern) pour vitesse et sécurité (les scripts postinstall sont un vecteur d'attaque supply-chain).
- **Parallélisation par DAG** — `needs:` plutôt que des stages strictement séquentiels : la sécurité tourne en parallèle du build (votre architecture lint → build ∥ security → test).

**Repère payant :** les caches distribués managés (Nx Cloud, Depot, BuildJet — quelques dizaines à centaines de $/mois) accélèrent encore ; **Nx local + cache runner persistant** en donne l'essentiel gratuitement.

---

### 4.4 Qualité : lint, tests, couverture

**Rôle.** Prouver que le code fonctionne et rester lisible. Contenu par techno, structure universelle.

| Brique | Standard frontend (Angular) | Standard backend (Django/Python) | Gratuit ? |
|---|---|---|---|
| **Lint / format** | ESLint (+ config Nx), Prettier | ruff *(moderne, remplace flake8+isort+black en 1 outil ~100× plus rapide)* — ou votre trio actuel black/isort/flake8 | ✅ |
| **Typage statique** | TypeScript strict (dans le build) | mypy (votre choix) ou pyright | ✅ |
| **Tests unitaires** | Jest (votre choix) / Vitest | pytest + pytest-django *(standard de fait, supérieur à unittest)* | ✅ |
| **Tests d'intégration** | — (mock API, votre mock GraphQL) | pytest contre **vraies dépendances conteneurisées** (votre MSSQL/Redis par job) ; alternative moderne : **Testcontainers** | ✅ |
| **Couverture** | jest --coverage + seuil (votre 85 %) | coverage.py + seuil | ✅ |
| **E2E** | **Playwright** *(devenu le standard, devant Cypress : multi-navigateurs, parallélisme, image Docker officielle — votre choix)* | Playwright/API tests sur environnement éphémère | ✅ |
| **Qualité agrégée** | **SonarQube Community** (self-host gratuit) : dette technique, duplication, *quality gate* historisé — le complément naturel de vos rapports CodeQuality | idem | ✅ |

**Repères payants :** SonarQube Developer/Enterprise (par lignes de code, de ~500 à >20 000 €/an), Codecov (~10 $/user/mois), BrowserStack/Sauce Labs pour les fermes de navigateurs (~100–300 $/mois). **Le gratuit couvre l'essentiel** : SonarQube Community + Playwright + les rapports natifs GitLab.

---

### 4.5 Chaîne DevSecOps — la sécurité *dans* le pipeline

**Rôle.** Détecter les vulnérabilités **avant le merge**. C'est la couche où vos pipelines sont déjà les plus matures. Six familles de scans, chacune avec son outil gratuit de référence :

```mermaid
flowchart LR
  subgraph CODE["Sur le code source"]
    S1["SAST<br/>code dangereux<br/><b>Semgrep</b>"]
    S2["Secrets<br/>clés commitées<br/><b>Gitleaks</b>"]
    S3["SCA dépendances<br/>CVE des libs<br/><b>Trivy fs</b>"]
  end
  subgraph IMAGE["Sur l'image Docker"]
    S4["Scan conteneur<br/>CVE des couches<br/><b>Trivy image</b>"]
    S5["SBOM<br/>inventaire CycloneDX<br/><b>Trivy / Syft</b>"]
  end
  subgraph RUN["Sur l'app qui tourne"]
    S6["DAST<br/>attaque de l'app déployée<br/><b>OWASP ZAP</b>"]
  end
  CODE --> IMAGE --> RUN
```

| Famille | Outil gratuit retenu | Pourquoi lui | Repère payant (le plus cher) |
|---|---|---|---|
| **SAST** (analyse statique) | **Semgrep OSS** *(votre choix)* + **Bandit** (spécifique Python/Django) + règles `p/django`, `p/typescript` | Rapide, règles lisibles, format GitLab natif | Snyk Code, Checkmarx, GitLab Ultimate (souvent plusieurs dizaines de $/dev/mois ou devis) |
| **Secrets** | **Gitleaks** *(votre choix : fast scan par commit + full history planifié — pattern exemplaire)* | Standard OSS, baseline + allowlist | GitGuardian (par dev/mois) |
| **SCA** (dépendances) | **Trivy fs** *(votre choix)* + `npm audit` / **pip-audit** | Une seule base CVE pour fs *et* image, SBOM intégré | **Snyk Open Source** (~25–139 $/dev/mois) — le plus abouti en remédiation guidée |
| **Scan conteneur** | **Trivy image** *(votre choix)* — HIGH/CRITICAL, `--ignore-unfixed` | Standard OSS de fait, cache DB, rapport GitLab | Aqua / Prisma Cloud (entreprise, devis) |
| **SBOM** | **Trivy CycloneDX** *(votre choix)* ou Syft | Exigence croissante (conformité, clients grands comptes) | Plateformes supply-chain (devis) |
| **DAST** *(le chaînon manquant chez vous)* | **OWASP ZAP baseline scan** contre l'environnement de staging/review | Attaque réelle de l'app déployée (XSS, headers, auth) — complète le SAST | Burp Suite Enterprise, GitLab Ultimate DAST |
| **Signature d'images** *(cible)* | **Cosign** (Sigstore) — signer l'image à la promotion, vérifier au déploiement | Garantit que ce qui tourne = ce que le pipeline a produit | Notary entreprise |

**Politique de blocage recommandée** (votre logique actuelle, formalisée) : **secrets = bloquant** dès maintenant (un secret commité est une urgence) ; **CRITICAL avec correctif disponible = bloquant** sur l'image ; le reste **informatif** avec revue hebdomadaire, puis durcissement progressif. Un scan tout-bloquant dès le jour 1 → l'équipe le contourne.
---

### 4.6 Registre d'artefacts & d'images

**Rôle.** Stocker les images Docker validées et les paquets privés. La **source de vérité** des déploiements.

| Option | Catégorie | Prix indicatif 2026 | Pourquoi |
|---|---|---|---|
| **GitLab Container Registry** *(retenu — votre choix)* | Le plus intégré | **Gratuit** (inclus, y compris CE) | Zéro outil en plus, auth par `CI_JOB_TOKEN`, politiques de nettoyage des tags intégrées. |
| **Harbor** | Le meilleur self-host | **Gratuit** (OSS, CNCF graduated) | Registre entreprise : scan Trivy intégré, signature, réplication multi-sites, quotas, RBAC fin. À adopter si le registre devient central multi-équipes. |
| Registres cloud (ACR, ECR, GCR) | Managés | ~0,10 $/Go/mois + egress | Pertinents près du cluster (ACR ↔ AKS) ; coût faible mais réel. |
| **JFrog Artifactory** | **Le plus cher** (premium) | De ~150 $/mois à devis entreprise | La référence « tous formats » (Docker, npm, PyPI, Maven…) avec métadonnées avancées ; surdimensionné ici. |

**Le choix gratuit :** **GitLab Container Registry** (déjà en place) + **politique de nettoyage** des tags `tmp-*` (voir §7.4). Harbor en option d'évolution.

---

### 4.7 Livraison continue : push (Ansible) vs GitOps pull (Argo CD)

**Rôle.** Amener l'image validée jusqu'aux environnements. **Le choix d'architecture CD le plus structurant** — et celui où votre stack actuelle (Ansible déclenché par trigger) diffère du standard Kubernetes 2026.

```mermaid
flowchart TB
  subgraph PUSH["Modèle PUSH (votre actuel — Ansible)"]
    P1["Pipeline CI"] -->|"trigger + credentials<br/>du cluster dans la CI"| P2["Ansible playbook"] -->|"kubectl / helm apply"| P3["Cluster AKS"]
  end
  subgraph PULL["Modèle PULL / GitOps (standard K8s — Argo CD)"]
    G1["Pipeline CI"] -->|"met à jour le tag d'image<br/>dans un dépôt Git de config"| G2["Dépôt Git<br/>= état désiré"]
    G3["Agent Argo CD<br/>DANS le cluster"] -->|"observe"| G2
    G3 -->|"réconcilie en continu<br/>+ corrige la dérive"| G4["Cluster AKS"]
  end
```

| Critère | **Push (Ansible)** | **Pull / GitOps (Argo CD)** |
|---|---|---|
| Credentials du cluster | Dans la CI (surface d'attaque) | Ne quittent jamais le cluster |
| Dérive (modif manuelle `kubectl`) | Invisible jusqu'au prochain deploy | **Détectée et corrigée automatiquement** |
| Rollback | Rejouer un playbook | `git revert` — instantané, audité |
| Audit | Logs de pipeline | **Chaque état de la prod = un commit Git** |
| Multi-services / multi-env | Un trigger par service (votre modèle) | Un dépôt de config, N applications réconciliées |
| Cibles non-Kubernetes (VM, réseau) | **Excellent** — c'est le terrain d'Ansible | Non (K8s uniquement) |

| Option | Catégorie | Prix 2026 | Pourquoi |
|---|---|---|---|
| **Argo CD** *(retenu pour AKS)* | **Le plus utilisé (GitOps) + le meilleur** | **Gratuit** (OSS, CNCF graduated) | ~45–60 % du marché GitOps. UI temps réel (arbre des ressources, sync, drift, diff), multi-cluster, `ApplicationSet` pour décliner N microservices × M environnements. Le GitOps est devenu le mode de livraison K8s majoritaire (~2/3 des entreprises). |
| **Flux CD** | Le plus léger (GitOps) | **Gratuit** (OSS, CNCF graduated) | Sans UI, pur Kubernetes-native, très composable ; excellent mais adoption moindre (~11 %) et moins accessible aux équipes mixtes. |
| **Ansible** *(conservé pour le hors-K8s)* | Le standard config/VM | **Gratuit** (OSS) | Imbattable pour provisionner VM, réseau, bases, l'infra des runners… — mais en tant que *moteur de deploy K8s*, il réintroduit le push et ses limites. |
| **Helm / Kustomize** | Le format des manifestes | **Gratuit** | Pas des moteurs CD mais le *packaging* : Helm (charts paramétrés par env) ou Kustomize (overlays). Argo CD les consomme nativement. |
| **Harness / Spinnaker / Octopus** | **Le plus cher** (premium) | Devis / ~4 000 $+/an | Orchestration entreprise, vérification IA des déploiements, canary analysé automatiquement. |

**Le choix gratuit :** **Argo CD pour AKS** (GitOps pull) + **Ansible conservé** pour tout le hors-Kubernetes. La transition douce est détaillée en §7.5 — vos playbooks ne sont pas jetés, ils changent de rôle.

---

### 4.8 Stratégies de déploiement & environnements

**Rôle.** *Comment* la nouvelle version remplace l'ancienne, et avec quelles protections par environnement.

| Stratégie | Principe | Coût infra | Quand |
|---|---|---|---|
| **Rolling update** *(défaut K8s — retenu comme base)* | Remplacement progressif des pods, health checks entre chaque | Aucun surcoût | Le défaut sain pour la majorité des services |
| **Blue/Green** | Deux environnements complets ; bascule instantanée du trafic ; rollback = re-bascule | ×2 temporaire | Releases risquées, rollback en secondes exigé |
| **Canary** | 5 % → 25 % → 100 % du trafic, **validé par les métriques** (SLO du document observabilité) | Faible | Trafic élevé, maturité observabilité — c'est ici que les deux stacks fusionnent |
| **Feature flags** | Déployer ≠ activer : le code part en prod éteint, activation ciblée à chaud | Aucun | Découpler release technique et release produit — **Unleash** (OSS gratuit) est le standard self-host |

**Gestion des environnements (GitLab, gratuit) :** déclarer `environment:` sur chaque job de deploy (vous le faites) ; **environnements protégés** (seuls certains rôles déploient en prod) ; `when: manual` pour les approbations (votre choix) ; **review apps** — un environnement éphémère par MR, détruit au merge (`on_stop`) : le testeur voit la fonctionnalité *avant* le merge. Progression standard des déclencheurs : **dev = auto sur `develop`** ; **staging = auto ou manuel sur `main`** ; **prod = manuel sur tag `vX.Y.Z`** (vos exemples commentés suivent déjà ce schéma — il faut l'activer).

---

### 4.9 Gestion des secrets

**Rôle.** Fournir les credentials aux pipelines et aux applis **sans** qu'ils vivent dans le code ou en clair.

| Option | Catégorie | Prix 2026 | Pourquoi |
|---|---|---|---|
| **Variables CI GitLab (protected + masked)** *(votre actuel)* | Le minimum vital | **Gratuit** | Correct pour démarrer ; limites : pas de rotation, pas d'audit fin, visibles des mainteneurs. |
| **OpenBao** (fork OSS de Vault) / **Vault Community** | **Le meilleur gratuit** | **Gratuit** (self-host) | Coffre central : secrets dynamiques, rotation, audit, auth OIDC **depuis les jobs CI** (le job échange son identité contre un secret court-vécu — plus aucun secret stocké dans GitLab). |
| **External Secrets Operator + Azure Key Vault** *(cible AKS)* | Le plus intégré cloud | ESO **gratuit** ; Key Vault ~0,03 $/10k opérations | Les secrets vivent dans Key Vault, ESO les synchronise dans le cluster — compatible GitOps (aucun secret dans Git). |
| **SOPS + age** | Le plus GitOps-natif | **Gratuit** | Secrets chiffrés *dans* Git, déchiffrés au déploiement ; simple et auditable. |
| HashiCorp Vault Enterprise / CyberArk | **Le plus cher** | Devis (souvent 5–6 chiffres/an) | HSM, gouvernance, conformité réglementaire. |

**Le choix gratuit :** court terme, **variables GitLab protected/masked** (durcies : scoping par environnement) ; cible, **External Secrets Operator + Azure Key Vault** côté cluster (vous êtes sur Azure, coût négligeable) ou **OpenBao** si full self-host exigé.

---

### 4.10 Mises à jour de dépendances automatisées

**Rôle.** La majorité des vulnérabilités vient de dépendances **obsolètes**. Scanner (Trivy) détecte ; encore faut-il **mettre à jour** — automatiquement.

| Option | Catégorie | Prix 2026 | Pourquoi |
|---|---|---|---|
| **Renovate** *(retenu)* | **Le meilleur + gratuit** | **Gratuit** (OSS, self-host ou app hébergée) | Ouvre des MR de mise à jour (npm, pip, Docker base images, GitLab CI includes !) avec notes de version, regroupement, planification. Supporte GitLab nativement. Le complément indispensable de vos scans Trivy. |
| Dependabot | Le plus connu | Gratuit mais **GitHub only** | Non applicable sur GitLab. |
| Snyk (fix PRs) | Le plus cher | ~25–139 $/dev/mois | Remédiation guidée premium. |

**Le choix gratuit :** **Renovate** en job planifié GitLab — chaque lundi, des MR de mise à jour prêtes à revoir, testées par votre propre pipeline. Boucle vertueuse complète : Renovate propose → pipeline valide → Trivy confirme.

---

### 4.11 Versioning & releases

**Rôle.** Identifier ce qui tourne où, générer les changelogs, déclencher la prod.

Les standards (tous gratuits) :

- **Conventional Commits** (`feat:`, `fix:`, `feat!:`) — des messages de commit machine-lisibles, vérifiés en MR par **commitlint**.
- **SemVer** (`vX.Y.Z`) — le tag Git de version **est** le déclencheur du déploiement prod (votre règle commentée `deploy_production`).
- **semantic-release** ou **release-please** — calculent la version, génèrent le changelog et posent le tag automatiquement à partir des commits.
- **Tags d'images** : `<sha>` (traçabilité exacte — votre pratique), `vX.Y.Z` (releases). **Éviter de déployer `latest`** : non-reproductible, rollback impossible à raisonner (voir §7.4).
---

<a name="5"></a>
## 5. Les écrans qui comptent (et pourquoi)

Même logique que pour l'observabilité : une hiérarchie **macro → micro**, chaque écran répond à **une question**, pour **un public**, à **un moment** précis.

```mermaid
flowchart TB
  E0["NIVEAU 0 · MACRO<br/>Santé du delivery (DORA)<br/><i>« Livre-t-on vite et bien ? »</i>"]
  E1["NIVEAU 1 · PIPELINES<br/>succès · durée · flakiness<br/>par service"]
  E2["NIVEAU 2 · SÉCURITÉ<br/>vulnérabilités · secrets<br/>SBOM · licences"]
  E3["NIVEAU 3 · MICRO<br/>la MR · le job · le log<br/><i>« Pourquoi c'est rouge ? »</i>"]
  E4["ENVIRONNEMENTS<br/>quoi tourne où ?<br/>Argo CD / GitLab Environments"]
  E0 --> E1
  E0 --> E4
  E1 --> E2
  E1 --> E3
  E2 --> E3
  E4 --> E3
```

| # | Écran | Public | Quand | Vue | Contenu clé | Pourquoi il existe |
|---|---|---|---|---|---|---|
| 0 | **DORA / santé du delivery** (Grafana, alimenté par l'API GitLab) | Direction, leads | Hebdo / mensuel | MACRO | Fréquence de déploiement, lead time, change failure rate, MTTR — par équipe et tendance | Le « SLO du delivery » : arbitre les investissements pipeline (le lien direct avec le doc observabilité) |
| 1 | **Vue pipelines par service** (GitLab CI/CD Analytics + Grafana) | Platform team, leads | Quotidien | MACRO | Taux de succès, durée médiane/p95 par étape, jobs les plus lents, tests *flaky* récurrents | Un pipeline lent ou instable est contourné ; cet écran est le radar du « pipeline en tant que produit » |
| 2 | **La Merge Request** (GitLab natif) | **Le développeur** | À chaque MR | MICRO | Diff + revue, pipeline intégré, rapports **dans la MR** : code quality (le vôtre), couverture, SAST, secrets, dépendances, conteneur | **L'écran le plus important de toute la chaîne** : 90 % des décisions s'y prennent ; tous vos `reports:` GitLab existent pour alimenter cet écran |
| 3 | **Le job en échec** (GitLab natif) | Développeur | Pipeline rouge | MICRO | Log complet, artefacts (votre `test-output.log`, rapports JSON), retry, durée vs historique | Le « debug » du delivery — l'équivalent de la trace en observabilité |
| 4 | **Sécurité / vulnérabilités** (Grafana sur vos JSON Trivy/Semgrep/Gitleaks agrégés, ou DefectDojo OSS) | Sécurité, leads | Hebdo | MACRO | Vulnérabilités ouvertes par sévérité/service/âge, nouveaux secrets, tendance, SBOM consultable | Reconstitue **gratuitement** le « Security Dashboard » de GitLab Ultimate ; sans agrégation, vos rapports JSON dorment dans les artefacts |
| 5 | **Environnements — quoi tourne où** (GitLab Environments + **UI Argo CD**) | Tous | Continu + incident | MACRO→micro | Version (SHA/tag) déployée par env, état de sync, **dérive détectée**, historique, bouton rollback | Répond à la première question de tout incident : « qu'est-ce qui tourne en prod, et depuis quand ? » |
| 6 | **Registre & artefacts** (GitLab Registry) | Platform | Mensuel | MACRO | Images par service, tailles, âge des tags, résultat du dernier scan, espace consommé | Hygiène : tags `tmp-*` orphelins, images obèses, CVE sur images anciennes encore déployées |
| 7 | **Review app / environnement de MR** | Dev, QA, product | Pendant la revue | Client | L'application *elle-même*, déployée pour cette MR | Voir la fonctionnalité avant le merge — le testeur n'attend plus staging |
| 8 | **Annotations de déploiement** (Grafana — doc observabilité) | SRE, astreinte | Incident | Corrélation | Trait vertical « deploy v2.3.1 » superposé aux courbes de latence/erreurs | « Qu'est-ce qui a changé juste avant que ça casse ? » — la jonction physique des deux stacks |

### Le scénario type d'une livraison (le fil rouge)

```mermaid
flowchart LR
  MR["Écran 2 · MR<br/>revue + rapports verts"] --> PIPE["Pipeline<br/>build → scans → tests<br/>→ image promue"]
  PIPE --> ENV["Écran 5 · Argo CD<br/>sync auto sur dev<br/>tag → prod (manuel)"]
  ENV --> ANNOT["Écran 8 · Grafana<br/>annotation de deploy<br/>sur les dashboards SLO"]
  ANNOT -->|"SLO stable"| OK["Livraison validée<br/>DORA ✚"]
  ANNOT -->|"burn rate anormal"| RB["git revert<br/>rollback en minutes<br/>MTTR ↓"]
```

### Principes de conception

1. **La MR est le cockpit du développeur** : tout rapport qui n'apparaît pas dans la MR (via `reports:`) a une valeur divisée par dix.
2. **Un échec doit se lire en 30 secondes** : logs structurés par section, message d'erreur explicite en fin de job (vos `echo "ERROR: ..."` systématiques sont la bonne pratique).
3. **Mesurer le pipeline lui-même** : durée par étape historisée — le pipeline est un produit, avec ses SLO.
4. **Agréger la sécurité** : N rapports JSON par pipeline × M services = illisible sans un écran d'agrégation (écran 4).
5. **Toujours savoir « quoi tourne où »** : si répondre prend plus de 10 secondes, l'écran 5 manque.
---

<a name="6"></a>
## 6. La stack finale 100 % gratuite

Une chaîne complète, **entièrement gratuite et auto-hébergeable**, qui s'appuie sur ce que vous avez déjà (GitLab, runners auto-hébergés, Trivy/Semgrep/Gitleaks, Ansible) et la complète pour atteindre le standard de l'industrie.

```mermaid
flowchart TB
  subgraph FORGE["① FORGE (gratuit)"]
    F1["GitLab Free / CE<br/>code · MR · registre · environnements"]
    F2["Dépôt ci-templates<br/>(pipelines mutualisés microservices)"]
    F3["Renovate<br/>(MR de mise à jour auto)"]
  end

  subgraph RUN["② EXÉCUTION (gratuit)"]
    R1["GitLab Runners auto-hébergés<br/>executor Docker → Kubernetes (AKS)<br/>minutes illimitées"]
  end

  subgraph QUAL["③ QUALITÉ (gratuit)"]
    Q1["ESLint · ruff · mypy<br/>Jest · pytest · Playwright<br/>seuils de couverture"]
    Q2["SonarQube Community<br/>(dette · quality gate)"]
  end

  subgraph SEC["④ DEVSECOPS (gratuit)"]
    S1["Semgrep + Bandit (SAST)<br/>Gitleaks (secrets)<br/>Trivy (SCA + image + SBOM)"]
    S2["OWASP ZAP (DAST sur staging)<br/>Cosign (signature d'images)"]
    S3["DefectDojo / Grafana<br/>(agrégation vulnérabilités)"]
  end

  subgraph ART["⑤ ARTEFACTS (gratuit)"]
    A1["GitLab Container Registry<br/>images immuables <sha> + vX.Y.Z<br/>+ SBOM attaché"]
  end

  subgraph CD["⑥ LIVRAISON (gratuit)"]
    C1["Argo CD (GitOps pull)<br/>dépôt de config = état désiré<br/>AKS · drift · rollback git revert"]
    C2["Ansible<br/>VM · infra · runners · hors-K8s"]
    C3["Unleash (feature flags)<br/>External Secrets Op. + Key Vault"]
  end

  OBS["⑦ OBSERVABILITÉ (doc précédent)<br/>annotations de deploy · DORA dans Grafana<br/>SLO = juge de paix du canary"]

  F1 --> R1
  F2 --> F1
  F3 --> F1
  R1 --> Q1
  Q1 --> Q2
  R1 --> S1
  S1 --> A1
  Q1 --> A1
  A1 --> C1
  S2 -.->|"scanne staging"| C1
  C2 -.->|"provisionne"| R1
  C1 --> OBS
  OBS -.->|"rollback si SLO KO"| C1
```

### Composant par composant — et pourquoi

| Rôle | Outil gratuit retenu | Pourquoi lui | Équivalent payant remplacé |
|---|---|---|---|
| **Forge + CI** | **GitLab Free/CE + runners auto-hébergés** | Déjà en place ; runners self-host = minutes illimitées gratuites | GitLab Premium/Ultimate, GitHub Team |
| **Runners** | **GitLab Runner (Docker → K8s executor)** | Isolation propre, reproductible, scalable sur AKS | Runners SaaS à la minute |
| **Templates pipeline** | **Dépôt `ci-templates` + `include:`** | Un pipeline maintenu une fois pour N microservices | — (pratique, pas un produit) |
| **Lint/format Python** | **ruff** (+ mypy) | Remplace flake8+isort+black, ~100× plus rapide | SonarQube payant |
| **Tests** | **Jest · pytest · Playwright** | Standards de fait de vos deux stacks | Fermes de tests cloud |
| **Qualité agrégée** | **SonarQube Community** | Quality gate historisé, gratuit self-host | SonarQube Developer+ |
| **SAST** | **Semgrep OSS + Bandit** | Vos choix + spécialisation Django | Snyk Code, Checkmarx |
| **Secrets** | **Gitleaks** (fast + full history) | Votre pattern, exemplaire | GitGuardian |
| **SCA + conteneur + SBOM** | **Trivy** (+ pip-audit, npm audit) | Un outil, trois scans, déjà maîtrisé | Snyk, Aqua |
| **DAST** | **OWASP ZAP baseline** | Le chaînon manquant, gratuit | Burp Enterprise, GitLab Ultimate |
| **Signature** | **Cosign** | Intégrité build → prod | Notary entreprise |
| **Agrégation sécu** | **DefectDojo** (ou Grafana sur vos JSON) | Reconstruit le dashboard Ultimate gratuitement | GitLab Ultimate Security Dashboard |
| **MAJ dépendances** | **Renovate** | MR automatiques npm/pip/Docker, natif GitLab | Snyk fix PRs |
| **Registre** | **GitLab Registry** (+ Harbor en option) | Inclus, intégré | Artifactory |
| **CD Kubernetes** | **Argo CD** | Standard GitOps (~moitié du marché), UI, drift, rollback = git revert | Harness, Codefresh |
| **CD hors-K8s / infra** | **Ansible** (conservé) | Son vrai terrain : VM, runners, provisioning | — |
| **Feature flags** | **Unleash** | Déployer ≠ activer, self-host | LaunchDarkly (~10–20 $/siège) |
| **Secrets runtime** | **External Secrets Operator + Azure Key Vault** (ou OpenBao) | GitOps-compatible, coût négligeable | Vault Enterprise |
| **Versioning/release** | **Conventional Commits + semantic-release** | Changelog et tags automatiques | — |
| **Métriques DORA** | **Grafana + API GitLab** (ou Apache DevLake OSS) | Le macro-écran du delivery | GitLab Ultimate DORA, LinearB |

> **Le message clé** : GitLab Ultimate (sur devis, typiquement 60–99 $/user/mois) vend principalement *l'intégration* de ces fonctions (scans natifs, dashboards sécurité, DORA). **Chaque fonction se reconstruit gratuitement** avec les briques OSS ci-dessus — au prix d'un peu d'assemblage, que vos pipelines ont déjà largement réalisé.
---

<a name="7"></a>
## 7. Spécifique à votre architecture : Angular, Django, microservices, Ansible/AKS

Le squelette (les 8 étapes du §2) est identique partout — vos deux fichiers le prouvent. Voici ce qui **diffère réellement**, puis l'analyse de l'existant.

### 7.1 Frontend Angular (monorepo Nx) — les différences qui comptent

Le frontend a une particularité : **l'artefact final est statique** (bundle JS/CSS servi au navigateur). Les conséquences :

| Spécificité | Pratique standard | Outil gratuit |
|---|---|---|
| **Le poids du bundle est une feature** | *Budgets* de taille dans `angular.json` (échec du build si dépassement) + rapport de diff de taille en MR | Angular builder natif, `source-map-explorer` |
| **La perf perçue se teste en CI** | **Lighthouse CI** sur le build : scores perf/accessibilité/SEO avec seuils, commentés en MR | Lighthouse CI (gratuit) |
| **Monorepo Nx : ne tester que l'affecté** | `nx affected -t lint,test,build` avec `--base` sur la cible de MR : un commit sur une lib ne rebuild pas tout | Nx (déjà en place) — **le levier de vitesse n°1 chez vous** |
| **Les erreurs prod doivent être lisibles** | Upload des **source maps** vers GlitchTip/Sentry à la promotion (lien avec le doc observabilité : stack traces déminifiées) | sentry-cli (gratuit) |
| **L'image finale est un serveur statique** | Multi-stage : `node` (build) → `nginx-alpine` (run) ; l'image ne contient **ni** node_modules **ni** sources | Docker (déjà) |
| **La config varie par env sans rebuild** | Config injectée au runtime (env.js généré au démarrage du conteneur), pas au build — sinon on viole « build once, promote everywhere » | Pattern, pas un outil |
| **E2E avec backend simulé** | Votre pattern mock GraphQL local + login réel est le bon équilibre ; les E2E full-stack vivent plutôt en staging | Playwright (déjà) |

### 7.2 Backend Django — les différences qui comptent

Le backend a deux particularités : il **possède un état** (la base de données) et il **expose des contrats** (API/gRPC).

| Spécificité | Pratique standard | Outil gratuit |
|---|---|---|
| **Les migrations sont le risque n°1** | Job dédié : `python manage.py makemigrations --check --dry-run` (échec si migration manquante) + `migrate` **testé contre une vraie base** en CI ; en CD, migrations exécutées *avant* le rollout (initContainer/Job K8s), **rétro-compatibles** (pattern *expand/contract* : jamais de suppression de colonne dans la même release que le code qui cesse de l'utiliser) | Django natif |
| **SAST spécialisé Python** | **Bandit** (injections, `eval`, secrets) + règles Semgrep `p/django` en plus de `p/python` (vous l'avez en schedule — à passer sur chaque MR) | Bandit, Semgrep |
| **Config Django de prod vérifiée** | `manage.py check --deploy --fail-level WARNING` en CI : DEBUG, ALLOWED_HOSTS, cookies sécurisés… | Django natif |
| **Dépendances Python auditées** | **pip-audit** en complément de Trivy (bases CVE différentes) | pip-audit |
| **Tests d'intégration réalistes** | Vos conteneurs MSSQL/Redis isolés par job = la bonne pratique ; pytest-django + fixtures | Déjà en place |
| **Le healthcheck est un contrat** | `/health/` (liveness — le process vit) **et** `/ready/` (readiness — DB/Redis joignables) distincts : K8s les utilise différemment pendant les rollouts | django-health-check |
| **gRPC : les stubs sont un artefact** | Votre job `build_microservice` compile les protos — voir §7.3 pour la version microservices-propre | grpcio-tools (déjà) |

### 7.3 Microservices — les trois patterns qui changent tout

**① Un pipeline mutualisé, pas N copies.** Vos deux fichiers partagent ~70 % de logique (workflow, scans, package, promotion). Le standard : un dépôt **`ci-templates`**, versionné, que chaque service inclut :

```yaml
# .gitlab-ci.yml d'un microservice Django — c'est TOUT le fichier
include:
  - project: 'mon-groupe/ci-templates'
    ref: v2.4.0                    # les templates sont versionnés — un service peut rester sur v2.3
    file: '/pipelines/django-service.yml'

variables:
  COVERAGE_THRESHOLD: "85"
  SERVICE_PORT: "8000"
```

Un correctif de pipeline (nouvelle version de Trivy, nouveau scan) = **une MR dans un dépôt**, propagée partout. Renovate peut même mettre à jour le `ref:` automatiquement. C'est la différence entre 5 microservices et 50.

**② Les contrats entre services se testent en CI.** En microservices, la régression la plus dangereuse n'est pas *dans* un service mais **entre** deux services (le producteur change son API, le consommateur casse en prod). Deux réponses gratuites :

- **Protobuf/gRPC (votre cas)** : centraliser les `.proto` dans un dépôt **`protos`** unique (aujourd'hui chaque service compile les siens → risque de divergence silencieuse), avec **buf** (gratuit) en CI : `buf lint` + **`buf breaking`** — le pipeline **échoue si un changement de proto casse la compatibilité**. Les stubs générés sont publiés en paquet versionné que les services consomment.
- **API REST/GraphQL** : **contract testing** avec **Pact** (gratuit) — le consommateur publie ses attentes, le producteur les rejoue dans SON pipeline : impossible de merger un breaking change sans le savoir.

```mermaid
flowchart LR
  subgraph PROTOS["Dépôt protos (source de vérité)"]
    P["*.proto<br/>buf lint + buf breaking"]
  end
  P -->|"stubs versionnés v1.8.0"| S1["units-service"]
  P -->|"stubs versionnés v1.8.0"| S2["orders-service"]
  P -->|"stubs versionnés v1.8.0"| FE["units-webapp (types)"]
```

**③ Un déploiement d'ensemble, pas N triggers.** Chaque service déclenche aujourd'hui son déploiement isolément (trigger Ansible). À N services, on perd la vue d'ensemble (« quelles versions sont censées tourner ensemble ? »). Le pattern GitOps : un **dépôt de configuration** unique décrit l'état désiré de *tous* les services par environnement — voir §7.5.

### 7.4 Analyse de vos pipelines actuels : forces & axes d'amélioration

**Ce qui est déjà au niveau des standards (à conserver tel quel) :**

- ✅ **Build once, promote** : `tmp-<sha>` → scan → smoke → promotion. Exactement le pattern de référence.
- ✅ **Chaîne DevSecOps complète** : SAST + secrets (fast **et** full history planifié — rarement vu) + SCA + scan conteneur + **SBOM CycloneDX**. Beaucoup d'équipes payantes n'en sont pas là.
- ✅ **Supply-chain** : versions épinglées + **SHA256 vérifiés** des outils, `--ignore-scripts` npm.
- ✅ **Ingénierie CI solide** : gestion explicite des exit codes (`set +e` documenté), isolation réseau par job, nettoyage `after_script`, caches à clés composites, `interruptible`, rapports natifs GitLab dans les MR.
- ✅ **needs: assaini** [C3] : les scans informatifs ne bloquent plus les jobs aval.

**Les axes d'amélioration, par priorité :**

| # | Constat | Risque | Correctif (gratuit) |
|---|---|---|---|
| 1 | **`environment: production/...` déclenché depuis `develop`** (backend) | Confusion d'audit : ce qui part de develop n'est pas la prod ; pas de chaîne dev→staging→prod réelle | Activer la progression de vos jobs commentés : develop→dev (auto), main→staging, **tag `vX.Y.Z`→prod (manuel, environnement protégé)** |
| 2 | **Déploiement consommant implicitement `latest`** possible côté Ansible | Non-reproductible ; rollback impossible à raisonner | Déployer **uniquement par SHA ou tag SemVer** (vous passez déjà `APP_IMAGE_TAG=$CI_COMMIT_SHA` — supprimer `latest` des chemins de deploy ; le garder éventuellement pour usage humain) |
| 3 | **Pas de politique de nettoyage du registre** (`tmp-*` s'accumulent) | Stockage qui gonfle, bruit | GitLab *cleanup policies* : purge `tmp-*` > 7 jours, garder N dernières versions |
| 4 | **Migrations Django absentes du pipeline** | Le risque n°1 backend non couvert | Jobs `makemigrations --check` + `migrate` sur base CI (§7.2) |
| 5 | **Pas de DAST** | Les vulnérabilités d'exécution (headers, auth, XSS réfléchi) passent | Job **ZAP baseline** hebdomadaire contre staging |
| 6 | **Pas de mise à jour automatique des dépendances** | Trivy signale, personne ne corrige → dette CVE | **Renovate** planifié |
| 7 | **Coverage `allow_failure: true` + seuil en dur 85 côté front** | Le seuil n'engage à rien ; incohérence avec le backend paramétré | Variable `COVERAGE_THRESHOLD` partagée via template ; passer bloquant une fois stabilisé |
| 8 | **Executor shell sur WSL** (d'où les contournements `docker-credential-desktop.exe`) | Fragilité, non-reproductibilité, jobs qui se partagent l'hôte | Migrer vers **executor Docker** sur une VM Linux dédiée (ou K8s sur AKS) — les workarounds disparaissent |
| 9 | **Duplication front/back** (~70 % commun) | Divergence inévitable à N services | Dépôt **`ci-templates`** (§7.3) |
| 10 | **Pas de review apps** | La QA attend staging | `environment: review/$CI_MERGE_REQUEST_IID` + `on_stop` sur AKS |
| 11 | **Pas d'annotation des déploiements dans Grafana** | Les deux stacks (CI/CD ↔ observabilité) restent disjointes | Un `curl` vers l'API annotations Grafana dans le job de deploy |
| 12 | **E2E dépendant d'un backend d'auth distant** | Flakiness structurel (réseau, dispo du backend) | Mock de l'auth aussi, ou compte de test sur un service d'auth conteneurisé en CI |

### 7.5 Cible recommandée : Ansible + GitOps, chacun à sa place

Vous n'avez **pas** à choisir entre Ansible et GitOps — le standard est de les **spécialiser** :

```mermaid
flowchart TB
  subgraph CI["Pipeline CI (par microservice)"]
    A["build → scans → tests<br/>→ image :sha promue"]
  end
  subgraph CFG["Dépôt gitops-config (nouveau)"]
    B["environments/<br/>  dev/    → units-service: sha-abc<br/>  staging/→ units-service: v1.8.0<br/>  prod/   → units-service: v1.7.2"]
  end
  subgraph AKS["Cluster AKS"]
    C["Argo CD<br/>réconcilie · détecte la dérive<br/>UI 'quoi tourne où'"]
    D["Workloads"]
  end
  subgraph ANS["Ansible (conservé)"]
    E["Provisionne : VM des runners,<br/>bases, réseau, bootstrap AKS,<br/>installation d'Argo CD lui-même"]
  end

  A -->|"le job deploy fait un simple<br/>commit du nouveau tag<br/>(dev : auto · prod : MR approuvée)"| B
  C -->|observe| B
  C --> D
  E -.-> AKS
  E -.-> A
```

**La transition, en douceur et gratuite :**

1. **Étape 1** — créer le dépôt `gitops-config` (manifests Helm/Kustomize par service × environnement). Vos playbooks Ansible actuels contiennent déjà cette information : c'est une extraction, pas une réécriture.
2. **Étape 2** — installer Argo CD sur AKS (via Ansible, justement) ; brancher `dev` en sync automatique. Ansible continue de gérer staging/prod : les deux coexistent sans risque.
3. **Étape 3** — remplacer le `trigger_ansible_deploy` par un job qui **commit le nouveau tag d'image** dans `gitops-config` (dev : commit direct ; prod : MR avec approbation — la revue de code devient la revue de déploiement).
4. **Étape 4** — basculer staging puis prod ; **Ansible garde définitivement** l'infra (runners, VM, bootstrap cluster, tout le hors-K8s — son vrai terrain).

**Ce que vous y gagnez** : rollback = `git revert` (MTTR ↓), audit = historique Git de la prod, dérive détectée/corrigée, credentials du cluster sortis de la CI, l'écran « quoi tourne où » (UI Argo CD) gratuit, et un déploiement d'*ensemble* cohérent pour vos microservices.
---

### 7.6 Corrections avant / après (code)

Chaque correctif reprend le numéro du tableau §7.4. Les extraits « avant » viennent de vos fichiers ; les « après » sont directement utilisables.

---

#### #1 — Chaîne d'environnements réelle (dev → staging → prod)

**Avant** *(backend : un déploiement depuis `develop` étiqueté production)* :

```yaml
trigger_ansible_deploy:
  stage: deploy
  rules:
    - if: '$CI_COMMIT_BRANCH == "develop"'
      when: manual
  environment:
    name: production/${CI_COMMIT_REF_SLUG}   # ⚠ develop ≠ production
```

**Après** *(trois jobs, un template commun ; prod uniquement sur tag SemVer, environnement protégé)* :

```yaml
.deploy_base:
  stage: deploy
  interruptible: false
  needs: ['promote_image']

deploy_dev:
  extends: .deploy_base
  environment: { name: dev, url: 'https://dev.example.com' }
  rules:
    - if: '$CI_COMMIT_BRANCH == "develop"'
      when: on_success          # dev : automatique

deploy_staging:
  extends: .deploy_base
  environment: { name: staging, url: 'https://staging.example.com' }
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
      when: on_success          # staging : automatique sur main

deploy_production:
  extends: .deploy_base
  environment: { name: production, url: 'https://app.example.com' }
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/'
      when: manual              # prod : bouton, sur tag vX.Y.Z uniquement
  allow_failure: false
```

> À compléter côté GitLab : **Settings → CI/CD → Protected environments** → `production` réservé aux Maintainers, et **Protected tags** sur `v*`.

---

#### #2 — Déployer par SHA/tag, jamais `latest`

**Avant** *(promotion : `latest` publié au même rang que le SHA → un deploy peut le consommer)* :

```yaml
- docker tag "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:latest"
- docker push "$IMAGE_NAME:latest"
```

**Après** *(tags immuables ; le tag SemVer n'est posé que sur un tag Git ; `latest` supprimé des chemins de déploiement — seul le cache de build garde `latest`, ce qui est son rôle)* :

```yaml
promote_image:
  script:
    - docker pull "$IMAGE_NAME:$IMAGE_TAG_TMP"
    - docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:$CI_COMMIT_SHA"
    - docker push "$IMAGE_NAME:$CI_COMMIT_SHA"
    - |
      if [ -n "$CI_COMMIT_TAG" ]; then
        docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:$CI_COMMIT_TAG"
        docker push "$IMAGE_NAME:$CI_COMMIT_TAG"      # v1.8.0 — releases humaines
      fi
    - docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$CACHE_IMAGE:latest"
    - docker push "$CACHE_IMAGE:latest"                # cache de build uniquement
```

Et côté déploiement : **toujours** `APP_IMAGE=$IMAGE_NAME:$CI_COMMIT_SHA` (jamais de tag flottant).

---

#### #3 — Nettoyage du registre (`tmp-*` orphelins)

**Avant** : aucune politique — chaque pipeline laisse un `tmp-<sha>`.

**Après** *(politique GitLab, à poser une fois par projet — UI : Settings → Packages & registries → Cleanup policies, ou API)* :

```bash
curl --request PUT --header "PRIVATE-TOKEN: $ADMIN_TOKEN" \
  --data 'container_expiration_policy_attributes[enabled]=true' \
  --data 'container_expiration_policy_attributes[cadence]=7d' \
  --data 'container_expiration_policy_attributes[keep_n]=10' \
  --data 'container_expiration_policy_attributes[older_than]=7d' \
  --data 'container_expiration_policy_attributes[name_regex_delete]=^tmp-.*' \
  --data 'container_expiration_policy_attributes[name_regex_keep]=^(v\d+.*|[0-9a-f]{40})$' \
  "https://gitlab.com/api/v4/projects/$PROJECT_ID"
```

---

#### #4 — Migrations Django dans le pipeline (le risque n°1 couvert)

**Avant** : aucun job — une migration oubliée ou destructrice part en prod sans filet.

**Après** *(nouveau job en stage `lint` : rapide, échoue tôt)* :

```yaml
django_checks:
  extends: .python_job
  stage: lint
  variables:
    SECRET_KEY: "ci-only"
    DJANGO_SETTINGS_MODULE: "units_project.settings"
  script:
    # 1. Migration manquante = échec (le modèle a changé sans makemigrations)
    - python manage.py makemigrations --check --dry-run
    # 2. Config de prod dangereuse = échec (DEBUG, ALLOWED_HOSTS, cookies…)
    - python manage.py check --deploy --fail-level WARNING
  allow_failure: false
```

Et dans le job `test` (qui a déjà MSSQL) : `python manage.py migrate --no-input` **avant** pytest — chaque MR prouve que ses migrations s'appliquent sur une vraie base.

---

#### #5 — DAST : OWASP ZAP contre staging

**Avant** : rien après le déploiement — SAST et scans d'image ne testent jamais l'app *qui tourne*.

**Après** *(nouveau job planifié — hebdomadaire, non bloquant au départ)* :

```yaml
dast_zap_baseline:
  stage: deploy
  image:
    name: ghcr.io/zaproxy/zaproxy:stable
    entrypoint: [""]
  variables:
    TARGET_URL: "https://staging.example.com"
  script:
    - mkdir -p /zap/wrk
    - zap-baseline.py -t "$TARGET_URL" -J zap-report.json -r zap-report.html || true
    - cp /zap/wrk/zap-report.* . 2>/dev/null || true
  artifacts:
    when: always
    paths: [zap-report.json, zap-report.html]
    expire_in: 1 month
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
  allow_failure: true
```

---

#### #6 — Renovate : les dépendances se mettent à jour toutes seules

**Avant** : Trivy signale les CVE… et personne n'ouvre la MR de mise à jour.

**Après** — deux fichiers. Un projet GitLab dédié `renovate-runner` avec ce pipeline planifié (lundi 6 h) :

```yaml
# .gitlab-ci.yml du projet renovate-runner
renovate:
  image: renovate/renovate:latest
  variables:
    RENOVATE_PLATFORM: gitlab
    RENOVATE_ENDPOINT: "$CI_API_V4_URL"
    RENOVATE_TOKEN: "$RENOVATE_PAT"          # PAT scope api (Masked)
    RENOVATE_AUTODISCOVER: "true"
    RENOVATE_AUTODISCOVER_FILTER: "mon-groupe/**"
  script: [renovate]
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
```

Et à la racine de chaque service, `renovate.json` :

```json
{
  "extends": ["config:recommended", ":dependencyDashboard"],
  "packageRules": [
    { "matchUpdateTypes": ["patch"], "groupName": "patchs hebdo", "automerge": false },
    { "matchDatasources": ["docker"], "pinDigests": true }
  ],
  "vulnerabilityAlerts": { "labels": ["security"], "prPriority": 10 }
}
```

---

#### #7 — Seuil de couverture : une variable, deux stacks

**Avant** *(frontend : 85 en dur ; backend : variable — incohérent)* :

```yaml
if [ "$COVERAGE_INT" -lt 85 ]; then
  echo "❌ Coverage below threshold (85%)"
```

**Après** *(même variable partout, surchargée au besoin par service)* :

```yaml
variables:
  COVERAGE_THRESHOLD: "85"
# ...
    - |
      if [ "$COVERAGE_INT" -lt "$COVERAGE_THRESHOLD" ]; then
        echo "ERROR: coverage ${COVERAGE_INT}% < seuil ${COVERAGE_THRESHOLD}%"
        exit 1
      fi
```

Et une fois stabilisé : `allow_failure: false` — un seuil non bloquant n'est pas un seuil.

---

#### #8 — Executor Docker : la moitié du pipeline disparaît

**Avant** *(executor shell sur WSL → contournements en cascade dans chaque job)* :

```toml
# config.toml du runner
[[runners]]
  executor = "shell"
```

```yaml
# …et dans CHAQUE job : le fix docker-credential-desktop.exe,
# l'installation manuelle de trivy/gitleaks avec SHA256,
# les réseaux Docker à créer/nettoyer à la main…
.setup_docker_config: &setup_docker_config |
  mkdir -p "/tmp/docker-config-${CI_JOB_ID}"
  echo '{"auths":{}}' > "/tmp/docker-config-${CI_JOB_ID}/config.json"
```

**Après** *(executor Docker sur une VM Linux : chaque job = un conteneur jetable ; les outils = des images officielles épinglées ; les dépendances de test = des `services:` natifs)* :

```toml
# config.toml du runner
[[runners]]
  executor = "docker"
  [runners.docker]
    image = "alpine:3.20"
    privileged = true                      # requis pour le service docker:dind
    pull_policy = "if-not-present"         # images épinglées → cache hôte réutilisé
                                           # (services MSSQL/Redis/dind, images d'outils)
    volumes = ["/cache"]
```

```yaml
# Un scan devient trivial — plus d'installation, plus de checksum à gérer :
container_scan:
  image:
    name: aquasec/trivy:0.69.3   # version épinglée = même garantie que le SHA256
    entrypoint: [""]
  script:
    - trivy image --severity HIGH,CRITICAL --ignore-unfixed "$IMAGE_NAME:$IMAGE_TAG_TMP"

# Les bases de test deviennent des services natifs — plus de réseau manuel :
test:
  services:
    - name: mcr.microsoft.com/mssql/server:2019-latest
      alias: mssql
    - name: redis:7-alpine
      alias: redis
```

Disparaissent : `setup_docker_config`, `cleanup_docker_config`, `install_trivy`, `install_gitleaks`, `create_docker_network`, `cleanup_test_containers`, `pull_images` — **~150 lignes de contournements**.

> **Nuance importante sur le cache d'images** : les `services:` d'un job (MSSQL, Redis, dind lui-même) et les images de jobs (Trivy, Semgrep…) sont lancés par le démon **de l'hôte** du runner — avec `pull_policy = "if-not-present"`, ils restent en cache entre les jobs (le pré-pull manuel `pull_images` devient inutile). Seuls les `docker build/pull` exécutés *dans* dind repartent d'un démon vierge à chaque job : c'est le rôle du cache de registre (`--cache-from`, déjà en place) et du **Dependency Proxy** GitLab (gratuit) pour les images de base Docker Hub des Dockerfiles.

---

#### #9 — Mutualisation : de 2 × 1000 lignes à 2 × 8 lignes

**Avant** : deux fichiers autonomes, ~70 % de logique dupliquée qui divergera.

**Après** *(le `.gitlab-ci.yml` complet d'un service — le vrai contenu vit dans `ci-templates`, voir §10)* :

```yaml
include:
  - project: 'mon-groupe/ci-templates'
    ref: v1.0.0
    file: '/pipelines/django-service.yml'   # ou /pipelines/angular-app.yml

variables:
  COVERAGE_THRESHOLD: "85"
  HEALTH_PATH: "/health/"
```

---

#### #10 — Review apps : voir la MR avant de merger

**Avant** : rien — la QA attend staging.

**Après** *(frontend ; un environnement éphémère par MR, détruit au merge ou après 3 jours)* :

```yaml
deploy_review:
  stage: deploy
  image: dtzar/helm-kubectl:3.16
  needs: ['docker_build_final']
  variables:
    IMAGE_TAG_TMP: 'tmp-$CI_COMMIT_SHORT_SHA'
  environment:
    name: review/$CI_MERGE_REQUEST_IID
    url: https://mr-$CI_MERGE_REQUEST_IID.review.example.com
    on_stop: stop_review
    auto_stop_in: 3 days
  script:
    - kubectl config use-context "$AKS_KUBE_CONTEXT"
    - |
      helm upgrade --install "review-$CI_MERGE_REQUEST_IID" ./deployment/chart \
        --namespace review --create-namespace \
        --set image.repository="$IMAGE_NAME" \
        --set image.tag="$IMAGE_TAG_TMP" \
        --set ingress.host="mr-$CI_MERGE_REQUEST_IID.review.example.com"
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

stop_review:
  stage: deploy
  image: dtzar/helm-kubectl:3.16
  environment:
    name: review/$CI_MERGE_REQUEST_IID
    action: stop
  script:
    - kubectl config use-context "$AKS_KUBE_CONTEXT"
    - helm uninstall "review-$CI_MERGE_REQUEST_IID" --namespace review
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual
  allow_failure: true
```

---

#### #11 — Annoter chaque déploiement dans Grafana (la jonction des deux stacks)

**Avant** : les dashboards SLO ignorent les déploiements — « qu'est-ce qui a changé ? » reste sans réponse.

**Après** *(3 lignes à la fin de chaque job de deploy ; `GRAFANA_URL` et `GRAFANA_API_TOKEN` en variables CI)* :

```yaml
    - |
      curl -sf -X POST "$GRAFANA_URL/api/annotations" \
        -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"tags\":[\"deploy\",\"$CI_PROJECT_NAME\",\"$CI_ENVIRONMENT_NAME\"],
             \"text\":\"Deploy $CI_PROJECT_NAME ${CI_COMMIT_TAG:-$CI_COMMIT_SHORT_SHA} → $CI_ENVIRONMENT_NAME ($GITLAB_USER_LOGIN)\"}" \
        || echo "WARN: annotation Grafana échouée (non bloquant)"
```

Sur les dashboards, chaque courbe porte désormais un trait vertical « deploy » — l'écran 8 du §5.

---

#### #12 — E2E sans dépendance à un backend distant

**Avant** *(le login passe par le backend d'auth réel → flakiness réseau structurelle)* :

```yaml
rules:
  - if: '$E2E_USERNAME == null || $E2E_USERNAME == ""'
    when: never
```

**Après** *(l'auth aussi est simulée : le `webServer` Playwright démarre le mock d'auth à côté du mock GraphQL — zéro dépendance externe, le job tourne sur chaque MR)* :

```ts
// playwright.config.ts — extrait
webServer: [
  { command: 'node mocks/graphql-server.js', port: 4001, reuseExistingServer: !process.env.CI },
  { command: 'node mocks/auth-server.js',    port: 4002, reuseExistingServer: !process.env.CI },
  { command: 'npx nx serve units-webapp',      port: 4200, reuseExistingServer: !process.env.CI },
],
```

Les E2E *avec* auth réelle restent utiles — mais en job planifié contre **staging**, pas dans le chemin des MR.
---

<a name="8"></a>
## 8. Modèle de maturité : par où commencer

Même logique que pour l'observabilité : par phases, chacune rentable seule. **Vous êtes déjà en phase 2 avancée** — c'est un excellent point de départ.

```mermaid
flowchart LR
  M1["PHASE 1 · CI de base<br/>lint + build + tests<br/>+ image Docker<br/><i>(acquis)</i>"]
  M2["PHASE 2 · DevSecOps<br/>SAST · secrets · SCA<br/>scan conteneur · SBOM<br/>smoke + promotion<br/><i>(acquis ✔)</i>"]
  M3["PHASE 3 · Industrialiser<br/>ci-templates mutualisés<br/>executor Docker<br/>migrations Django · Renovate<br/>chaîne dev→staging→prod réelle"]
  M4["PHASE 4 · GitOps<br/>Argo CD sur AKS<br/>dépôt gitops-config<br/>review apps · buf breaking<br/>DAST · annotations Grafana"]
  M5["PHASE 5 · Piloter<br/>DORA dans Grafana<br/>canary validé par SLO<br/>feature flags (Unleash)<br/>signature Cosign"]
  M1 --> M2 --> M3 --> M4 --> M5
```

| Phase | Objectif | Actions clés | Valeur |
|---|---|---|---|
| **3 · Industrialiser** (votre prochaine) | Passer de « 2 pipelines solides » à « N services maintenables » | ci-templates + include versionné ; executor Docker ; jobs migrations ; Renovate ; activer dev→staging→prod (tags SemVer) ; cleanup registre | Coût de maintenance divisé par N ; le risque migrations couvert |
| **4 · GitOps** | Livraison standard Kubernetes | Argo CD + gitops-config (transition §7.5) ; review apps ; buf breaking sur protos ; ZAP ; annotations de deploy | Rollback en minutes, audit total, « quoi tourne où » instantané |
| **5 · Piloter** | La boucle complète CI/CD ↔ observabilité | DORA en Grafana ; canary jugé par les SLO ; Unleash ; Cosign + vérification au déploiement | Livraison mesurée, sécurisée de bout en bout, réversible |

---

<a name="9"></a>
## 9. Annexes

### 9.1 Checklist de mise en place

- [ ] Pipeline mutualisé dans un dépôt `ci-templates` versionné, inclus par chaque service.
- [ ] Runners auto-hébergés en **executor Docker** (puis Kubernetes) — plus de shell/WSL.
- [ ] **Build once** : une image `tmp-<sha>` → scans → smoke → promotion `<sha>` + `vX.Y.Z`. Jamais de rebuild par environnement, jamais de deploy de `latest`.
- [ ] MR = cockpit : tous les rapports (`codequality`, `sast`, `secret_detection`, `dependency_scanning`, `container_scanning`, couverture) visibles dans la MR.
- [ ] Secrets : bloquants au commit (Gitleaks) ; variables CI protected/masked ; cible External Secrets + Key Vault.
- [ ] Django : `makemigrations --check`, `migrate` testé en CI, migrations expand/contract, `/health` + `/ready` distincts.
- [ ] Angular : `nx affected`, budgets de bundle, Lighthouse CI, source maps vers GlitchTip/Sentry, config au runtime.
- [ ] Protos centralisés + `buf breaking` bloquant.
- [ ] Renovate planifié ; images de base épinglées par digest.
- [ ] Chaîne d'environnements réelle : develop→dev (auto), main→staging, tag→prod (manuel, protégé).
- [ ] Argo CD sur AKS + dépôt `gitops-config` ; Ansible sur l'infra.
- [ ] Chaque deploy annoté dans Grafana ; DORA suivies mensuellement.
- [ ] Politique de nettoyage du registre.

### 9.2 Anti-patterns à éviter

- **Rebuild par environnement** : « ça marchait en staging » ne prouve plus rien. Un seul build, promu.
- **Déployer `latest`** : non-reproductible, rollback aveugle.
- **Config au build-time** (API_URL compilée dans le bundle Angular) : viole build-once ; injecter au runtime.
- **Pipelines copiés-collés entre services** : divergence garantie ; templates + include.
- **Tout bloquant dès le jour 1** : l'équipe contourne (`[skip ci]`, force-merge). Durcir progressivement.
- **Scans dont personne ne lit les rapports** : sans écran d'agrégation (écran 4), le DevSecOps est décoratif.
- **Migrations destructrices couplées au code** : toujours expand/contract, sinon le rollback applicatif casse la donnée.
- **Credentials de prod dans la CI** : le modèle pull (Argo CD) les garde dans le cluster.
- **E2E dépendant de services distants vivants** : flakiness structurelle ; mocker ou conteneuriser.
- **Le pipeline lent qu'on ne mesure pas** : > 15 min = contournements ; instrumenter le pipeline lui-même.

### 9.3 Glossaire express

- **CI / CD (delivery) / CD (deployment)** — intégration continue / artefact toujours prêt / prod automatique.
- **DORA** — les 4 métriques de performance du delivery (fréquence, lead time, taux d'échec, MTTR).
- **Quality gate** — condition bloquante pour merger/publier (couverture ≥ X, zéro CRITICAL…).
- **SAST / DAST / SCA** — analyse statique du code / attaque dynamique de l'app déployée / analyse des dépendances.
- **SBOM** — inventaire des composants d'un artefact (CycloneDX/SPDX), exigence de conformité montante.
- **Build once, promote** — un artefact unique, immuable, promu d'environnement en environnement.
- **GitOps** — l'état désiré des environnements vit dans Git ; un agent (Argo CD) réconcilie en continu (modèle *pull*).
- **Dérive (drift)** — écart entre l'état déclaré dans Git et l'état réel du cluster.
- **Canary / Blue-Green / Rolling** — stratégies d'exposition progressive / de bascule / de remplacement graduel.
- **Feature flag** — activer une fonctionnalité indépendamment de son déploiement.
- **Contract testing / buf breaking** — vérifier en CI qu'un changement d'API/proto ne casse pas les consommateurs.
- **Review app** — environnement éphémère déployé pour une MR, détruit au merge.
- **Expand/contract** — pattern de migration de schéma rétro-compatible (ajouter, migrer, puis seulement retirer).

---

### En une phrase

**Un seul squelette universel — lint, build, sécurité en parallèle, tests, image unique scannée puis promue, déploiement progressif — mutualisé dans des templates GitLab pour tous vos microservices, exécuté sur vos runners gratuits, sécurisé par Semgrep/Gitleaks/Trivy/ZAP, livré sur AKS en GitOps par Argo CD (Ansible gardant l'infra), mesuré par les métriques DORA et bouclé sur vos SLO Grafana — le tout gratuit, open source, et déjà aux deux tiers construit dans vos pipelines actuels.**
---

<a name="10"></a>
## 10. Les pipelines à jour — versions finales complètes

Les deux fichiers ci-dessous intègrent **toutes** les recommandations applicables au niveau du fichier (#1, #2, #4, #5, #7, #8, #10, #11, #12 ; les correctifs #3, #6, #9 se font hors fichier : politique de registre, projet Renovate, extraction en templates — voir §10.3).

**Prérequis supposés** (les changements d'infra du §7) :

- Runner en **executor Docker** (`privileged = true`), tag `mirweb-docker` — plus aucun contournement WSL.
- Un dépôt **`gitops-config`** (§7.5) et un token projet `GITOPS_TOKEN` (scope `write_repository`).
- Variables CI : `COVERAGE_THRESHOLD`, `GITOPS_REPO_PATH`, `GRAFANA_URL`, `GRAFANA_API_TOKEN`, `SENTRY_URL` (GlitchTip), `SENTRY_AUTH_TOKEN`, `AKS_KUBE_CONTEXT` (agent GitLab).
- Environnements `production` **protégés** et tags `v*` **protégés** dans GitLab.
- Pendant la transition, l'ancien `trigger_ansible_deploy` peut cohabiter — il est fourni en commentaire.
- Review apps : nécessitent un **DNS wildcard** `*.review.example.com` pointant vers l'ingress AKS.

#### Ce qui s'exécute selon le déclencheur

| Déclencheur | Jobs exécutés | Jobs exclus |
|---|---|---|
| **Merge request** | lint, checks (django/nx), build, sécurité, tests unitaires **+ E2E (front)**, image `tmp`, scans, smoke, **review app (front)** | promotion, déploiements, jobs planifiés |
| **Push `develop`** | tout le chemin + **promotion `:sha`** + **deploy_dev (auto)** | staging, prod |
| **Push `main`** | idem + **deploy_staging (auto)** | prod |
| **Tag `vX.Y.Z`** | revalidation complète + promotion `:sha` + `:vX.Y.Z` + **deploy_production (manuel)** | — |
| **Schedule (hebdo)** | gitleaks **historique complet**, **ZAP** (staging) | secret fast-scan ; ⚠ lint/build/test tournent aussi par défaut — voir note 1 |

#### Notes de performance & options

**1 — Alléger les pipelines planifiés.** Les schedules ne servent qu'aux audits (gitleaks full, ZAP) ; pour ne pas y rejouer lint/build/test, ajoutez en tête de leurs `rules:` :

```yaml
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
      when: never
```

**2 — Pipelines de tag : deux stratégies.** Par défaut, un tag **revalide tout** (sécurité maximale, ~même durée qu'un push). Option rapide — cohérente avec *build once, promote* — si vos tags pointent toujours un commit déjà validé sur `main` : remplacer le pipeline complet par une simple re-promotion (~1 min) :

```yaml
promote_release:                       # sur tag : retague l'image DÉJÀ validée du même SHA
  stage: package
  extends: .docker_job
  script:
    - docker pull "$IMAGE_NAME:$CI_COMMIT_SHA"        # existe depuis le pipeline de main
    - docker tag  "$IMAGE_NAME:$CI_COMMIT_SHA" "$IMAGE_NAME:$CI_COMMIT_TAG"
    - docker push "$IMAGE_NAME:$CI_COMMIT_TAG"
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/'
```

(dans ce cas : `when: never` sur `$CI_COMMIT_TAG` dans les autres jobs, et `deploy_production` passe à `needs: [promote_release]`).

**3 — Cache d'images.** Sur le runner, `pull_policy = "if-not-present"` garde en cache hôte les images de **services** (MSSQL ~1,5 Go, Redis, dind) et d'**outils** (Trivy, Semgrep, Gitleaks) — versions épinglées oblige, c'est sûr. Pour les images de base des Dockerfiles (Docker Hub), activez le **Dependency Proxy** GitLab (gratuit) : `FROM ${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/library/python:3.12-slim`.

**4 — Impact sur le temps d'exécution.** À périmètre MR, le chemin critique (lint → build → tests → package) est inchangé ; les nouveaux jobs (django_checks, bandit, pip-audit, E2E) tournent **en parallèle** hors de ce chemin, et les suppressions (installations d'outils remplacées par des images, `nx affected`, ruff, `services:` natifs) font gagner plus que les ajouts ne coûtent. Détail complet dans la réponse d'accompagnement.

### 10.1 Backend Django — `.gitlab-ci.yml` (units-service, v4)

```yaml
# =============================================================================
# units-service — Pipeline v4 (recommandations du document d'architecture)
#   lint(+django_checks) --+--> build ----+--> test --> package --> deploy
#                          +--> security -+   (dev auto / staging auto / prod tag manuel)
# Runner : executor Docker (tag mirweb-docker)
# =============================================================================

workflow:
  rules:
    - if: '$CI_COMMIT_MESSAGE =~ /(\[skip ci\]|\[ci skip\])/i'
      when: never
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
    - if: '$CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS'
      when: never
    - if: '$CI_COMMIT_BRANCH'
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/'      # [#1] les tags déclenchent (prod)
    - when: never

stages: [lint, build, security, test, package, deploy]

default:
  tags: [mirweb-docker]                                # [#8] executor Docker
  interruptible: true

variables:
  IMAGE_NAME:  "$CI_REGISTRY_IMAGE"
  CACHE_IMAGE: "$CI_REGISTRY_IMAGE/cache/$CI_PROJECT_NAME"
  IMAGE_TAG_TMP: "tmp-$CI_COMMIT_SHORT_SHA"
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  COVERAGE_THRESHOLD: "85"                             # [#7] partagé front/back
  GIT_DEPTH: "0"
  SERVICE_PORT: "8000"
  HEALTH_PATH: "/health/"

# --- Template Python (image officielle épinglée — remplace l'install manuelle) ---
.python_job:
  image: python:3.12-slim
  cache:
    key: { files: [requirements.txt], prefix: "pip-$CI_COMMIT_REF_SLUG" }
    paths: [.cache/pip]
    policy: pull
  before_script:
    - pip install --quiet --upgrade pip
    - pip install --quiet -r requirements.txt

# --- Template Docker-in-Docker (remplace shell+WSL et ses contournements) ---
.docker_job:
  image: docker:27.5.1
  services: ["docker:27.5.1-dind"]
  variables: { DOCKER_TLS_CERTDIR: "/certs" }
  before_script:
    - docker login -u gitlab-ci-token -p "$CI_JOB_TOKEN" "$CI_REGISTRY"

# =============================== LINT ========================================
lint:
  extends: .python_job
  stage: lint
  cache: { key: { files: [requirements.txt], prefix: "pip-$CI_COMMIT_REF_SLUG" }, paths: [.cache/pip], policy: pull-push }
  script:
    # ruff remplace isort+black+flake8 (1 outil, ~100x plus rapide) — mypy conservé
    # (config : migrer .flake8/setup.cfg vers [tool.ruff] dans pyproject.toml)
    - pip install --quiet ruff mypy mypy-gitlab-code-quality
    - ruff check .                                    # bloquant : erreurs réelles
    - ruff format --check .                           # bloquant : formatage
    - mypy . --config-file=mypy.ini --output=json 2>/dev/null | mypy-gitlab-code-quality > gl-code-quality-report.json || true
    - test -s gl-code-quality-report.json || echo '[]' > gl-code-quality-report.json
  artifacts:
    when: always
    reports: { codequality: gl-code-quality-report.json }
    expire_in: 1 week

django_checks:                                         # [#4] NOUVEAU — risque n°1 couvert
  extends: .python_job
  stage: lint
  variables: { SECRET_KEY: "ci-only", DJANGO_SETTINGS_MODULE: "units_project.settings" }
  script:
    - python manage.py makemigrations --check --dry-run   # migration manquante = échec
    - python manage.py check --deploy --fail-level WARNING # config prod dangereuse = échec
  allow_failure: false

# =============================== BUILD =======================================
build_microservice:
  extends: .python_job
  stage: build
  needs: [lint]
  script:
    - pip install --quiet grpcio-tools
    - mkdir -p generated
    # NOTE cible (§7.3) : protos centralisés dans un dépôt unique + buf breaking ;
    # en attendant, compilation locale conservée :
    - |
      if ls protos/*.proto 2>/dev/null; then
        python -m grpc_tools.protoc --proto_path=./protos \
          --python_out=./generated --grpc_python_out=./generated ./protos/*.proto
      else
        touch generated/.keep
      fi
  artifacts: { paths: [generated/], expire_in: 2h }

# ============================= SECURITY ======================================
semgrep_sast:
  stage: security
  needs: [lint]
  image: { name: semgrep/semgrep, entrypoint: [""] }   # [#8] image officielle, plus d'install
  script:
    # p/django désormais sur CHAQUE MR (avant : schedule uniquement)
    - semgrep scan --config=p/python --config=p/django --error --gitlab-sast --output gl-sast-report.json . || SEMGREP_EXIT=$?
    - if [ "${SEMGREP_EXIT:-0}" -gt 1 ]; then exit "$SEMGREP_EXIT"; fi   # crash outil = échec réel
    - test -s gl-sast-report.json || echo '{"version":"15.0.0","vulnerabilities":[]}' > gl-sast-report.json
  artifacts:
    when: always
    reports: { sast: gl-sast-report.json }
    expire_in: 1 week
  allow_failure: true

bandit_sast:                                           # NOUVEAU — SAST spécialisé Python
  stage: security
  needs: [lint]
  image: python:3.12-slim
  before_script:
    - pip install --quiet bandit                       # pas besoin des requirements → job léger (~20 s)
  script:
    - bandit -r . -x ./tests,./generated -f json -o bandit-report.json || true
    - bandit -r . -x ./tests,./generated || true       # sortie lisible dans le log
  artifacts: { when: always, paths: [bandit-report.json], expire_in: 1 week }
  allow_failure: true

secret_scanning:
  stage: security
  needs: [lint]
  image: { name: ghcr.io/gitleaks/gitleaks:v8.18.4, entrypoint: [""] }  # [#8] image épinglée
  script:
    - CONFIG_FLAG=""; [ -f .gitleaks.toml ] && CONFIG_FLAG="--config .gitleaks.toml"
    - gitleaks detect $CONFIG_FLAG --source . --log-opts="-1" --report-format json --report-path gitleaks.json
  artifacts:
    when: always
    reports: { secret_detection: gitleaks.json }
    expire_in: 1 week
  allow_failure: false                                  # un secret commité = bloquant
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
      when: never
    - when: on_success

secret_scanning_full_history:
  stage: security
  needs: [lint]
  interruptible: false
  image: { name: ghcr.io/gitleaks/gitleaks:v8.18.4, entrypoint: [""] }
  script:
    - CONFIG_FLAG="";   [ -f .gitleaks.toml ]        && CONFIG_FLAG="--config .gitleaks.toml"
    - BASELINE_FLAG=""; [ -f gitleaks-baseline.json ] && BASELINE_FLAG="--baseline-path gitleaks-baseline.json"
    - gitleaks detect $CONFIG_FLAG $BASELINE_FLAG --source . --log-opts="--all" --report-format json --report-path gitleaks_full.json
  artifacts: { when: always, paths: [gitleaks_full.json], expire_in: 1 month }
  allow_failure: true
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'

dependency_scan:
  stage: security
  needs: [lint]
  image: { name: aquasec/trivy:0.69.3, entrypoint: [""] }
  cache: { key: trivy-db-stable, paths: [.trivycache] }
  variables: { TRIVY_CACHE_DIR: "$CI_PROJECT_DIR/.trivycache" }
  script:
    - trivy fs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed
      --format json -o gl-dependency-scanning-report.json . || true
    - trivy fs --format cyclonedx -o gl-sbom-report.cdx.json . || true
    - test -s gl-dependency-scanning-report.json || echo '{"Results":[]}' > gl-dependency-scanning-report.json
  artifacts:
    when: always
    paths: [gl-dependency-scanning-report.json, gl-sbom-report.cdx.json]
    reports:
      dependency_scanning: gl-dependency-scanning-report.json
      cyclonedx: [gl-sbom-report.cdx.json]
    expire_in: 1 week
  allow_failure: true

pip_audit:                                             # NOUVEAU — 2e base CVE Python
  stage: security
  needs: [lint]
  image: python:3.12-slim
  before_script:
    - pip install --quiet pip-audit                    # lit requirements.txt, n'installe pas le projet
  script:
    - pip-audit -r requirements.txt --format json --output pip-audit.json || true
    - pip-audit -r requirements.txt || true
  artifacts: { when: always, paths: [pip-audit.json], expire_in: 1 week }
  allow_failure: true

# ================================ TEST =======================================
test:
  extends: .python_job
  stage: test
  needs: [build_microservice]
  services:                                            # [#8] remplace les docker run manuels
    - name: mcr.microsoft.com/mssql/server:2019-latest
      alias: mssql
    - name: redis:7-alpine
      alias: redis
  variables:
    ACCEPT_EULA: "Y"
    MSSQL_SA_PASSWORD: "Ci-Only-P@ssw0rd!"
    SA_PASSWORD: "Ci-Only-P@ssw0rd!"
    DB_HOST: "mssql"
    REDIS_URL: "redis://redis:6379/0"
    SECRET_KEY: "ci-only"
    DJANGO_SETTINGS_MODULE: "units_project.settings"
  script:
    - pip install --quiet pytest pytest-django coverage
    # Readiness MSSQL (le service démarre en ~10-20 s)
    - |
      for i in $(seq 1 20); do
        python -c "import socket; socket.create_connection(('mssql',1433),3)" && break
        echo "waiting mssql ($i/20)…"; sleep 3
      done
    - python manage.py migrate --no-input              # [#4] les migrations s'appliquent vraiment
    - coverage run -m pytest --tb=short --junitxml=junit.xml
    - coverage report
    - coverage xml -o coverage.xml
    - |
      COVERAGE_INT=$(coverage report --format=total | cut -d'.' -f1)
      echo "Coverage: ${COVERAGE_INT}% (seuil: ${COVERAGE_THRESHOLD}%)"
      if [ "$COVERAGE_INT" -lt "$COVERAGE_THRESHOLD" ]; then
        echo "ERROR: couverture sous le seuil"; exit 1
      fi
  coverage: '/TOTAL.*\s(\d+)%/'
  artifacts:
    when: always
    reports:
      junit: junit.xml
      coverage_report: { coverage_format: cobertura, path: coverage.xml }
    expire_in: 1 week

# =============================== PACKAGE =====================================
docker_build:
  extends: .docker_job
  stage: package
  needs: [test, build_microservice]
  script:
    - docker pull "$CACHE_IMAGE:latest" || true
    - docker build --build-arg BUILDKIT_INLINE_CACHE=1 --cache-from "$CACHE_IMAGE:latest"
      -t "$IMAGE_NAME:$IMAGE_TAG_TMP" .
    - docker push "$IMAGE_NAME:$IMAGE_TAG_TMP"
  rules:
    - if: '$CI_PIPELINE_SOURCE =~ /push|merge_request_event/ || $CI_COMMIT_TAG'

container_scan:
  stage: package
  needs: [docker_build]
  image: { name: aquasec/trivy:0.69.3, entrypoint: [""] }
  cache: { key: trivy-db-stable, paths: [.trivycache] }
  variables:
    TRIVY_CACHE_DIR: "$CI_PROJECT_DIR/.trivycache"
    TRIVY_USERNAME: gitlab-ci-token
    TRIVY_PASSWORD: "$CI_JOB_TOKEN"
  script:
    - trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --timeout 20m
      --format json -o gl-container-scanning-report.json "$IMAGE_NAME:$IMAGE_TAG_TMP" || true
    - trivy image --format cyclonedx -o gl-sbom-container.cdx.json "$IMAGE_NAME:$IMAGE_TAG_TMP" || true
    - test -s gl-container-scanning-report.json || echo '{"Results":[]}' > gl-container-scanning-report.json
  artifacts:
    when: always
    paths: [gl-container-scanning-report.json, gl-sbom-container.cdx.json]
    reports:
      container_scanning: gl-container-scanning-report.json
      cyclonedx: [gl-sbom-container.cdx.json]
    expire_in: 1 week
  allow_failure: true
  rules:
    - if: '$CI_PIPELINE_SOURCE =~ /push|merge_request_event/ || $CI_COMMIT_TAG'

smoke_test:
  extends: .docker_job
  stage: package
  interruptible: false
  needs: [container_scan, docker_build]
  script:
    - docker pull "$IMAGE_NAME:$IMAGE_TAG_TMP"
    - docker run -d --name smoke -e SECRET_KEY=smoketest
      -e DJANGO_SETTINGS_MODULE=units_project.settings "$IMAGE_NAME:$IMAGE_TAG_TMP"
    - sleep 10
    - docker exec smoke curl -sf "http://127.0.0.1:${SERVICE_PORT}${HEALTH_PATH}"
      || { docker logs smoke; exit 1; }
  # dind éphémère par job : conteneurs et réseaux meurent avec le job — aucun nettoyage requis
  rules:
    - if: '$CI_PIPELINE_SOURCE =~ /push|merge_request_event/ || $CI_COMMIT_TAG'

promote_image:                                         # [#2] SHA + SemVer, jamais latest
  extends: .docker_job
  stage: package
  interruptible: false
  needs: [smoke_test]
  script:
    - docker pull "$IMAGE_NAME:$IMAGE_TAG_TMP"
    - docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:$CI_COMMIT_SHA"
    - docker push "$IMAGE_NAME:$CI_COMMIT_SHA"
    - |
      if [ -n "$CI_COMMIT_TAG" ]; then
        docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:$CI_COMMIT_TAG"
        docker push "$IMAGE_NAME:$CI_COMMIT_TAG"
      fi
    - docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$CACHE_IMAGE:latest"   # cache de build only
    - docker push "$CACHE_IMAGE:latest"
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push" || $CI_COMMIT_TAG'

# =============================== DEPLOY ======================================
# GitOps (§7.5) : le deploy = un commit du nouveau tag dans gitops-config.
# Argo CD réconcilie. Rollback = git revert dans gitops-config.
.deploy_gitops:
  stage: deploy
  interruptible: false
  needs: [promote_image]
  image: alpine:3.20
  before_script: [apk add --no-cache git yq curl]      # yq v4 (mikefarah) — paquet alpine
  script:
    - DEPLOY_TAG="${CI_COMMIT_TAG:-$CI_COMMIT_SHA}"
    - git clone "https://gitlab-ci-token:${GITOPS_TOKEN}@gitlab.com/${GITOPS_REPO_PATH}.git" gitops
    - cd gitops
    - yq -i ".image.tag = \"$DEPLOY_TAG\"" "environments/${TARGET_ENV}/${CI_PROJECT_NAME}/values.yaml"
    - git config user.email "ci@example.com" && git config user.name "gitlab-ci"
    - git commit -am "deploy(${CI_PROJECT_NAME}) ${DEPLOY_TAG} -> ${TARGET_ENV}"
    - git push origin HEAD:main
    # [#11] Annotation Grafana — la jonction avec la stack d'observabilité
    - |
      curl -sf -X POST "$GRAFANA_URL/api/annotations" \
        -H "Authorization: Bearer $GRAFANA_API_TOKEN" -H "Content-Type: application/json" \
        -d "{\"tags\":[\"deploy\",\"$CI_PROJECT_NAME\",\"$TARGET_ENV\"],
             \"text\":\"Deploy $CI_PROJECT_NAME $DEPLOY_TAG -> $TARGET_ENV ($GITLAB_USER_LOGIN)\"}" \
        || echo "WARN: annotation Grafana échouée (non bloquant)"

deploy_dev:                                            # [#1] chaîne d'environnements réelle
  extends: .deploy_gitops
  variables: { TARGET_ENV: dev }
  environment: { name: dev }
  rules:
    - if: '$CI_COMMIT_BRANCH == "develop"'
      when: on_success

deploy_staging:
  extends: .deploy_gitops
  variables: { TARGET_ENV: staging }
  environment: { name: staging }
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
      when: on_success

deploy_production:
  extends: .deploy_gitops
  variables: { TARGET_ENV: prod }
  environment: { name: production }
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/'
      when: manual                                     # + environnement protégé côté GitLab
  allow_failure: false

# --- Transition : l'ancien trigger Ansible, conservé le temps de la migration ---
# trigger_ansible_deploy:
#   stage: deploy
#   needs: [promote_image]
#   script:
#     - curl -s -X POST -F "token=$ANSIBLE_TRIGGER_TOKEN" -F "ref=develop"
#       -F "variables[SERVICE_NAME]=$CI_PROJECT_NAME"
#       -F "variables[APP_IMAGE]=$IMAGE_NAME:$CI_COMMIT_SHA"     # [#2] SHA, pas latest
#       "https://gitlab.com/api/v4/projects/$ANSIBLE_PROJECT_ID/trigger/pipeline"
#   environment: { name: dev }                                   # [#1] nom honnête
#   rules:
#     - if: '$CI_COMMIT_BRANCH == "develop"'
#       when: manual

dast_zap_baseline:                                     # [#5] NOUVEAU — hebdo contre staging
  stage: deploy
  needs: []
  image: { name: ghcr.io/zaproxy/zaproxy:stable, entrypoint: [""] }
  variables: { TARGET_URL: "https://staging.example.com" }
  script:
    - mkdir -p /zap/wrk
    - zap-baseline.py -t "$TARGET_URL" -J zap-report.json -r zap-report.html || true
    - cp /zap/wrk/zap-report.* . 2>/dev/null || true
  artifacts: { when: always, paths: [zap-report.json, zap-report.html], expire_in: 1 month }
  allow_failure: true
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
```
### 10.2 Frontend Angular — `.gitlab-ci.yml` (units-webapp, v2)

```yaml
# =============================================================================
# units-webapp — Pipeline v2 (recommandations du document d'architecture)
#   lint --+--> build ----+--> test (unit+e2e) --> package --> deploy
#          +--> security -+                        (review app par MR)
# Runner : executor Docker (tag mirweb-docker)
# =============================================================================

workflow:
  rules:
    - if: '$CI_COMMIT_MESSAGE =~ /(\[skip ci\]|\[ci skip\])/i'
      when: never
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
    - if: '$CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS'
      when: never
    - if: '$CI_COMMIT_BRANCH'
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/'
    - when: never

stages: [lint, build, security, test, package, deploy]

default:
  tags: [mirweb-docker]
  interruptible: true

variables:
  NODE_OPTIONS: "--max-old-space-size=2048"
  IMAGE_NAME:  "$CI_REGISTRY_IMAGE/units-webapp"
  CACHE_IMAGE: "$CI_REGISTRY_IMAGE/cache/units-webapp"
  IMAGE_TAG_TMP: "tmp-$CI_COMMIT_SHORT_SHA"
  COVERAGE_THRESHOLD: "85"                             # [#7] variable partagée
  GIT_DEPTH: "0"        # requis par nx affected (merge-base) — coût de clone accepté

.node_job:
  image: node:20.20.0-bullseye
  cache:
    key: { files: [package-lock.json, nx.json] }
    paths: [.npm/, .nx/cache/]
    policy: pull-push
  before_script:
    - npm ci --cache .npm --prefer-offline --no-audit --no-fund --ignore-scripts
    # nx affected : base = cible de la MR, sinon dernier commit
    - |
      if [ -n "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" ]; then
        git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
        export NX_BASE="origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
      else
        export NX_BASE="HEAD~1"
      fi

.docker_job:
  image: docker:27.5.1
  services: ["docker:27.5.1-dind"]
  variables: { DOCKER_TLS_CERTDIR: "/certs" }
  before_script:
    - docker login -u gitlab-ci-token -p "$CI_JOB_TOKEN" "$CI_REGISTRY"

# =============================== LINT ========================================
lint:
  extends: .node_job
  stage: lint
  script:
    # nx affected : on ne lint que ce que le commit touche — levier de vitesse n°1
    - npx nx affected -t lint --base="$NX_BASE" --configuration=ci
    - npx eslint webapp/units-webapp/src --config webapp/units-webapp/eslint.config.mjs
      --ext .ts,.html -f eslint-formatter-codeclimate -o gl-code-quality-report.json || true
    - test -s gl-code-quality-report.json || echo '[]' > gl-code-quality-report.json
  artifacts:
    when: always
    reports: { codequality: gl-code-quality-report.json }
    expire_in: 1 week
  allow_failure: false                                 # avant : true — un lint non bloquant ne sert à rien

# =============================== BUILD =======================================
build_application:
  extends: .node_job
  stage: build
  needs: [lint]
  script:
    - npm rebuild lightningcss --foreground-scripts
    # Les budgets de bundle (angular.json > budgets) font échouer ce build
    # si l'app grossit anormalement — le poids du bundle est une feature.
    - npx nx affected -t build --base="$NX_BASE" --configuration=production
    # Garantit dist/ même si l'app n'est pas "affectée" : l'image Docker et la
    # review app exigent un artefact. (Optimisation possible : conditionner tout
    # le chemin package/deploy avec rules:changes quand rien n'est affecté.)
    - test -d dist || npm run build -- --configuration=production
  artifacts: { paths: [dist/], expire_in: 2h }
  allow_failure: false

# ============================= SECURITY ======================================
semgrep_sast:
  stage: security
  needs: [lint]
  image: { name: semgrep/semgrep, entrypoint: [""] }
  script:
    - semgrep scan --config=p/typescript --config=p/owasp-top-ten --error
      --gitlab-sast --output gl-sast-report.json . || SEMGREP_EXIT=$?
    - if [ "${SEMGREP_EXIT:-0}" -gt 1 ]; then exit "$SEMGREP_EXIT"; fi
    - test -s gl-sast-report.json || echo '{"version":"15.0.0","vulnerabilities":[]}' > gl-sast-report.json
  artifacts:
    when: always
    reports: { sast: gl-sast-report.json }
    expire_in: 1 week
  allow_failure: true

secret_scanning:
  stage: security
  needs: [lint]
  image: { name: ghcr.io/gitleaks/gitleaks:v8.18.4, entrypoint: [""] }
  script:
    - CONFIG_FLAG=""; [ -f .gitleaks.toml ] && CONFIG_FLAG="--config .gitleaks.toml"
    - gitleaks detect $CONFIG_FLAG --source . --log-opts="-1"
      --report-format json --report-path gitleaks.json
  artifacts:
    when: always
    reports: { secret_detection: gitleaks.json }
    expire_in: 1 week
  allow_failure: false                                 # secret commité = bloquant
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
      when: never
    - when: on_success

dependency_scan:
  stage: security
  needs: [lint]
  image: { name: aquasec/trivy:0.69.3, entrypoint: [""] }
  cache: { key: trivy-cache, paths: [.trivycache] }
  variables: { TRIVY_CACHE_DIR: "$CI_PROJECT_DIR/.trivycache" }
  script:
    - trivy fs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --skip-dirs node_modules
      --format json -o gl-dependency-scanning-report.json . || true
    - trivy fs --scanners vuln,license --skip-dirs node_modules
      --format cyclonedx -o gl-sbom-report.cdx.json . || true
    - test -s gl-dependency-scanning-report.json || echo '{"Results":[]}' > gl-dependency-scanning-report.json
  artifacts:
    when: always
    paths: [gl-dependency-scanning-report.json, gl-sbom-report.cdx.json]
    reports:
      dependency_scanning: gl-dependency-scanning-report.json
      cyclonedx: [gl-sbom-report.cdx.json]
    expire_in: 1 week
  allow_failure: true

# ================================ TEST =======================================
unit_tests:
  extends: .node_job
  stage: test
  needs: [build_application]
  script:
    - npx nx affected -t test --base="$NX_BASE" --configuration=ci --coverage -- --ci 2>&1 | tee test-output.log
    - |
      if grep -qE '^\s*console\.(log|warn|error)\s*$' test-output.log; then
        echo "ERROR: console sale détectée dans les tests"; exit 1
      fi
  artifacts:
    when: always
    paths: [test-output.log, coverage/]
    expire_in: 1 week

coverage_check:
  stage: test
  image: node:20.20.0-bullseye
  needs: [unit_tests]
  script:
    - |
      # nx affected peut ne rien tester (commit sans impact) → pas de couverture = job neutre
      if [ ! -d coverage ] || [ -z "$(ls -A coverage 2>/dev/null)" ]; then
        echo "Aucune couverture générée (rien d'affecté par ce commit) — skip"
        exit 0
      fi
      if   [ -f coverage/apps/units-webapp/coverage-summary.json ]; then F=coverage/apps/units-webapp/coverage-summary.json
      elif [ -f coverage/coverage-summary.json ];                then F=coverage/coverage-summary.json
      else echo "ERROR: coverage-summary.json introuvable"; exit 1; fi
      COVERAGE=$(node -p "require('./$F').total.lines.pct")
      COVERAGE_INT=$(printf "%.0f" "$COVERAGE")
      echo "Coverage: ${COVERAGE_INT}% (seuil: ${COVERAGE_THRESHOLD}%)"   # [#7]
      if [ "$COVERAGE_INT" -lt "$COVERAGE_THRESHOLD" ]; then
        echo "ERROR: couverture sous le seuil"; exit 1
      fi
  allow_failure: true    # → passer à false une fois le seuil tenu 2 sprints

e2e_tests:
  stage: test
  image: mcr.microsoft.com/playwright:v1.61.1-noble
  needs: [lint]
  cache:
    key: { files: [package-lock.json, nx.json] }
    paths: [.npm/, .nx/cache/]
  before_script:
    - npm ci --cache .npm --prefer-offline --no-audit --no-fund --ignore-scripts
  script:
    # [#12] Auth mockée (playwright.config.ts > webServer : graphql:4001 + auth:4002 + app:4200)
    # → zéro dépendance externe, le job tourne sur CHAQUE MR sans condition de secret
    - npx nx e2e units-webapp-e2e
  artifacts: { when: always, paths: [dist/.playwright/], expire_in: 1 week }
  allow_failure: true    # → false une fois la stabilité prouvée sur le runner
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH'

# =============================== PACKAGE =====================================
docker_build_final:
  extends: .docker_job
  stage: package
  needs: [build_application, unit_tests]
  script:
    - docker pull "$CACHE_IMAGE:latest" || true
    - docker build --build-arg BUILDKIT_INLINE_CACHE=1 --cache-from "$CACHE_IMAGE:latest"
      -t "$IMAGE_NAME:$IMAGE_TAG_TMP" -f Dockerfile .
    - docker push "$IMAGE_NAME:$IMAGE_TAG_TMP"
  rules:
    - if: '$CI_PIPELINE_SOURCE =~ /push|merge_request_event/ || $CI_COMMIT_TAG'

docker_scan_final:
  stage: package
  needs: [docker_build_final]
  image: { name: aquasec/trivy:0.69.3, entrypoint: [""] }
  cache: { key: trivy-cache, paths: [.trivycache] }
  variables:
    TRIVY_CACHE_DIR: "$CI_PROJECT_DIR/.trivycache"
    TRIVY_USERNAME: gitlab-ci-token
    TRIVY_PASSWORD: "$CI_JOB_TOKEN"
  script:
    - trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --timeout 20m
      --format json -o gl-container-scanning-report.json "$IMAGE_NAME:$IMAGE_TAG_TMP" || true
    - trivy image --format cyclonedx -o gl-sbom-container.cdx.json "$IMAGE_NAME:$IMAGE_TAG_TMP" || true
    - test -s gl-container-scanning-report.json || echo '{"Results":[]}' > gl-container-scanning-report.json
  artifacts:
    when: always
    paths: [gl-container-scanning-report.json, gl-sbom-container.cdx.json]
    reports:
      container_scanning: gl-container-scanning-report.json
      cyclonedx: [gl-sbom-container.cdx.json]
    expire_in: 1 week
  allow_failure: true
  rules:
    - if: '$CI_PIPELINE_SOURCE =~ /push|merge_request_event/ || $CI_COMMIT_TAG'

docker_artifact_validation:
  extends: .docker_job
  stage: package
  interruptible: false
  needs: [docker_scan_final, docker_build_final]
  script:
    - docker pull "$IMAGE_NAME:$IMAGE_TAG_TMP"
    - CONTAINER=$(docker run -d "$IMAGE_NAME:$IMAGE_TAG_TMP")
    - sleep 5
    - docker exec "$CONTAINER" curl -sf http://127.0.0.1:8080/ || { docker logs "$CONTAINER"; exit 1; }
  # dind éphémère par job : aucun nettoyage nécessaire (et $CONTAINER n'existerait
  # pas dans un after_script — chaque section script tourne dans un shell distinct)
  rules:
    - if: '$CI_PIPELINE_SOURCE =~ /push|merge_request_event/ || $CI_COMMIT_TAG'

docker_push_final:                                     # [#2] SHA + SemVer, pas de latest déployable
  extends: .docker_job
  stage: package
  interruptible: false
  needs: [docker_artifact_validation]
  script:
    - docker pull "$IMAGE_NAME:$IMAGE_TAG_TMP"
    - docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:$CI_COMMIT_SHA"
    - docker push "$IMAGE_NAME:$CI_COMMIT_SHA"
    - |
      if [ -n "$CI_COMMIT_TAG" ]; then
        docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$IMAGE_NAME:$CI_COMMIT_TAG"
        docker push "$IMAGE_NAME:$CI_COMMIT_TAG"
      fi
    - docker tag  "$IMAGE_NAME:$IMAGE_TAG_TMP" "$CACHE_IMAGE:latest"
    - docker push "$CACHE_IMAGE:latest"
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push" || $CI_COMMIT_TAG'

upload_sourcemaps:                                     # NOUVEAU — erreurs prod lisibles (GlitchTip)
  stage: package
  image: getsentry/sentry-cli
  needs: [docker_push_final, build_application]
  variables:
    SENTRY_ORG: "mon-org"
    SENTRY_PROJECT: "units-webapp"
    # SENTRY_URL pointe vers votre GlitchTip self-host ; SENTRY_AUTH_TOKEN en variable CI
  script:
    - RELEASE="${CI_COMMIT_TAG:-$CI_COMMIT_SHA}"
    - sentry-cli releases new "$RELEASE"
    - sentry-cli releases files "$RELEASE" upload-sourcemaps dist/ --rewrite
    - sentry-cli releases finalize "$RELEASE"
  allow_failure: true
  rules:
    - if: '$CI_PIPELINE_SOURCE == "push" || $CI_COMMIT_TAG'

# =============================== DEPLOY ======================================
deploy_review:                                         # [#10] NOUVEAU — un env par MR
  stage: deploy
  image: dtzar/helm-kubectl:3.16
  needs: [docker_build_final]
  environment:
    name: review/$CI_MERGE_REQUEST_IID
    url: https://mr-$CI_MERGE_REQUEST_IID.review.example.com
    on_stop: stop_review
    auto_stop_in: 3 days
  script:
    - kubectl config use-context "$AKS_KUBE_CONTEXT"
    - helm upgrade --install "review-$CI_MERGE_REQUEST_IID" ./deployment/chart
      --namespace review --create-namespace
      --set image.repository="$IMAGE_NAME" --set image.tag="$IMAGE_TAG_TMP"
      --set ingress.host="mr-$CI_MERGE_REQUEST_IID.review.example.com"
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

stop_review:
  stage: deploy
  image: dtzar/helm-kubectl:3.16
  environment: { name: review/$CI_MERGE_REQUEST_IID, action: stop }
  script:
    - kubectl config use-context "$AKS_KUBE_CONTEXT"
    - helm uninstall "review-$CI_MERGE_REQUEST_IID" --namespace review
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual
  allow_failure: true

.deploy_gitops:                                        # identique au backend ([#1][#11])
  stage: deploy
  interruptible: false
  needs: [docker_push_final]
  image: alpine:3.20
  before_script: [apk add --no-cache git yq curl]
  script:
    - DEPLOY_TAG="${CI_COMMIT_TAG:-$CI_COMMIT_SHA}"
    - git clone "https://gitlab-ci-token:${GITOPS_TOKEN}@gitlab.com/${GITOPS_REPO_PATH}.git" gitops
    - cd gitops
    - yq -i ".image.tag = \"$DEPLOY_TAG\"" "environments/${TARGET_ENV}/units-webapp/values.yaml"
    - git config user.email "ci@example.com" && git config user.name "gitlab-ci"
    - git commit -am "deploy(units-webapp) ${DEPLOY_TAG} -> ${TARGET_ENV}"
    - git push origin HEAD:main
    - |
      curl -sf -X POST "$GRAFANA_URL/api/annotations" \
        -H "Authorization: Bearer $GRAFANA_API_TOKEN" -H "Content-Type: application/json" \
        -d "{\"tags\":[\"deploy\",\"units-webapp\",\"$TARGET_ENV\"],
             \"text\":\"Deploy units-webapp $DEPLOY_TAG -> $TARGET_ENV ($GITLAB_USER_LOGIN)\"}" \
        || echo "WARN: annotation Grafana échouée (non bloquant)"

deploy_dev:
  extends: .deploy_gitops
  variables: { TARGET_ENV: dev }
  environment: { name: dev }
  rules:
    - if: '$CI_COMMIT_BRANCH == "develop"'
      when: on_success

deploy_staging:
  extends: .deploy_gitops
  variables: { TARGET_ENV: staging }
  environment: { name: staging }
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
      when: on_success

deploy_production:
  extends: .deploy_gitops
  variables: { TARGET_ENV: prod }
  environment: { name: production }
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/'
      when: manual
  allow_failure: false
```

### 10.3 L'étape suivante : extraction en `ci-templates` (correctif #9)

Les deux fichiers ci-dessus partagent désormais volontairement les mêmes blocs (`workflow`, `.docker_job`, scans, promotion, `.deploy_gitops`). L'extraction devient mécanique :

```text
ci-templates/                        (nouveau dépôt GitLab, tags v1.0.0, v1.1.0…)
├── templates/
│   ├── workflow.yml                 # bloc workflow: commun
│   ├── security.yml                 # semgrep, gitleaks (fast+full), trivy fs
│   ├── package.yml                  # .docker_job, build tmp, scan image, SBOM, smoke, promote
│   └── deploy-gitops.yml            # .deploy_gitops + deploy_dev/staging/production + annotation
└── pipelines/
    ├── django-service.yml           # include des 4 templates + lint ruff/mypy,
    │                                #   django_checks, protos, test MSSQL/Redis
    └── angular-app.yml              # include des 4 templates + lint/build/test nx affected,
                                     #   e2e Playwright, sourcemaps, review apps
```

Chaque microservice se réduit alors au fichier de 8 lignes du §7.6-#9. Renovate maintient le `ref:` à jour, et une amélioration de pipeline se déploie sur toute la flotte par **une seule MR taguée**.

> **Rappel des actions hors-fichier** pour boucler les 12 correctifs : politique de nettoyage du registre (#3, API du §7.6), projet `renovate-runner` planifié (#6), protection des environnements `production` et des tags `v*` dans GitLab (#1), et création du dépôt `gitops-config` + installation d'Argo CD via Ansible (§7.5).

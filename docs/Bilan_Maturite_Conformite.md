# Bilan de maturité et de conformité

Revue au 20 juillet 2026. Elle confronte l'état réel du dépôt (preuves citées : fichiers et sections) aux attentes d'une application professionnelle : standards d'ingénierie et d'observabilité, complétude de la documentation, posture de sécurité, position vis à vis de SOC 2, et cohérence de la trajectoire. Le ton est volontairement franc. Ce qui va bien est crédité, ce qui manque est nommé sans détour.

> **Mise à jour du 20 juillet 2026 (après-midi).** Cette revue est l'instantané du **matin**, avant l'exécution du plan de correction. Depuis, les lots **S1 à S4 et la gouvernance R8** ont soldé l'essentiel des écarts décrits plus bas : scan de secrets (gitleaks en pre-commit et en intégration continue), conteneurs sans privilège, verrou de dépendances versionné, **dossier de sécurité** (`SECURITY.md`, `docs/Modele_Menace.md`, `docs/Runbooks_Incident.md`), **durcissement** (`observability/hardening/` : reverse proxy Caddy TLS, ports dépubliés, sauvegarde), **CI de sécurité** (`.github/workflows/ci.yml` : lint, build, scan de vulnérabilités, SBOM) et **protections de branches actives** (MR obligatoire, CI verte requise, historique linéaire). Le constat ci-dessous reste valable comme photographie de départ ; l'état à jour figure dans la section **« Suite donnée »** en fin de document et dans `MEMORY.md`. Seul demeure ouvert, volontairement hors périmètre, le **volet organisationnel** (politiques écrites, évaluation de risque formelle).

## Résumé exécutif

Le projet est solide sur ce qu'il prétend être aujourd'hui : une plateforme d'observabilité de laboratoire, construite avec des choix techniques modernes, une gouvernance stricte et une documentation nourrie. Sur ce périmètre, la maturité est réelle et supérieure à la moyenne.

En revanche, il ne faut pas confondre cet état avec celui d'une application prête pour la production ni conforme à un référentiel de sécurité. Les mécanismes de sécurité d'exploitation (chiffrement en transit, authentification des services, chiffrement au repos, chaîne d'intégration continue avec contrôles) ne sont pas encore en place. C'est assumé et planifié (lots 9 et 10 du backlog), mais tant que ce n'est pas fait, la réponse honnête aux questions « respecte t on les standards de sécurité » et « est on conforme SOC 2 » est non, pas encore.

Le tableau suivant résume la maturité par dimension.

| Dimension | Niveau | Justification en une ligne |
|---|---|---|
| Conception et mise en œuvre de l'observabilité | Élevé | OpenTelemetry natif, LGTM, méthodes RED et USE, SLO as code, corrélation des signaux, échantillonnage par la queue, discipline de cardinalité |
| Documentation technique, architecturale et utilisateur | Élevé avec lacunes | Deux documents d'architecture, un guide d'intégration, des README par composant ; manquent un fichier de sécurité, des runbooks d'incident et des ADR formels |
| Gouvernance et gestion du changement | Moyen à élevé | Règles Git strictes et hooks locaux effectifs, mais protections côté GitHub (R8) et intégration continue non encore actives |
| Sécurité d'infrastructure et applicative (état courant) | Faible (laboratoire assumé) | Pas de TLS, pas d'authentification sur la plupart des services, ports publiés en clair, un conteneur en root |
| Préparation à SOC 2 | Non prêt | Contrôles techniques d'accès et de chiffrement absents, pas d'évaluation de risque ni de politiques, et SOC 2 dépasse de toute façon le périmètre d'un dépôt |
| Intégration continue et chaîne d'approvisionnement | Absent | Aucun pipeline, aucun scan de dépendances, de secrets ou de vulnérabilités, pas de SBOM |
| Cohérence de la progression | Élevée | Enchaînement logique socle, instrumentation, alerting, sondes, avec recette validée à chaque étape et journal tenu à jour |

## Standards d'ingénierie et d'observabilité

Sur le cœur du sujet, l'observabilité, le travail est aligné sur l'état de l'art. La collecte repose sur OpenTelemetry et un Collector pivot qui reçoit toute la télémétrie avant de la router, ce qui évite le couplage direct des applications aux backends. Les métriques dérivées des traces (spanmetrics et servicegraph) sont calculées au Collector avant l'échantillonnage par la queue, si bien que les taux d'erreur et les latences restent exacts même quand la majorité des traces rapides est écartée. Les alertes suivent la méthode RED sur ces mêmes métriques, les objectifs de niveau de service sont décrits comme du code avec Sloth et génèrent des alertes multi burn rate, et la corrélation métrique vers trace vers log vers profil est câblée dans les datasources Grafana. La discipline de cardinalité est respectée : les identifiants à forte cardinalité vont en attributs de span, jamais en labels de métrique. La surveillance externe adopte le bon réflexe avec une sonde Uptime Kuma pensée pour être hébergée hors de l'infrastructure, seule capable d'alerter quand le serveur surveillé tombe.

Ce sont des choix que l'on attend d'une équipe expérimentée. Les écarts par rapport aux bonnes pratiques sont limités et concernent surtout l'industrialisation. Le conteneur du frontend de démonstration s'exécute en root, faute de directive `USER` dans son image nginx, là où le service Django tourne correctement en utilisateur non privilégié. Le verrou de dépendances du frontend n'est pas versionné, ce qui nuit à la reproductibilité des builds. Enfin, aucune analyse de la chaîne d'approvisionnement (dépendances, images) n'est en place, ce qui est cohérent avec l'absence d'intégration continue mais reste un manque pour un usage professionnel.

## Documentation

La documentation est l'un des points forts. Le dépôt s'ouvre sur un triptyque de gouvernance, `README.md` puis `CONTEXT.md` puis `MEMORY.md`, dont l'ordre de lecture est imposé et qui sépare proprement les règles, le contexte durable et l'état vivant. Le document maître d'architecture couvre le quoi et le pourquoi de chaque technologie, avec des comparatifs et le code de référence du socle. Un document compagnon traite la chaîne d'intégration et de déploiement. Le guide d'utilisation de la plateforme joue le rôle de référence d'intégration pour les projets consommateurs, avec prérequis, concepts, justification de chaque brique et points d'entrée. Chaque composant exécutable possède son README. Le journal de `MEMORY.md` tient lieu de changelog daté et il est réellement à jour, y compris des incidents rencontrés et de leur résolution.

Pour une application professionnelle, il subsiste toutefois des absences qui comptent. Il n'existe pas de fichier `SECURITY.md` ni de modèle de menace formel : les mesures de sécurité sont décrites en section 7.4 du document maître, mais comme une cible de conception, pas comme une analyse de menaces ni une politique. Il n'y a pas de runbooks d'exploitation au sens strict, c'est à dire de procédures de réponse par alerte du type « quand HighErrorRate se déclenche, voici les étapes de diagnostic et de remédiation » ; on trouve une procédure de démarrage et un scénario d'incident narratif, ce qui est utile mais différent. Les décisions d'architecture sont tracées de façon légère dans `CONTEXT.md` et `MEMORY.md`, ce qui est appréciable, mais pas sous la forme d'ADR numérotés et autoportants. Un fichier `CONTRIBUTING` explicite et une politique de classification des données feraient également partie d'un socle documentaire complet. Ces manques n'enlèvent rien à la qualité de l'existant ; ils marquent la distance entre une très bonne documentation d'ingénierie et un dossier documentaire prêt pour un audit.

## Sécurité, posture réelle

C'est ici que l'écart entre l'ambition professionnelle et l'état courant est le plus net, et c'est parfaitement assumé dans le dépôt, qui affiche des avertissements « configuration de laboratoire » dans le `README` du socle et en tête du fichier compose.

Concrètement, la télémétrie et les interfaces circulent en clair. Le Collector reçoit l'OTLP sur les ports 4317 et 4318 sans authentification, les échanges internes vers Tempo et depuis Alloy sont explicitement en `insecure: true`, et treize ports sont publiés sur l'hôte sans terminaison TLS, dont deux pour la démonstration en profil opt-in. Côté authentification, Grafana et GlitchTip disposent d'un mot de passe fourni par variable d'environnement, mais Prometheus, Loki (`auth_enabled: false`), Tempo et Alertmanager n'ont aucune authentification propre et reposent sur l'hypothèse d'un réseau privé. Le récepteur Faro d'Alloy accepte toutes les origines. Il n'y a pas de chiffrement au repos sur les volumes ni sur la base Postgres de GlitchTip. La sauvegarde et la reprise sont décrites en section 7.5 mais ne sont pas automatisées.

Ce qui est en place et mérite d'être souligné : la gestion des secrets est saine pour ce stade. Le `.gitignore` exclut les fichiers d'environnement et le répertoire de secrets d'Alertmanager, seuls des fichiers d'exemple avec des valeurs neutres sont versionnés, le webhook Slack est lu depuis un fichier hors dépôt, et aucun secret en clair n'a été trouvé dans l'arbre versionné. Un incident de secret a d'ailleurs déjà eu lieu, a été détecté par la protection GitHub, corrigé et consigné. Les images portent des tags de version fixes, sans épinglage par empreinte et pour trois d'entre elles au tag majeur seulement, et les dépendances Python sont épinglées au correctif.

Il reste une lacune de sécurité directement liée à cet incident : les hooks locaux ne scannent pas les secrets. Ils protègent les branches, ce qui est utile, mais un outil comme gitleaks en pre-commit attraperait localement ce que seule la protection distante a arrêté la dernière fois. C'est une recommandation à faible coût et à fort effet, déjà notée dans le journal.

En résumé, la posture de sécurité actuelle est celle d'un laboratoire correctement hygiéné, pas celle d'une application exposable. Le durcissement (reverse proxy TLS, authentification et SSO Grafana, ports non publiés, secrets gérés par un coffre) constitue le lot 9 du backlog et n'a pas commencé.

## Position vis à vis de SOC 2

Il faut d'abord cadrer la question, car elle est souvent mal posée. SOC 2 n'est pas une propriété d'un code ou d'un dépôt. C'est une attestation produite par un cabinet d'audit indépendant sur les contrôles d'une organisation autour d'un système, évalués au regard des Trust Services Criteria, et, pour un rapport de type II, sur leur fonctionnement effectif observé pendant une période de plusieurs mois. Une partie des exigences est organisationnelle et sort entièrement du périmètre de ce dépôt : politiques, évaluation des risques, gestion des accès du personnel, gestion des fournisseurs, réponse à incident formalisée, collecte de preuves dans la durée.

Cela dit, on peut honnêtement situer le projet par rapport aux critères communs de sécurité. Le point remarquable, et positif, est qu'une plateforme d'observabilité est précisément un des contrôles que SOC 2 attend au titre de la surveillance des opérations, la détection des anomalies et l'identification des incidents. En construisant cette plateforme et son alerting, le projet pose une brique réelle de ce que demande le critère consacré aux opérations du système. La gestion du changement est également bien pensée sur le papier, avec des branches protégées, des revues obligatoires et un historique linéaire visés par les règles Git.

Mais les contrôles techniques que recherche un auditeur sont, pour l'essentiel, absents en l'état. Le contrôle des accès logiques est faible, sans authentification généralisée, sans chiffrement en transit ni au repos, sans gestion fine des droits. La gestion des vulnérabilités n'existe pas, faute de scan de dépendances et d'images. La gestion du changement, bien que conçue, n'est pas encore appliquée côté GitHub, où les protections de branches et l'exigence d'intégration continue verte restent à activer. Il n'y a ni évaluation de risque ni politiques écrites. La conclusion est donc sans ambiguïté : en l'état, le projet ne satisferait pas un audit SOC 2, et l'atteindre suppose un chantier dédié qui combine le durcissement technique déjà prévu et un volet organisationnel qui n'est pas encore ouvert. La bonne nouvelle est que plusieurs lots du backlog, une fois réalisés, alimenteront directement les critères techniques.

## Cohérence de la progression

La trajectoire est cohérente et bien tenue. L'ordre suivi, socle puis recette, puis instrumentation du backend et du frontend, puis alerting et SLO, puis sondes externes, est logique et chaque étape a été validée de bout en bout avant de passer à la suivante, avec une recette réelle sur la machine de l'utilisateur et une trace écrite dans le journal. La gouvernance est disciplinée, les incidents sont consignés, la reprise de contexte est facile. Sur la méthode, il y a peu à redire.

Deux réserves méritent d'être posées, non pour contredire le plan mais pour éclairer une décision. D'une part, la sécurité et l'intégration continue arrivent en fin de parcours, aux lots 9 et 10. C'est défendable pour un laboratoire qui cherche d'abord à démontrer la valeur, mais cela signifie que le système grossit sans filet pendant tout ce temps et que la mise en conformité se fera d'un bloc, ce qui est plus risqué qu'un durcissement introduit tôt et par petites touches. D'autre part, les règles de gouvernance imposent des protections GitHub et une intégration continue verte qui ne sont pas encore effectives : le cadre existe, son application distante est en retard sur son ambition. Ce n'est pas une incohérence, c'est un écart entre le texte et l'exécution qu'il vaut mieux résorber avant qu'il ne s'installe.

## Registre des écarts priorisés

Le tableau ordonne les manques par priorité, avec une estimation d'effort. Il vaut feuille de route de mise à niveau vers un usage professionnel.

| Priorité | Écart | Impact | Effort | Rattachement backlog |
|---|---|---|---|---|
| 1 | Scan de secrets local (gitleaks en pre-commit) | Empêche la fuite de secrets à la source, incident déjà survenu | Faible | Enabler, hors backlog actuel |
| 2 | Activer les protections de branches GitHub et l'exigence de revue (R8) | Rend la gouvernance réellement opposable | Faible | Gouvernance, à faire maintenant |
| 3 | Durcissement réseau et TLS (reverse proxy, ports non publiés) | Condition de toute exposition hors poste local | Moyen | Lot 9 |
| 4 | Authentification et SSO sur Grafana, cloisonnement des backends | Contrôle des accès logiques, exigence SOC 2 CC6 | Moyen | Lot 9 |
| 5 | Intégration continue avec tests, scan de dépendances et d'images, SBOM | Qualité et gestion des vulnérabilités | Moyen à élevé | Lot 10 |
| 6 | Conteneur frontend en non-root et verrou de dépendances versionné | Réduction de surface, reproductibilité | Faible | Correctif ciblé |
| 7 | Fichier SECURITY.md, modèle de menace, runbooks d'incident | Dossier documentaire de sécurité | Moyen | Documentation |
| 8 | Chiffrement au repos et sauvegarde automatisée | Confidentialité et reprise | Moyen | Lots 9 et exploitation |
| 9 | Évaluation de risque et politiques écrites, si SOC 2 est un objectif réel | Volet organisationnel de la conformité | Élevé | Chantier dédié |

Sur l'ordonnancement, les priorités 1 et 2 sont des gains immédiats et peu coûteux qui referment l'écart le plus visible entre les règles affichées et leur application. Elles peuvent être traitées avant de poursuivre la phase 4 du backlog. Le reste suit l'ordre déjà prévu, à ceci près qu'il serait sain d'introduire le durcissement un peu plus tôt que le lot 9 si une exposition, même limitée, est envisagée à court terme.

## Conclusion

Le travail accompli est de bonne facture et la méthode est saine. Pour une plateforme d'observabilité de laboratoire, les standards d'ingénierie sont respectés, la documentation est riche et à jour, la gouvernance est réfléchie et la progression est cohérente. La franchise impose toutefois de distinguer deux plans. Sur le plan de l'observabilité et de la conduite de projet, le niveau est élevé. Sur le plan de la sécurité d'exploitation et de la conformité, le projet est au début du chemin : les mécanismes ne sont pas encore en place, aucun n'est en place par accident, tout est planifié, mais rien n'est fait. Répondre oui aux questions de sécurité et de conformité SOC 2 supposera d'exécuter le durcissement, d'activer réellement la gouvernance distante, de mettre en place l'intégration continue avec ses contrôles, et, si SOC 2 est visé pour de bon, d'ouvrir le volet organisationnel correspondant. Les priorités 1 et 2 du registre sont le meilleur point de départ, car elles coûtent peu et rapprochent aussitôt le dépôt de ce qu'il affiche déjà vouloir être.

## Suite donnée (mise à jour du 20 juillet 2026, après-midi)

Le plan de correction issu de ce bilan a été exécuté le jour même. Voici l'état du registre des écarts ci-dessus, mis à jour.

| Priorité | Écart | État |
|---|---|---|
| 1 | Scan de secrets local (gitleaks en pre-commit) | ✅ Fait (S1) — `.githooks/pre-commit` + `.gitleaks.toml`, doublé en CI. |
| 2 | Protections de branches GitHub (R8) | ✅ Fait — `develop` et `main` protégées : MR obligatoire, CI verte requise, historique linéaire, `enforce_admins`. |
| 3 | Durcissement réseau et TLS (reverse proxy, ports non publiés) | ✅ Fait (S3) — surcouche `observability/hardening/` : Caddy TLS, ports internes dépubliés. |
| 4 | Authentification et SSO Grafana, cloisonnement des backends | 🟡 Cadre livré — backends dépubliés, joignables via Grafana seul ; SSO et auth restent une action de déploiement, documentée dans `hardening/README.md`. |
| 5 | CI avec tests, scan de dépendances et d'images, SBOM | ✅ Fait (S4) — `.github/workflows/ci.yml` : gitleaks, lint, build, Trivy, SBOM Syft. La CI a d'ailleurs immédiatement détecté et fait corriger un CVE critique (Django). |
| 6 | Conteneur frontend non-root et verrou de dépendances versionné | ✅ Fait (S1) — `units-webapp` en nginx non-root, `package-lock.json` versionné (`npm ci`). |
| 7 | SECURITY.md, modèle de menace, runbooks d'incident | ✅ Fait (S2) — `SECURITY.md`, `docs/Modele_Menace.md` (STRIDE), `docs/Runbooks_Incident.md`. |
| 8 | Chiffrement au repos et sauvegarde automatisée | 🟡 Partiel — `hardening/backup.sh` livré, chiffrement au repos documenté au niveau hôte ; planification cron et choix du chiffrement restent des actions d'exploitation. |
| 9 | Évaluation de risque et politiques écrites (volet organisationnel) | ⚪ Ouvert, volontairement hors périmètre technique. |

Sur les neuf écarts, six sont entièrement soldés, deux le sont sur leur part outillée (le reste relevant de décisions d'exploitation), et seul le volet organisationnel demeure, par choix. La réponse aux questions de sécurité a donc nettement évolué depuis l'instantané du matin : la plateforme dispose désormais des mécanismes techniques de base ; il reste à les activer pleinement lors d'un déploiement réel.

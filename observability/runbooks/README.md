# Runbooks — que faire quand ça sonne

Le §8.4 du DAT pose la règle : *« chaque alerte a un runbook (fiche « que faire ») liée dans
l'annotation ; toute alerte qui sonne sans action possible est supprimée ou reclassée »*. Ce
fichier est la cible de ces liens. L'annotation `runbook_url` de chaque règle pointe vers la
section correspondante.

Une fiche tient en trois questions : **ce que ça veut dire**, **ce qu'on regarde**, **ce qu'on
fait**. Si une fiche ne peut pas répondre à la troisième, l'alerte n'a rien à faire en astreinte.

---

## HighErrorRate

**Ce que ça veut dire.** Plus de 5 % des spans d'un service portent `STATUS_CODE_ERROR` depuis
cinq minutes. Mesuré sur 100 % du trafic, avant échantillonnage : le chiffre n'est pas une
estimation.

**Ce qu'on regarde.** Dashboard *Par service*, sélecteur sur le service en cause → panneau
« Erreurs par opération » pour savoir si l'erreur est diffuse ou concentrée sur une opération.
Puis les journaux du même écran, filtrés sur le niveau erreur.

**Ce qu'on fait.** Une opération unique en cause → dépendance de cette opération (base, courtier,
service appelé). Erreurs diffuses → le service lui-même, ou son démarrage récent. Cliquer un
exemplar mène à la trace ; le `trace_id` du journal mène à la même.

## HighLatencyP99

**Ce que ça veut dire.** Le P99 d'un service dépasse 500 ms depuis dix minutes. Le P99 attrape ce
que la moyenne cache : un utilisateur sur cent attend trop.

**Ce qu'on regarde.** *Par service* → « Opérations les plus lentes ». Comparer au P95 du même
écran : un P99 seul très haut désigne une queue, pas une dégradation générale.

**Ce qu'on fait.** Vérifier les verrous et les requêtes lentes (dashboard *PostgreSQL*) avant de
soupçonner le code. Un import massif concurrent est la cause la plus fréquente.

## BudgetLatenceDepasse

**Ce que ça veut dire.** Une opération de lecture dépasse 2 s au P95 depuis quinze minutes —
budget ENF-01 épuisé.

**Ce qu'on regarde.** *Par service* → l'opération nommée dans l'alerte. Suivre un exemplar
jusqu'à la trace Tempo pour voir où le temps part.

**Ce qu'on fait.** Le temps est dans la base → *PostgreSQL* (verrous, requêtes lentes). Il est
réparti sur plusieurs appels → chercher un N+1. Il est dans un seul span applicatif → profil
Pyroscope du span.

## BudgetLatenceEcritureDepasse

**Ce que ça veut dire.** Une écriture dépasse 500 ms au P95 depuis quinze minutes — budget
ENF-02, plus serré que la lecture parce que l'utilisateur attend le résultat de son geste.

**Ce qu'on regarde.** Les verrous d'abord : dashboard *PostgreSQL*, panneau « Verrous détenus »
et « Transaction la plus longue ».

**Ce qu'on fait.** Une transaction longue bloque les écritures concurrentes et fait enfler la
base. L'identifier et la terminer prime sur toute optimisation de code.

## DisqueBientotPlein

**Ce que ça veut dire.** Un système de fichiers dépasse 80 % depuis dix minutes. On planifie, on
ne court pas encore.

**Ce qu'on regarde.** *Vue d'ensemble* → « Remplissage des systèmes de fichiers ». Les gros
consommateurs habituels sont la rétention Prometheus (15 j), les blocs Tempo, les segments Loki.

**Ce qu'on fait.** Réduire une rétention, ou étendre le volume. Noter que `node-exporter` embarqué
mesure le **conteneur** : pour l'espace réel de la machine, regarder l'hôte.

## DisquePresquePlein

**Ce que ça veut dire.** Plus de 90 %. Intervention immédiate.

**Ce qu'on regarde.** Le même panneau, et l'hôte directement.

**Ce qu'on fait.** Libérer de l'espace tout de suite. Au-delà de 95 %, PostgreSQL refuse les
écritures et la plateforme perd ses propres données d'observation : on devient aveugle pendant
la panne, ce qui est le pire moment.

## CibleInjoignable

**Ce que ça veut dire.** Prometheus n'obtient plus de métriques d'une cible depuis deux minutes.

**Ce qu'on regarde.** *Prometheus → Status → Targets*, pour lire l'erreur exacte de collecte.
Puis *Vue d'ensemble* → « Cibles injoignables ».

**Ce qu'on fait.** **Compter d'abord.** Une seule cible tombée → le composant. Toutes en même
temps → le réseau ou la plateforme elle-même, et les autres alertes de cette salve sont des
conséquences, pas des causes.

## ProbeDown

**Ce que ça veut dire.** Une sonde HTTP en boîte noire échoue depuis deux minutes. Contrairement
à `CibleInjoignable`, la sonde teste le service *comme un client*, sans instrumentation.

**Ce qu'on regarde.** Le point de vue compte : cette sonde part de l'intérieur de la plateforme.
Croiser avec Uptime Kuma, hébergée hors infrastructure, qui seule voit une coupure entre le
public et nous.

**Ce qu'on fait.** Sonde interne KO et Uptime Kuma OK → problème réseau interne. Les deux KO →
le service est réellement tombé.

## ProbeSlow

**Ce que ça veut dire.** Une sonde met plus d'une seconde à répondre depuis cinq minutes. Pas
encore une panne, déjà une dégradation.

**Ce qu'on regarde.** Le RED du même service : la lenteur est-elle vue aussi par les métriques
applicatives, ou seulement par la sonde ?

**Ce qu'on fait.** Vue seulement par la sonde → suspecter le chemin réseau ou le proxy. Vue par
les deux → traiter comme une latence applicative.

## ProbeSSLCertExpiringSoon

**Ce que ça veut dire.** Un certificat TLS expire dans moins de quinze jours.

**Ce qu'on regarde.** L'`instance` de l'alerte donne l'URL concernée.

**Ce qu'on fait.** Renouveler avant expiration. Quinze jours laissent de la marge : cette alerte
ne doit jamais devenir une urgence. Si elle sonne en boucle sans action, le renouvellement
automatique est cassé — c'est lui qu'il faut réparer, pas le certificat.

## FileDeRebutNonVide

**Ce que ça veut dire.** Au moins un message a épuisé toutes ses reprises et attend en file de
rebut. Une donnée métier est perdue tant que personne ne la rejoue. Le seuil est 1, pas 10 :
au-delà de zéro, quelque chose n'est pas arrivé.

**Ce qu'on regarde.** Dashboard *RabbitMQ et événements* → « Rebut par file ». Lire l'en-tête
`x-death` du message : il porte le motif et le nombre de tentatives.

**Ce qu'on fait.** Corriger la cause, **puis** rejouer la file. Ne jamais purger sans avoir lu :
purger efface la seule trace de ce qui a échoué.

## EchecsAuthentificationAnormaux

**Ce que ça veut dire.** Plus de vingt échecs de connexion en cinq minutes. Au-delà, l'hypothèse
de l'erreur de saisie ne tient plus.

**Ce qu'on regarde.** Les journaux Keycloak : chercher si les échecs viennent d'une adresse
source unique, ou visent un compte unique.

**Ce qu'on fait.** Source unique → bloquer l'adresse. Compte unique visé depuis plusieurs
sources → prévenir la personne et forcer le renouvellement. Répartition diffuse → vérifier
qu'un déploiement récent n'a pas cassé le flux d'authentification : la panne se déguise
volontiers en attaque.

## SauvegardeAbsente

**Ce que ça veut dire.** Aucune sauvegarde n'a abouti depuis plus de 26 heures. Le seuil laisse
deux heures de glissement à un travail quotidien.

**Ce qu'on regarde.** Le travail planifié et ses journaux. La métrique vient d'un fichier `.prom`
déposé dans le répertoire textfile de `node-exporter` : si le fichier n'est plus écrit, c'est le
travail qui a échoué, pas la mesure.

**Ce qu'on fait.** Réparer le travail planifié **avant** de lancer une sauvegarde à la main. Une
sauvegarde manuelle réussie éteint l'alerte sans corriger la cause, et masque la panne jusqu'au
prochain incident réel — celui où l'on aura besoin de la sauvegarde.

# Politique de sécurité

Ce document décrit comment signaler une vulnérabilité, ce que couvre le projet, et l'état réel de sa sécurité. Il s'adresse aux personnes qui déploient ou font évoluer la plateforme d'observabilité et ses démonstrations.

## Signaler une vulnérabilité

Ne créez pas de ticket public pour une faille de sécurité. Utilisez le signalement privé de vulnérabilité de GitHub sur le dépôt, ou contactez directement le mainteneur. Décrivez le composant concerné, les étapes de reproduction, l'impact estimé et, si possible, une piste de correction.

Le mainteneur accuse réception sous quelques jours ouvrés, évalue la gravité, corrige sur une branche dédiée selon les règles Git du dépôt, puis publie le correctif. Nous privilégions une divulgation responsable et coordonnée, sans délai imposé mais dans un esprit de correction rapide.

## Périmètre

Sont couverts le socle d'observabilité (`observability/`), ses fichiers de configuration, les démonstrations (`demo/units-service`, `demo/units-webapp`), les hooks et scripts de gouvernance, et la documentation. Sont hors périmètre les vulnérabilités propres aux images et bibliothèques tierces, qui relèvent de leurs éditeurs respectifs, même si nous nous efforçons de les tenir à jour.

## Posture de sécurité actuelle

La plateforme est aujourd'hui dans une configuration de laboratoire, assumée et documentée. Cela signifie, en clair, qu'elle n'est pas prête pour une exposition sur un réseau non maîtrisé. Les points suivants sont volontaires à ce stade et font l'objet du lot de durcissement à venir.

Les échanges internes ne sont pas chiffrés, il n'y a pas de terminaison TLS. La plupart des services d'observabilité, dont Prometheus, Loki, Tempo et Alertmanager, n'ont pas d'authentification propre et supposent un réseau privé. Les ports sont publiés sur l'hôte. Le point d'entrée OTLP du Collector accepte la télémétrie sans authentification. Le récepteur des données du navigateur accepte toutes les origines. Il n'y a pas de chiffrement au repos ni de sauvegarde automatisée.

Le détail de ces écarts et l'ordre pour les combler figurent dans `docs/Bilan_Maturite_Conformite.md` et dans le modèle de menace `docs/Modele_Menace.md`. Le durcissement complet, à savoir un reverse proxy TLS, l'authentification des services, le cloisonnement réseau, le chiffrement au repos et la sauvegarde, est planifié avant toute mise en production. Tant qu'il n'est pas réalisé, ne déployez la plateforme que sur un réseau strictement privé ou une machine locale.

## Gestion des secrets

Aucun secret ne doit être versionné. Les variables sensibles vivent dans un fichier `.env` local, exclu par `.gitignore`, dérivé de `observability/.env.example`. Le webhook Slack d'Alertmanager est lu depuis `observability/alertmanager/secrets/slack_webhook_url`, lui aussi hors dépôt, seul un exemple neutre étant versionné.

Le hook `pre-commit` exécute `gitleaks` sur les changements indexés et bloque le commit si un secret est détecté. La configuration `.gitleaks.toml` hérite des règles par défaut et autorise uniquement les fichiers d'exemple. Installez `gitleaks` localement pour que cette protection soit active. Un scan équivalent en intégration continue est prévu.

Si un secret a été exposé par erreur, considérez le comme compromis, révoquez le et générez en un nouveau, puis purgez le de l'historique concerné avant toute publication.

## Bonnes pratiques pour un déploiement

Renseignez des mots de passe forts et propres à chaque environnement pour Grafana et GlitchTip, ne réutilisez jamais les valeurs d'exemple. Avant toute exposition, placez la plateforme derrière un reverse proxy assurant le TLS et l'authentification, ne publiez pas les ports en clair, et restreignez les origines acceptées par le récepteur du navigateur au seul domaine de votre application. Faites tourner les conteneurs applicatifs sans privilège, comme le font déjà les deux démonstrations. Renouvelez régulièrement les secrets.

## Dépendances et chaîne d'approvisionnement

Les images des conteneurs sont épinglées à une version fixe, sans balise flottante. Les dépendances Python des démonstrations sont épinglées au correctif, et le frontend utilise un verrou de dépendances afin d'obtenir des builds reproductibles. L'analyse automatisée des dépendances et des images, ainsi qu'un inventaire logiciel, sont prévus en intégration continue.

## Versions supportées

Le développement se fait sur la branche `develop`, intégrée dans `main` pour les livraisons. Les correctifs de sécurité s'appliquent à l'état courant de `develop`.

# Astreinte avec OneUptime (hors infra)

Alertmanager sait grouper, router et dédupliquer les alertes, mais il ne gère ni la rotation d'astreinte, ni l'escalade, ni l'appel téléphonique quand personne n'accuse réception. C'est le rôle d'un outil de garde. La cible du projet est OneUptime, choisi parce que Grafana OnCall a été archivé le 24 mars 2026 ; il ne faut donc pas le réintroduire. OneUptime reçoit les alertes de niveau page, ouvre un incident, prévient la personne d'astreinte et remonte la chaîne d'escalade si le silence persiste.

## Pourquoi hors infrastructure

Comme la sonde Uptime Kuma, l'outil d'astreinte doit vivre sur une machine indépendante de la plateforme surveillée. Le raisonnement est le même : si le serveur d'observabilité tombe, Alertmanager tombe avec lui, mais c'est justement le moment où il faut réveiller quelqu'un. Un outil d'astreinte hébergé sur le même serveur serait aveugle à la panne la plus grave. Hébergez donc OneUptime ailleurs, idéalement chez un autre fournisseur ou dans une autre région, ou utilisez son offre hébergée.

Les deux briques hors infrastructure sont complémentaires et ne font pas double emploi. Uptime Kuma regarde la plateforme du dehors et détecte l'indisponibilité. OneUptime prend le relais côté humain : il transforme une alerte en incident suivi, avec une personne responsable et une escalade. L'une voit, l'autre fait agir.

## Déploiement

Deux options. La plus simple est l'offre hébergée de OneUptime, qui évite d'exploiter une machine de plus. Sinon, auto-hébergez OneUptime sur une machine séparée en suivant leur documentation officielle d'auto-hébergement, qui fournit son propre assemblage de conteneurs. Ce dépôt ne duplique pas cet assemblage, qui évolue avec le produit ; référez vous à la source officielle pour rester à jour.

## Configuration côté OneUptime

Créez un projet. Définissez d'abord la garde : une politique d'astreinte avec la rotation des personnes, puis une politique d'escalade qui précise qui est prévenu, par quel canal, et au bout de combien de temps sans accusé de réception on passe à l'échelon suivant. C'est ce mécanisme, absent d'Alertmanager, qui justifie l'outil.

Créez ensuite l'entrée qui reçoit les alertes d'Alertmanager, via l'intégration entrante prévue à cet effet. Vous obtenez une URL de webhook. Rattachez cette entrée à votre politique d'escalade, afin qu'une alerte reçue déclenche réellement la garde.

## Câblage avec Alertmanager

Le routage est déjà en place dans `../alertmanager/alertmanager.yml` : les alertes de niveau page partent vers le receiver `page-oncall`, qui notifie à la fois Slack, pour la visibilité de l'équipe, et OneUptime, pour la garde. Les alertes de niveau ticket ne vont qu'à Slack.

Il ne reste qu'à fournir l'URL du webhook. Copiez le fichier d'exemple en retirant le suffixe, puis remplacez son contenu par l'URL réelle, sur une seule ligne :

```bash
cp alertmanager/secrets/oneuptime_webhook_url.example alertmanager/secrets/oneuptime_webhook_url
# éditez le fichier : il ne doit contenir QUE l'URL, rien d'autre
```

Ce fichier reste hors Git, comme le webhook Slack : `.gitignore` exclut tout le dossier `secrets/` sauf les fichiers d'exemple. Rechargez ensuite Alertmanager pour prendre en compte la nouvelle configuration.

## Vérification

Provoquez une alerte de niveau page, par exemple en générant des erreurs sur la démo pour faire sonner `HighErrorRate`. Vous devez voir l'alerte arriver dans Slack comme avant, et en parallèle un incident s'ouvrir dans OneUptime, qui déclenche la notification de la personne d'astreinte selon la politique d'escalade. Coupez ensuite la source d'erreur et vérifiez que la résolution est bien propagée, puisque le receiver envoie aussi les résolutions.

## Points de vigilance

OneUptime ne remplace pas la supervision, il la prolonge côté humain. Ne routez vers lui que les alertes qui méritent un réveil, c'est à dire le niveau page, pour ne pas user la garde avec du bruit. Gardez l'outil sur une machine indépendante, testez la chaîne d'escalade de bout en bout de temps en temps, et rappelez vous que Grafana OnCall, archivé, ne doit pas être réintroduit à sa place.

# Runbooks de réponse aux alertes

Ce document donne, pour chaque alerte de la plateforme, la marche à suivre : ce qu'elle signifie, comment diagnostiquer, comment remédier et quand escalader. Il s'appuie sur la force de la plateforme, la corrélation des signaux : depuis presque toute alerte, on descend d'un symptôme jusqu'à sa cause en quelques clics dans Grafana.

## Triage général

Quel que soit le déclenchement, commencez par la même séquence. Ouvrez Alertmanager sur le port 9093 pour voir l'alerte, ses étiquettes et son groupe. Ouvrez Grafana sur le port 3000, allez sur l'écran RED du service concerné et regardez les trois courbes, débit, taux d'erreur et latence, pour situer le problème. À partir d'un point suspect sur une courbe, suivez l'exemplar vers une trace, puis de la trace vers ses logs, puis vers GlitchTip si une exception est en jeu. Cette descente est la méthode de base de tous les runbooks ci-dessous.

Les requêtes proposées s'exécutent dans Grafana, en explorateur, sur la source indiquée. Adaptez le nom du service si nécessaire.

## HighErrorRate

Gravité page. L'alerte se déclenche quand plus de cinq pour cent des spans d'un service sont en erreur sur cinq minutes. C'est un symptôme utilisateur direct : une part significative des requêtes échoue.

Diagnostic. Confirmez le taux et le service avec, sur Prometheus, `sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m])) / sum by (service_name) (rate(traces_span_metrics_calls_total[5m]))`. Sur l'écran RED, cliquez un exemplar de la courbe d'erreur pour ouvrir une trace en échec, ou cherchez dans Tempo les traces en erreur du service avec `{ resource.service.name = "units-service" && status = error }`. Depuis le span fautif, ouvrez ses logs pour lire le message d'erreur, puis vérifiez GlitchTip, qui regroupe les exceptions avec leur pile d'appel et la version concernée.

Remédiation. Si l'erreur a suivi un déploiement, revenez à la version précédente en priorité, puis corrigez à froid. Si elle vient d'une dépendance en panne, traitez la dépendance. Une fois la correction déployée, vérifiez le retour du taux d'erreur sous le seuil sur l'écran RED.

Escalade. Comme c'est une alerte de niveau page, si le taux ne redescend pas rapidement ou si l'origine reste inconnue, sollicitez la personne d'astreinte. L'escalade téléphonique via OneUptime est prévue au backlog.

## HighLatencyP99

Gravité ticket. L'alerte se déclenche quand le quatre-vingt-dix-neuvième centile de latence dépasse cinq cents millisecondes sur dix minutes. Le service répond, mais trop lentement pour une part des utilisateurs.

Diagnostic. Visualisez le centile avec `histogram_quantile(0.99, sum by (le, service_name) (rate(traces_span_metrics_duration_milliseconds_bucket[5m])))`. Dans Tempo, ouvrez les traces les plus lentes du service avec `{ resource.service.name = "units-service" && duration > 500ms }` et repérez, dans la trace, le span où le temps se concentre. Si le profilage continu est en place, descendez de la trace vers le profil pour identifier la fonction coûteuse.

Remédiation. Selon la cause, optimisez le point chaud, ajoutez de la mise en cache, ou augmentez les ressources. Vérifiez le retour du centile sous le seuil.

Escalade. Alerte de niveau ticket, à traiter en heures ouvrées sauf dégradation qui se transforme en taux d'erreur.

## UnitsServiceAvailability

Gravité page ou ticket selon la fenêtre. Cette alerte, générée à partir de l'objectif de service, se déclenche quand le budget d'erreur se consomme trop vite. La variante page correspond à une consommation rapide sur fenêtres courte et longue, la variante ticket à une consommation plus lente.

Diagnostic. Une consommation rapide accompagne presque toujours un pic d'erreurs, donc traitez d'abord comme un HighErrorRate et suivez le même chemin de corrélation. Regardez l'écran de l'objectif pour voir la part de budget déjà consommée et le rythme de consommation.

Remédiation. Arrêtez l'hémorragie en corrigeant la cause des erreurs, exactement comme pour HighErrorRate. Si le budget d'erreur est épuisé, gelez les déploiements non essentiels jusqu'au retour sous l'objectif, afin de ne pas aggraver la situation.

Escalade. La variante page réveille l'astreinte, la variante ticket alimente le suivi. Rappelez vous que cette alerte à double fenêtre est conçue pour ne pas sonner à tort, donc un déclenchement mérite attention.

## ProbeDown

Gravité page. Une sonde en boîte noire n'arrive plus à joindre une cible surveillée. Vu de l'extérieur, un endpoint est indisponible.

Diagnostic. Identifiez la cible en cause par l'étiquette d'instance de l'alerte. Vérifiez que le service tourne, par exemple avec l'état des conteneurs, puis lisez ses logs. Confirmez la valeur avec `probe_success` sur Prometheus, qui doit valoir zéro pour cette cible. Attention à un faux positif classique : si la configuration des sondes a changé récemment sans que l'exporteur de sondes ait été redémarré, celui ci répond en erreur et fait chuter toutes les sondes d'un coup. Dans ce cas, redémarrez l'exporteur de sondes, ce n'est pas une vraie panne.

Remédiation. Si le service est réellement à terre, redémarrez le et vérifiez ses dépendances. Une fois debout, la sonde repasse au vert en moins d'une minute.

Point important. Si c'est le serveur entier qui est tombé, Prometheus et Alertmanager sont tombés avec lui et n'enverront rien. La source de vérité devient alors la sonde externe Uptime Kuma, hébergée hors infrastructure, qui vous préviendra indépendamment.

Escalade. Alerte de niveau page. Une indisponibilité externe qui dure appelle l'astreinte sans délai.

## ProbeSlow

Gravité ticket. La sonde répond, mais met plus d'une seconde, sur cinq minutes. C'est un signe avant coureur de dégradation.

Diagnostic. Regardez `probe_duration_seconds` pour la cible concernée, et croisez avec l'état de la machine hôte via le tableau de bord Node Exporter, en particulier la saturation processeur, mémoire et disque, selon la méthode USE.

Remédiation. Traitez la cause de la lenteur, ressource saturée ou traitement coûteux, avant qu'elle ne devienne une indisponibilité.

Escalade. Niveau ticket, à traiter en heures ouvrées.

## ProbeSSLCertExpiringSoon

Gravité ticket. Le certificat TLS d'une cible surveillée expire dans moins de quinze jours. Cette alerte ne concerne que les cibles en HTTPS, donc les surfaces publiques une fois la plateforme exposée derrière un proxy TLS.

Diagnostic. Identifiez la cible et vérifiez la date d'expiration réelle du certificat.

Remédiation. Renouvelez le certificat. Avec une émission automatique par Let's Encrypt via le reverse proxy, vérifiez pourquoi le renouvellement automatique n'a pas eu lieu, plutôt que de renouveler à la main.

Escalade. Niveau ticket, mais ne laissez pas traîner : un certificat expiré coupe l'accès à tous les clients.

## Panne de la plateforme elle-même

Si plus aucune alerte n'arrive et que Grafana est injoignable, c'est peut être la plateforme qui est tombée. Ne comptez pas sur la supervision embarquée dans ce cas, elle est hors service en même temps que le reste. Fiez vous à la sonde externe Uptime Kuma et à la supervision de la machine hôte. Vérifiez l'état du serveur et du moteur de conteneurs, puis relancez la pile. Une fois la plateforme revenue, contrôlez que les backends sont sains et que la collecte reprend, en suivant les étapes de mise en route du socle.

## Escalade et astreinte

Aujourd'hui, les alertes arrivent dans le canal Slack dédié via Alertmanager, et l'astreinte se fait à la main. L'escalade automatique avec accusé de réception et bascule vers le téléphone est prévue au backlog avec OneUptime, sur une machine séparée. En attendant, toute alerte de niveau page non résolue rapidement doit être portée à la personne responsable par le canal le plus direct.

"""La chaîne d'alerte livre-t-elle réellement ? (constat C-042)

Le défaut d'origine ne se voyait dans AUCUNE validation statique : `amtool check-config`
disait « SUCCESS », le conteneur démarrait vert, et chaque alerte `severity=page` finissait
en « notify retry canceled due to unrecoverable error … no such file or directory » parce
qu'`url_file` n'est lu qu'AU MOMENT DE NOTIFIER. 1 447 notifications perdues en 72 heures.

On lance donc un vrai Alertmanager, on lui pousse une vraie alerte, et on vérifie qu'un
destinataire la reçoit — ou, quand aucun secret n'est fourni, qu'AUCUNE notification n'est
tentée ni mise en échec.
"""

from __future__ import annotations

import http.server
import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from typing import Any

from outils import (
    BESOIN_DOCKER,
    IMAGE_ALERTMANAGER,
    RACINE,
    ConteneurJetable,
    attendre_http,
    executer,
    port_libre,
)


class _Reception(http.server.BaseHTTPRequestHandler):
    """Destinataire de test : mémorise les corps reçus, par chemin."""

    recues: dict[str, list[Any]] = {}
    verrou = threading.Lock()

    def do_POST(self) -> None:  # noqa: N802 - imposé par BaseHTTPRequestHandler
        taille = int(self.headers.get("Content-Length", "0"))
        corps = self.rfile.read(taille).decode("utf-8", "replace")
        with _Reception.verrou:
            _Reception.recues.setdefault(self.path, []).append(corps)
        self.send_response(200)
        # Le notifieur Slack d'Alertmanager n'accepte QUE le corps « ok » : tout autre
        # contenu est traité comme « error response from Slack » et la notification est
        # perdue. Le destinataire de test reproduit donc le contrat réel de Slack.
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_: object) -> None:
        """Silence : les journaux du serveur de test n'apportent rien."""


class _Destinataire:
    """Serveur HTTP local jouant le rôle de Slack, OneUptime et surveillant externe."""

    def __init__(self) -> None:
        self.port = port_libre()
        _Reception.recues = {}
        self._serveur = http.server.ThreadingHTTPServer(("0.0.0.0", self.port), _Reception)
        self._fil = threading.Thread(target=self._serveur.serve_forever, daemon=True)

    def __enter__(self) -> _Destinataire:
        self._fil.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._serveur.shutdown()
        self._serveur.server_close()

    def attendre_reception(self, chemin: str, *, timeout: float = 120.0) -> list[Any]:
        """Attend au moins une notification sur `chemin`, et la rend."""
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            with _Reception.verrou:
                if _Reception.recues.get(chemin):
                    return list(_Reception.recues[chemin])
            time.sleep(0.5)
        with _Reception.verrou:
            recues = dict(_Reception.recues)
        raise AssertionError(f"aucune notification sur {chemin} en {timeout:.0f} s (reçu : {recues})")


def _pousser_alerte(port: int, nom: str, severite: str, service: str | None = None) -> None:
    """Injecte une alerte dans Alertmanager via son API v2, comme le ferait Prometheus."""
    etiquettes = {"alertname": nom, "severity": severite}
    if service:
        etiquettes["service_name"] = service
    charge = json.dumps([{
        "labels": etiquettes,
        "annotations": {"summary": f"alerte de test {nom}", "description": "injectée par la suite de tests"},
        "startsAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }]).encode("utf-8")
    requete = urllib.request.Request(  # noqa: S310 - URL locale de test
        f"http://127.0.0.1:{port}/api/v2/alerts",
        data=charge,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requete, timeout=10) as reponse:  # noqa: S310
        assert reponse.status in (200, 202), reponse.status


def _etats_des_alertes(port: int) -> dict[str, str]:
    """État (`active` / `suppressed`) de chaque alerte connue d'Alertmanager, par nom."""
    brut = attendre_http(
        f"http://127.0.0.1:{port}/api/v2/alerts?active=true&silenced=true&inhibited=true",
        timeout=30,
    )
    return {a["labels"]["alertname"]: a["status"]["state"] for a in json.loads(brut)}


def _notifications_en_echec(port: int) -> float:
    """Somme de `alertmanager_notifications_failed_total` exposée par l'instance."""
    metriques = attendre_http(f"http://127.0.0.1:{port}/metrics", timeout=30)
    total = 0.0
    for ligne in metriques.splitlines():
        if ligne.startswith("alertmanager_notifications_failed_total{"):
            total += float(ligne.rsplit(" ", 1)[1])
    return total


@BESOIN_DOCKER
class LivraisonDesAlertes(unittest.TestCase):
    """Bout en bout : Alertmanager → destinataire."""

    def _lancer(self, secrets: dict[str, str], port_am: int, nom: str) -> ConteneurJetable:
        repertoire = Path(tempfile.mkdtemp(prefix="obs-test-secrets-"))
        self.addCleanup(shutil.rmtree, repertoire, ignore_errors=True)
        for fichier, contenu in secrets.items():
            (repertoire / fichier).write_text(contenu, encoding="utf-8")
        return ConteneurJetable(nom, [
            "-p", f"127.0.0.1:{port_am}:9093",
            "--add-host", "host.docker.internal:host-gateway",
            "-v", f"{RACINE}/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro",
            "-v", f"{RACINE}/alertmanager/render-config.sh:/etc/alertmanager/render-config.sh:ro",
            "-v", f"{repertoire}:/etc/alertmanager/secrets:ro",
            "--entrypoint", "/bin/sh", IMAGE_ALERTMANAGER,
            "/etc/alertmanager/render-config.sh",
            "--config.file=/tmp/alertmanager.yml",
            "--storage.path=/alertmanager",
            "--web.listen-address=:9093",
        ])

    def test_une_alerte_page_atteint_slack_et_l_astreinte(self) -> None:
        """Le chemin `page-oncall` livre bien sur ses deux intégrations."""
        port_am = port_libre()
        with _Destinataire() as destinataire:
            base = f"http://host.docker.internal:{destinataire.port}"
            secrets = {
                "slack_webhook_url": f"{base}/slack\n",
                "oneuptime_webhook_url": f"{base}/astreinte\n",
            }
            with self._lancer(secrets, port_am, "obs-test-am-livraison") as conteneur:
                attendre_http(f"http://127.0.0.1:{port_am}/-/ready", timeout=60)
                _pousser_alerte(port_am, "TestLivraisonPage", "page", "gateway")

                recues_astreinte = destinataire.attendre_reception("/astreinte")
                recues_slack = destinataire.attendre_reception("/slack")
                journaux = conteneur.journaux()

        charge = json.loads(recues_astreinte[0])
        self.assertEqual(charge["receiver"], "page-oncall")
        self.assertEqual(charge["commonLabels"]["alertname"], "TestLivraisonPage")
        self.assertIn("TestLivraisonPage", recues_slack[0])
        self.assertNotIn("Notify for alerts failed", journaux)

    def test_sans_secret_optionnel_aucune_notification_n_echoue(self) -> None:
        """La régression C-042 : un secret absent ne doit plus produire d'échec.

        Auparavant, `alertmanager.yml` déclarait le webhook OneUptime en dur ; sans le
        fichier de secret, CHAQUE alerte `page` produisait une erreur irrécupérable et
        n'atteignait personne. Ici, seule l'intégration Slack existe : l'alerte est livrée
        et le compteur d'échecs reste à zéro.
        """
        port_am = port_libre()
        with _Destinataire() as destinataire:
            secrets = {"slack_webhook_url": f"http://host.docker.internal:{destinataire.port}/slack\n"}
            with self._lancer(secrets, port_am, "obs-test-am-sans-secret") as conteneur:
                attendre_http(f"http://127.0.0.1:{port_am}/-/ready", timeout=60)
                _pousser_alerte(port_am, "TestSansSecret", "page", "gateway")
                destinataire.attendre_reception("/slack")
                echecs = _notifications_en_echec(port_am)
                journaux = conteneur.journaux()

        self.assertEqual(echecs, 0.0, f"des notifications ont échoué :\n{journaux}")
        self.assertNotIn("Notify for alerts failed", journaux)
        self.assertNotIn("no such file or directory", journaux)
        # Le rendu doit dire, explicitement, ce qui n'est pas branché.
        self.assertIn("oneuptime_webhook_url » ABSENTE", journaux)

    def test_une_alerte_de_dette_ne_revient_pas_dans_le_canal_d_incident(self) -> None:
        """C-354 : deux alertes vraies EN PERMANENCE ne doivent plus alimenter #alertes.

        `SauvegardeJamaisDeclaree` et `SGFECronsNonInstrumentes` déclarent volontairement un
        trou d'instrumentation du dépôt observé : elles sont vraies tant qu'il n'est pas
        comblé. On ne les supprime pas — une surveillance qui ne peut pas se déclencher
        rassure à tort — mais en `severity: ticket` elles repartaient dans le canal
        d'incident toutes les 24 h, c'est-à-dire le bruit que ce même chantier venait d'y
        nettoyer. La gravité `dette` les en sort.

        Deux alertes sont poussées ensemble, une de chaque gravité, parce qu'une absence ne
        se prouve pas toute seule : si rien n'arrivait sur `/incidents`, le test passerait
        même avec un Alertmanager muet.
        """
        port_am = port_libre()
        with _Destinataire() as destinataire:
            base = f"http://host.docker.internal:{destinataire.port}"
            secrets = {
                "slack_webhook_url": f"{base}/incidents\n",
                "slack_webhook_dette_url": f"{base}/dette\n",
            }
            with self._lancer(secrets, port_am, "obs-test-am-dette") as conteneur:
                attendre_http(f"http://127.0.0.1:{port_am}/-/ready", timeout=60)
                # C'est amtool qui calcule la route sur la configuration RENDUE, pas le test
                # qui relit l'arbre du socle : le routage effectif est ce qui compte.
                routes = {
                    gravite: executer([
                        "docker", "exec", conteneur.nom, "amtool", "config", "routes", "test",
                        "--config.file=/tmp/alertmanager.yml", f"severity={gravite}",
                    ]).stdout.strip()
                    for gravite in ("dette", "ticket", "page", "veilleuse")
                }
                _pousser_alerte(port_am, "TestDetteInstrumentation", "dette")
                _pousser_alerte(port_am, "TestIncidentOrdinaire", "ticket", "gateway")

                recues_dette = destinataire.attendre_reception("/dette")
                recues_incidents = destinataire.attendre_reception("/incidents")
                journaux = conteneur.journaux()

        self.assertEqual(routes["dette"], "dette-technique")
        self.assertEqual(routes["ticket"], "slack")
        self.assertEqual(routes["page"], "page-oncall")
        self.assertEqual(routes["veilleuse"], "veilleuse")

        self.assertIn("TestDetteInstrumentation", "".join(recues_dette))
        self.assertIn("TestIncidentOrdinaire", "".join(recues_incidents))
        self.assertNotIn(
            "TestDetteInstrumentation", "".join(recues_incidents),
            "la dette d'instrumentation est revenue dans le canal d'incident",
        )
        self.assertNotIn("Notify for alerts failed", journaux)

    def test_sans_webhook_dedie_la_dette_retombe_sur_le_canal_principal(self) -> None:
        """Le repli doit livrer, jamais échouer : un secret absent n'est pas une panne.

        Sans `slack_webhook_dette_url`, le rendu réutilise le webhook principal avec un autre
        canal demandé. Un webhook d'app Slack étant lié à son canal, la séparation ne tient
        alors qu'à la fréquence (une fois par semaine au lieu d'une fois par jour) — ce qui
        doit être dit, et l'est : le script l'annonce au démarrage.
        """
        port_am = port_libre()
        with _Destinataire() as destinataire:
            secrets = {
                "slack_webhook_url": f"http://host.docker.internal:{destinataire.port}/incidents\n"
            }
            with self._lancer(secrets, port_am, "obs-test-am-dette-repli") as conteneur:
                attendre_http(f"http://127.0.0.1:{port_am}/-/ready", timeout=60)
                _pousser_alerte(port_am, "TestDetteSansCanalDedie", "dette")
                recues = destinataire.attendre_reception("/incidents")
                echecs = _notifications_en_echec(port_am)
                journaux = conteneur.journaux()

        self.assertIn("TestDetteSansCanalDedie", "".join(recues))
        self.assertEqual(echecs, 0.0, f"des notifications ont échoué :\n{journaux}")
        self.assertIn("webhook Slack PRINCIPAL", journaux)

    def test_un_secret_manquant_reference_en_dur_ferait_echouer_la_livraison(self) -> None:
        """Contrôle négatif : le test précédent sait détecter le défaut d'origine.

        On rejoue la configuration fautive — un `url_file` pointant un fichier absent — et
        l'on vérifie qu'Alertmanager compte bien des notifications en échec. Sans ce
        contrôle, `echecs == 0` pourrait n'être qu'un test qui ne mesure rien.
        """
        port_am = port_libre()
        fautive = Path(tempfile.mkdtemp(prefix="obs-test-am-fautif-")) / "alertmanager.yml"
        fautive.write_text(
            "route:\n"
            "  receiver: page-oncall\n"
            "  group_wait: 0s\n"
            "receivers:\n"
            "  - name: page-oncall\n"
            "    webhook_configs:\n"
            "      - url_file: /etc/alertmanager/secrets/secret-absent\n",
            encoding="utf-8",
        )
        self.addCleanup(shutil.rmtree, fautive.parent, ignore_errors=True)
        with ConteneurJetable("obs-test-am-fautif", [
            "-p", f"127.0.0.1:{port_am}:9093",
            "-v", f"{fautive}:/etc/alertmanager/alertmanager.yml:ro",
            IMAGE_ALERTMANAGER,
            "--config.file=/etc/alertmanager/alertmanager.yml",
            "--storage.path=/alertmanager",
        ]) as conteneur:
            attendre_http(f"http://127.0.0.1:{port_am}/-/ready", timeout=60)
            _pousser_alerte(port_am, "TestConfigurationFautive", "page")
            echecs = 0.0
            limite = time.monotonic() + 90
            while time.monotonic() < limite and echecs == 0.0:
                echecs = _notifications_en_echec(port_am)
                if echecs == 0.0:
                    time.sleep(1)
            journaux = conteneur.journaux()

        self.assertGreater(echecs, 0.0, f"le défaut d'origine n'a pas été reproduit :\n{journaux}")
        self.assertIn("no such file or directory", journaux)


@BESOIN_DOCKER
class InhibitionDesAlertes(unittest.TestCase):
    """C-354 : une `page` sans service ne doit plus éteindre TOUS les tickets sans service.

    `equal: [service_name]` compare des étiquettes ; or, dit la documentation Alertmanager,
    « semantically, a missing label and a label with an empty value are the same thing ».
    Une alerte disque permanente (`DisquePresquePlein`, sans `service_name`) « égalait » donc
    tous les tickets sans service et les inhibait en bloc : le bruit éteignait le signal.
    """

    # Déclarés au niveau de la classe : `setUpClass` les renseigne, et les annoncer ici
    # permet à mypy --strict de les suivre (une annotation posée sur `cls.x` ne compte pas).
    port: int
    _repertoire: Path
    _conteneur: ConteneurJetable
    etats: dict[str, str]

    @classmethod
    def setUpClass(cls) -> None:
        repertoire = Path(tempfile.mkdtemp(prefix="obs-test-inhibition-"))
        cls._repertoire = repertoire
        (repertoire / "slack_webhook_url").write_text("http://127.0.0.1:1/slack\n", encoding="utf-8")
        cls.port = port_libre()
        cls._conteneur = ConteneurJetable("obs-test-am-inhibition", [
            "-p", f"127.0.0.1:{cls.port}:9093",
            "-v", f"{RACINE}/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro",
            "-v", f"{RACINE}/alertmanager/render-config.sh:/etc/alertmanager/render-config.sh:ro",
            "-v", f"{repertoire}:/etc/alertmanager/secrets:ro",
            "--entrypoint", "/bin/sh", IMAGE_ALERTMANAGER,
            "/etc/alertmanager/render-config.sh",
            "--config.file=/tmp/alertmanager.yml",
            "--storage.path=/alertmanager",
            "--web.listen-address=:9093",
        ])
        cls._conteneur.__enter__()
        attendre_http(f"http://127.0.0.1:{cls.port}/-/ready", timeout=60)

        # Le jeu d'alertes exact de l'incident : une page d'infrastructure sans service, une
        # page de service, et trois tickets dont un seul partage le service de la page.
        _pousser_alerte(cls.port, "DisquePresquePlein", "page")
        _pousser_alerte(cls.port, "ProbeSlow", "ticket")
        _pousser_alerte(cls.port, "HighLatencyP99", "page", "gateway")
        _pousser_alerte(cls.port, "BudgetLatenceDepasse", "ticket", "gateway")
        _pousser_alerte(cls.port, "BudgetLatenceLecture", "ticket", "auth-service")

        attendus = {"DisquePresquePlein", "ProbeSlow", "HighLatencyP99",
                    "BudgetLatenceDepasse", "BudgetLatenceLecture"}
        cls.etats = {}
        limite = time.monotonic() + 60
        while time.monotonic() < limite:
            cls.etats = _etats_des_alertes(cls.port)
            if attendus <= set(cls.etats) and "unprocessed" not in cls.etats.values():
                break
            time.sleep(0.5)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._conteneur.__exit__()
        shutil.rmtree(cls._repertoire, ignore_errors=True)

    def test_un_ticket_du_meme_service_qu_une_page_est_bien_inhibe(self) -> None:
        """L'inhibition doit continuer de faire son travail : on ne l'a pas désactivée."""
        self.assertEqual(self.etats.get("BudgetLatenceDepasse"), "suppressed")

    def test_un_ticket_sans_service_n_est_plus_inhibe_par_une_page_sans_service(self) -> None:
        """LA régression C-354 : `ProbeSlow` était éteint par l'alerte disque permanente."""
        self.assertEqual(self.etats.get("ProbeSlow"), "active")

    def test_un_ticket_d_un_autre_service_reste_actif(self) -> None:
        self.assertEqual(self.etats.get("BudgetLatenceLecture"), "active")

    def test_les_pages_ne_sont_jamais_inhibees(self) -> None:
        for nom in ("DisquePresquePlein", "HighLatencyP99"):
            with self.subTest(alerte=nom):
                self.assertEqual(self.etats.get(nom), "active")


@BESOIN_DOCKER
class RenduConditionnelDeLaConfiguration(unittest.TestCase):
    """`render-config.sh` n'écrit une intégration que si son secret est utilisable."""

    def _rendre(self, secrets: dict[str, str], environnement: dict[str, str] | None = None) -> str:
        repertoire = Path(tempfile.mkdtemp(prefix="obs-test-rendu-"))
        self.addCleanup(shutil.rmtree, repertoire, ignore_errors=True)
        for fichier, contenu in secrets.items():
            (repertoire / fichier).write_text(contenu, encoding="utf-8")
        variables: list[str] = []
        for cle, valeur in (environnement or {}).items():
            variables += ["-e", f"{cle}={valeur}"]
        resultat = executer([
            "docker", "run", "--rm",
            "-v", f"{RACINE}/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro",
            "-v", f"{RACINE}/alertmanager/render-config.sh:/etc/alertmanager/render-config.sh:ro",
            "-v", f"{repertoire}:/etc/alertmanager/secrets:ro",
            "-e", "ALERTMANAGER_RENDERED_CONFIG=/tmp/rendu.yml",
            *variables,
            "--entrypoint", "/bin/sh", IMAGE_ALERTMANAGER,
            "-c", "/etc/alertmanager/render-config.sh >/dev/null 2>&1; cat /tmp/rendu.yml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return resultat.stdout

    def _journal_du_rendu(self, secrets: dict[str, str]) -> str:
        """Ce que le script DIT au démarrage — c'est le seul canal qui reste quand il n'y en a plus."""
        repertoire = Path(tempfile.mkdtemp(prefix="obs-test-journal-"))
        self.addCleanup(shutil.rmtree, repertoire, ignore_errors=True)
        for fichier, contenu in secrets.items():
            (repertoire / fichier).write_text(contenu, encoding="utf-8")
        resultat = executer([
            "docker", "run", "--rm",
            "-v", f"{RACINE}/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro",
            "-v", f"{RACINE}/alertmanager/render-config.sh:/etc/alertmanager/render-config.sh:ro",
            "-v", f"{repertoire}:/etc/alertmanager/secrets:ro",
            "-e", "ALERTMANAGER_RENDERED_CONFIG=/tmp/rendu.yml",
            "--entrypoint", "/bin/sh", IMAGE_ALERTMANAGER,
            "/etc/alertmanager/render-config.sh",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return resultat.stdout + resultat.stderr

    @staticmethod
    def _effectif(rendu: str) -> str:
        """Configuration débarrassée de ses commentaires.

        Le socle mentionne légitimement OneUptime et Slack dans ses commentaires : chercher
        une chaîne dans le fichier brut confondrait une explication et une intégration.
        """
        return "\n".join(ligne for ligne in rendu.splitlines() if not ligne.lstrip().startswith("#"))

    def test_un_secret_vide_vaut_un_secret_absent(self) -> None:
        """Le socle en mode image créait des fichiers VIDES : même échec qu'un fichier absent."""
        rendu = self._rendre({"slack_webhook_url": "https://exemple\n", "oneuptime_webhook_url": "   \n"})
        effectif = self._effectif(rendu)
        self.assertNotIn("webhook_configs", effectif)
        self.assertNotIn("secrets/oneuptime_webhook_url", effectif)
        # Slack, dont le secret est utilisable, reste bien branché.
        self.assertIn("api_url_file: /etc/alertmanager/secrets/slack_webhook_url", effectif)

    def test_sans_secret_slack_aucune_integration_slack_n_est_ecrite(self) -> None:
        """La règle « pas de secret, pas d'intégration » vaut AUSSI pour le canal principal.

        Slack était le dernier canal encore déclaré en dur dans le socle : une installation
        sans `slack_webhook_url` rejouait mot pour mot l'incident du 11/09, cette fois sur
        `api_url_file`. Les deux récepteurs qui l'utilisent doivent donc rester vides.
        """
        effectif = self._effectif(self._rendre({}))
        self.assertNotIn("slack_configs", effectif)
        self.assertNotIn("api_url_file", effectif)
        # Le routage, lui, reste intact : les récepteurs existent, ils n'envoient rien.
        for receveur in ("- name: slack", "- name: page-oncall", "- name: veilleuse"):
            self.assertIn(receveur, effectif)

    def test_l_absence_totale_de_canal_est_annoncee_bruyamment(self) -> None:
        """Le pire état n'est plus « une intégration en échec » mais « aucun canal »."""
        journal = self._journal_du_rendu({})
        self.assertIn("AUCUN canal de notification", journal)
        # Dès qu'un canal existe, l'avertissement disparaît : il doit rester un signal.
        self.assertNotIn("AUCUN canal de notification", self._journal_du_rendu({"slack_webhook_url": "https://x\n"}))

    def test_le_bloc_email_exige_toutes_ses_variables(self) -> None:
        secrets = {"slack_webhook_url": "https://exemple\n", "smtp_password": "motdepasse\n"}
        sans_destinataire = self._rendre(secrets, {"ALERT_SMTP_SMARTHOST": "smtp:587"})
        self.assertNotIn("email_configs", sans_destinataire)

        complet = self._rendre(secrets, {
            "ALERT_EMAIL_TO": "astreinte@exemple.test",
            "ALERT_EMAIL_FROM": "alertes@exemple.test",
            "ALERT_SMTP_SMARTHOST": "smtp-relay.exemple.test:587",
        })
        self.assertIn("email_configs", complet)
        self.assertIn("auth_password_file: /etc/alertmanager/secrets/smtp_password", complet)

    def test_tout_rendu_reste_accepte_par_amtool(self) -> None:
        """Quelle que soit la combinaison de secrets, la configuration doit rester valide."""
        combinaisons: list[dict[str, str]] = [
            # Aucun secret : trois récepteurs sans aucune intégration. Alertmanager doit
            # tout de même démarrer — un socle qui refuse de se charger est un socle qui ne
            # remonte plus rien du tout.
            {},
            {"slack_webhook_url": "https://exemple\n"},
            {"slack_webhook_url": "https://exemple\n", "oneuptime_webhook_url": "https://ou\n"},
            {"slack_webhook_url": "https://exemple\n", "veilleuse_webhook_url": "https://hb\n"},
            {"slack_webhook_url": "https://exemple\n", "oneuptime_webhook_url": "https://ou\n",
             "veilleuse_webhook_url": "https://hb\n", "smtp_password": "mdp\n"},
        ]
        for secrets in combinaisons:
            with self.subTest(secrets=sorted(secrets)):
                rendu = self._rendre(secrets, {
                    "ALERT_EMAIL_TO": "a@b.test",
                    "ALERT_EMAIL_FROM": "c@b.test",
                    "ALERT_SMTP_SMARTHOST": "smtp:587",
                })
                chemin = RACINE / "tests" / ".rendu-verifie.yml"
                try:
                    chemin.write_text(rendu, encoding="utf-8")
                    resultat = executer([
                        "docker", "run", "--rm", "-v", f"{chemin}:/cfg.yml:ro",
                        "--entrypoint", "amtool", IMAGE_ALERTMANAGER, "check-config", "/cfg.yml",
                    ])
                    self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
                finally:
                    chemin.unlink(missing_ok=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

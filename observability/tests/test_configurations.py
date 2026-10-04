"""Chaque fichier de configuration est relu par le binaire qui l'exécutera en production.

Un test qui se contenterait de chercher une chaîne dans un YAML ne prouve rien : c'est
exactement ce qui a laissé passer `sending_queue` sur l'exportateur remote-write (option
inexistante, le Collector refuse de démarrer) et un `url_file` pointant un secret absent
(configuration valide, notifications systématiquement en échec). On fait donc lire, et on
vérifie ce que le binaire répond.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from outils import (
    BESOIN_DOCKER,
    IMAGE_ALERTMANAGER,
    IMAGE_ALLOY,
    IMAGE_COLLECTOR,
    IMAGE_LOKI,
    IMAGE_PROMETHEUS,
    IMAGE_TEMPO,
    RACINE,
    env_test,
    executer,
)


@BESOIN_DOCKER
class ValidationParLesBinairesReels(unittest.TestCase):
    """Les six configurations du socle doivent être acceptées par leurs propres binaires."""

    def test_prometheus_accepte_sa_configuration_et_toutes_ses_regles(self) -> None:
        resultat = executer([
            "docker", "run", "--rm", "-v", f"{RACINE}/prometheus:/etc/prometheus:ro",
            "--entrypoint", "promtool", IMAGE_PROMETHEUS,
            "check", "config", "/etc/prometheus/prometheus.yml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        # Les fichiers de règles ajoutés pour SGFE doivent être chargés, pas seulement présents.
        for fichier in ("sgfe.yml", "collecte.yml", "veilleuse.yml", "slo-sgfe.yml"):
            self.assertIn(fichier, resultat.stdout, f"{fichier} n'est pas chargé par Prometheus")

    def _verifier_avec_regles_du_consommateur(self, regles: dict[str, str]) -> str:
        """Monte `regles` (nom → contenu) là où un consommateur les monte, et rend la sortie.

        Le montage imbriqué SOUS `./prometheus:ro` est celui du mode compose, le plus exigeant :
        il ne tient que si le point de montage existe déjà dans le dépôt (le `.gitkeep`).
        """
        dossier = Path(tempfile.mkdtemp(prefix="obs-test-consommateur-"))
        self.addCleanup(shutil.rmtree, dossier, ignore_errors=True)
        for nom, contenu in regles.items():
            (dossier / nom).write_text(contenu, encoding="utf-8")
        resultat = executer([
            "docker", "run", "--rm", "-v", f"{RACINE}/prometheus:/etc/prometheus:ro",
            "-v", f"{dossier}:/etc/prometheus/rules/consommateur:ro",
            "--entrypoint", "promtool", IMAGE_PROMETHEUS,
            "check", "config", "/etc/prometheus/prometheus.yml",
        ])
        return f"code={resultat.returncode}\n{resultat.stdout}{resultat.stderr}"

    def test_une_regle_deposee_par_un_consommateur_est_chargee(self) -> None:
        # La plateforme n'embarque aucune règle d'un projet observé : elles arrivent par ce
        # répertoire. Le fichier doit être LU, pas seulement listé — d'où le décompte de règles.
        sortie = self._verifier_avec_regles_du_consommateur({"projet.yml": (
            "groups:\n  - name: projet\n    rules:\n"
            "      - alert: ExempleDuConsommateur\n        expr: vector(1) > 0\n"
            "        labels: { severity: ticket }\n"
        )})
        self.assertTrue(sortie.startswith("code=0\n"), sortie)
        self.assertIn("Checking /etc/prometheus/rules/consommateur/projet.yml", sortie)
        self.assertIn("SUCCESS: 1 rules found", sortie.split("consommateur/projet.yml", 1)[1])

    def test_une_regle_invalide_du_consommateur_est_refusee(self) -> None:
        # La contre-épreuve : si le motif ne chargeait rien, un fichier cassé passerait aussi.
        sortie = self._verifier_avec_regles_du_consommateur(
            {"casse.yml": "groups:\n  - name: casse\n    rules:\n      - alert: X\n        expr: (\n"}
        )
        self.assertFalse(sortie.startswith("code=0\n"), sortie)
        self.assertIn("consommateur/casse.yml", sortie)

    def test_un_repertoire_du_consommateur_vide_ne_casse_rien(self) -> None:
        # Le cas de toute installation qui ne monte rien : l'image livre ce répertoire vide.
        sortie = self._verifier_avec_regles_du_consommateur({})
        self.assertTrue(sortie.startswith("code=0\n"), sortie)
        self.assertNotIn("consommateur/", sortie)

    def test_loki_accepte_sa_configuration_avec_la_retention_active(self) -> None:
        resultat = executer([
            "docker", "run", "--rm", "-v", f"{RACINE}/loki-config.yaml:/etc/loki/config.yaml:ro",
            IMAGE_LOKI, "-config.file=/etc/loki/config.yaml", "-verify-config",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("config is valid", resultat.stdout + resultat.stderr)

    def test_tempo_accepte_sa_configuration(self) -> None:
        resultat = executer([
            "docker", "run", "--rm", "-v", f"{RACINE}/tempo-config.yaml:/etc/tempo/config.yaml:ro",
            IMAGE_TEMPO, "-config.file=/etc/tempo/config.yaml", "-config.verify=true",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_le_collector_accepte_sa_configuration(self) -> None:
        resultat = executer([
            "docker", "run", "--rm",
            "-v", f"{RACINE}/otel-collector-config.yaml:/etc/otelcol/config.yaml:ro",
            IMAGE_COLLECTOR, "validate", "--config=/etc/otelcol/config.yaml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_le_collector_refuse_sending_queue_sur_le_remote_write(self) -> None:
        """Contrôle négatif : la correction proposée à l'audit aurait cassé le Collector.

        L'exportateur `prometheusremotewrite` n'expose PAS `sending_queue` (son README le
        dit : « the exporter doesn't support sending_queue but provides remote_write_queue »).
        Ce test fige la raison pour laquelle la configuration emploie `remote_write_queue`.
        """
        configuration = (RACINE / "otel-collector-config.yaml").read_text(encoding="utf-8")
        self.assertIn("remote_write_queue", configuration)
        fautive = configuration.replace("    remote_write_queue:", "    sending_queue:")
        chemin = RACINE / "tests" / ".collector-fautif.yaml"
        try:
            chemin.write_text(fautive, encoding="utf-8")
            resultat = executer([
                "docker", "run", "--rm", "-v", f"{chemin}:/etc/otelcol/config.yaml:ro",
                IMAGE_COLLECTOR, "validate", "--config=/etc/otelcol/config.yaml",
            ])
            self.assertNotEqual(resultat.returncode, 0, "le Collector aurait dû refuser sending_queue")
            self.assertIn("sending_queue", resultat.stdout + resultat.stderr)
        finally:
            chemin.unlink(missing_ok=True)

    def test_alloy_accepte_les_deux_configurations(self) -> None:
        for fichier in ("alloy-config.alloy", "docker/alloy-faro.alloy"):
            with self.subTest(fichier=fichier):
                resultat = executer([
                    "docker", "run", "--rm", "-v", f"{RACINE}/{fichier}:/cfg.alloy:ro",
                    "--entrypoint", "/bin/alloy", IMAGE_ALLOY, "fmt", "/cfg.alloy",
                ])
                self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_alloy_evalue_entierement_le_graphe_de_composants(self) -> None:
        """`fmt` ne vérifie que la syntaxe : on charge réellement la configuration.

        `sys.env`, `coalesce`, `stage.logfmt` et `stage.labels` ne sont résolus qu'à
        l'évaluation du graphe — une faute y passerait inaperçue d'un simple formatage.
        """
        from outils import ConteneurJetable, attendre_http, port_libre  # import local : docker requis

        port = port_libre()
        with ConteneurJetable("obs-test-alloy-eval", [
            "-p", f"127.0.0.1:{port}:{port}",
            "-v", f"{RACINE}/alloy-config.alloy:/cfg.alloy:ro",
            "-e", "LOGS_COMPOSE_PROJECTS=obs-test-.*",
            "--entrypoint", "/bin/alloy", IMAGE_ALLOY,
            "run", "/cfg.alloy", f"--server.http.listen-addr=0.0.0.0:{port}",
            "--storage.path=/tmp/alloy",
        ]) as conteneur:
            attendre_http(f"http://127.0.0.1:{port}/-/ready", timeout=60)
            # On attend la LIGNE, pas un instant : sur une machine chargée, `/-/ready`
            # répond avant qu'Alloy n'ait fini d'évaluer son graphe, et lire le journal
            # aussitôt faisait échouer ce test sans qu'aucune configuration soit en cause.
            journaux = conteneur.attendre_journal("finished complete graph evaluation", timeout=60)
        self.assertIn("finished complete graph evaluation", journaux)
        self.assertNotIn("Failed to load config", journaux)
        self.assertNotIn("decode error", journaux)

    def test_alertmanager_accepte_la_configuration_socle(self) -> None:
        resultat = executer([
            "docker", "run", "--rm",
            "-v", f"{RACINE}/alertmanager/alertmanager.yml:/cfg.yml:ro",
            "--entrypoint", "amtool", IMAGE_ALERTMANAGER, "check-config", "/cfg.yml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_les_deux_assemblages_compose_sont_valides(self) -> None:
        for fichiers in (
            ["docker-compose.yml"],
            ["docker-compose.yml", "hardening/docker-compose.hardening.yml"],
        ):
            with self.subTest(assemblage=" + ".join(fichiers)):
                arguments: list[str] = []
                for fichier in fichiers:
                    arguments += ["-f", str(RACINE / fichier)]
                resultat = executer([
                    "docker", "compose", "--project-directory", str(RACINE),
                    *arguments, "config", "-q",
                ])
                self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)


@BESOIN_DOCKER
class TestsUnitairesDesReglesPrometheus(unittest.TestCase):
    """`promtool test rules` : les alertes se déclenchent — ou se taisent — comme attendu."""

    def test_toutes_les_suites_de_regles_passent(self) -> None:
        fichiers = sorted(p.name for p in (RACINE / "tests" / "prometheus").glob("*_test.yml"))
        self.assertTrue(fichiers, "aucune suite de tests de règles trouvée")
        resultat = executer([
            "docker", "run", "--rm", "-v", f"{RACINE}:/w:ro", "-w", "/w/tests/prometheus",
            "--entrypoint", "promtool", IMAGE_PROMETHEUS, "test", "rules", *fichiers,
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("SUCCESS", resultat.stdout)


@BESOIN_DOCKER
class NeutraliteDeLImage(unittest.TestCase):
    """L'image publiée est universelle : elle ne nomme aucun projet consommateur.

    Jusqu'à la 1.1.7, la préprod d'un consommateur affichait un dossier Grafana, des alertes et
    des jobs Prometheus au nom d'un AUTRE. On ne relit pas les sources, on rejoue la copie :
    les `COPY` locaux du vrai Dockerfile, sur une base minimale, avec le vrai `.dockerignore` —
    c'est lui seul qui décide de ce qui entre, et c'est lui qu'il faut prendre en défaut.
    """

    # Noms des consommateurs connus. Ajouter ici tout nouveau projet qui tire l'image.
    CONSOMMATEURS = "sgfe|formuloo"

    def test_aucun_fichier_embarque_ne_nomme_un_consommateur(self) -> None:
        dockerfile = (RACINE / "Dockerfile").read_text(encoding="utf-8")
        copies = re.findall(r"^COPY\s+(?!--)(\S+)\s+(\S+)\s*$", dockerfile, re.MULTILINE)
        self.assertGreater(len(copies), 10, "les COPY du Dockerfile n'ont pas été relevés")
        # La moitié qui rend la preuve possible : les sources copiées CONTIENNENT ces noms, donc
        # une image propre ne l'est que par l'exclusion, pas par hasard.
        self.assertTrue((RACINE / "prometheus" / "rules" / "sgfe.yml").is_file())

        with tempfile.TemporaryDirectory() as dossier:
            gabarit = Path(dossier) / "Dockerfile"
            gabarit.write_text(
                "FROM busybox:1.37\n" + "".join(f"COPY {src} {dst}\n" for src, dst in copies),
                encoding="utf-8",
            )
            construction = executer(["docker", "build", "-q", "-f", str(gabarit), str(RACINE)])
        self.assertEqual(construction.returncode, 0, construction.stdout + construction.stderr)
        image = construction.stdout.strip()
        self.addCleanup(executer, ["docker", "rmi", "-f", image])

        def lancer(commande: str) -> str:
            resultat = executer(["docker", "run", "--rm", image, "sh", "-c", commande])
            return resultat.stdout.strip()

        # Garde contre un succès à vide : la configuration doit bien être là.
        self.assertEqual(lancer("test -f /etc/prometheus/prometheus.yml && echo ok"), "ok")
        self.assertEqual(
            lancer(f"grep -rliE '{self.CONSOMMATEURS}' /etc /usr/local/bin"), "",
            "des fichiers embarqués nomment un projet consommateur",
        )
        self.assertEqual(
            lancer("grep -rlE 'job_name: *blackbox-demo' /etc; ls /etc/prometheus/targets | grep demo"),
            "",
            "la démonstration de ce dépôt est entrée dans l'image",
        )


def load_tests(
    loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None
) -> unittest.TestSuite:
    """Injecte l'environnement minimal attendu par `docker compose config`."""
    os.environ.update(env_test())
    return tests


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

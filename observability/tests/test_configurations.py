"""Chaque fichier de configuration est relu par le binaire qui l'exécutera en production.

Un test qui se contenterait de chercher une chaîne dans un YAML ne prouve rien : c'est
exactement ce qui a laissé passer `sending_queue` sur l'exportateur remote-write (option
inexistante, le Collector refuse de démarrer) et un `url_file` pointant un secret absent
(configuration valide, notifications systématiquement en échec). On fait donc lire, et on
vérifie ce que le binaire répond.
"""

from __future__ import annotations

import os
import unittest

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


def load_tests(
    loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None
) -> unittest.TestSuite:
    """Injecte l'environnement minimal attendu par `docker compose config`."""
    os.environ.update(env_test())
    return tests


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

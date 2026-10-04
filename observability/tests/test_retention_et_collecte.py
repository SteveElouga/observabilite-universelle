"""Rétention réellement appliquée et télémétrie non perdue (C-167, C-350, C-353).

Le défaut d'origine de la rétention était invisible dans le fichier : `retention_period`
était bien posé, mais sans bloc `compactor` Loki n'applique RIEN — « the logs sent to Loki
live forever ». Seule la configuration EFFECTIVE du serveur le dit ; c'est donc elle qu'on
interroge, comme l'audit l'avait fait (`curl :3100/config`).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from outils import (
    BESOIN_DOCKER,
    IMAGE_COLLECTOR,
    IMAGE_LOKI,
    RACINE,
    ConteneurJetable,
    attendre_http,
    duree_en_heures,
    env_test,
    executer,
    port_libre,
)

HEURES_90_JOURS = 2160
HEURES_30_JOURS = 720


def _ressource_otlp(
    service: str, attributs: dict[str, str], identifiant: str
) -> dict[str, Any]:
    """Un `resourceSpans` OTLP/JSON minimal, tel qu'un SDK l'enverrait."""
    declares = {"service.name": service, **attributs}
    return {
        "resource": {
            "attributes": [
                {"key": cle, "value": {"stringValue": valeur}}
                for cle, valeur in declares.items()
            ]
        },
        "scopeSpans": [{"spans": [{
            "traceId": f"5b8efff798038103d269b633813fc6{ord(identifiant):02x}",
            "spanId": f"eee19b7ec3c1b1{ord(identifiant):02x}",
            "name": identifiant,
            "kind": 1,
            "startTimeUnixNano": "1",
            "endTimeUnixNano": "2",
        }]}],
    }


def _attendre_ressources_exportees(
    fichier: Path, *, attendues: int, timeout: float = 60.0
) -> list[dict[str, str]]:
    """Attend que l'exportateur fichier ait écrit `attendues` ressources, et les rend.

    L'export est asynchrone : lire le fichier une seule fois juste après la réponse HTTP
    rendrait le test dépendant de la charge de la machine.
    """
    limite = time.monotonic() + timeout
    ressources: list[dict[str, str]] = []
    while time.monotonic() < limite:
        ressources = []
        if fichier.exists():
            for ligne in fichier.read_text(encoding="utf-8").splitlines():
                if not ligne.strip():
                    continue
                for spans in json.loads(ligne)["resourceSpans"]:
                    ressources.append({
                        attribut["key"]: str(next(iter(attribut["value"].values())))
                        for attribut in spans["resource"]["attributes"]
                    })
        if len(ressources) >= attendues:
            return ressources
        time.sleep(0.5)
    raise AssertionError(
        f"{len(ressources)} ressource(s) exportée(s) sur {attendues} en {timeout:.0f} s"
    )


@BESOIN_DOCKER
class RetentionEffectiveDeLoki(unittest.TestCase):
    """On interroge la configuration que le serveur a réellement chargée."""

    # Déclarés au niveau de la classe : `setUpClass` les renseigne, et les annoncer ici
    # permet à mypy --strict de les suivre (une annotation posée sur `cls.x` ne compte pas).
    _conteneur: ConteneurJetable
    configuration: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        port = port_libre()
        cls._conteneur = ConteneurJetable("obs-test-loki-retention", [
            "-p", f"127.0.0.1:{port}:3100",
            "-v", f"{RACINE}/loki-config.yaml:/etc/loki/config.yaml:ro",
            IMAGE_LOKI, "-config.file=/etc/loki/config.yaml",
        ])
        cls._conteneur.__enter__()
        attendre_http(f"http://127.0.0.1:{port}/ready", timeout=120)
        cls.configuration = yaml.safe_load(
            attendre_http(f"http://127.0.0.1:{port}/config", timeout=60)
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._conteneur.__exit__()

    def test_la_retention_est_activee(self) -> None:
        """`retention_enabled: false` était la valeur EFFECTIVE constatée le 11/09/2026."""
        self.assertTrue(self.configuration["compactor"]["retention_enabled"])

    def test_le_magasin_des_demandes_de_suppression_est_declare(self) -> None:
        """Obligatoire dès que la rétention est active ; il valait `""`."""
        self.assertEqual(self.configuration["compactor"]["delete_request_store"], "filesystem")

    def test_la_duree_de_conservation_vaut_quatre_vingt_dix_jours(self) -> None:
        """Comparaison sur la DURÉE et non sur son écriture : Loki réaffiche 2160h en « 90d »."""
        self.assertEqual(
            duree_en_heures(self.configuration["limits_config"]["retention_period"]),
            HEURES_90_JOURS,
        )

    def test_la_periode_d_index_permet_la_retention(self) -> None:
        """La documentation Loki est formelle : « Retention is only available if the index
        period is 24h ».

        Même précaution que ci-dessus : le fichier demande `24h`, le serveur réaffiche `1d`.
        C'est la même période — ce test vérifie la durée, pas la mise en forme.
        """
        for schema in self.configuration["schema_config"]["configs"]:
            with self.subTest(depuis=schema["from"]):
                self.assertEqual(duree_en_heures(schema["index"]["period"]), 24.0)


class PolitiqueDeConservationParSignal(unittest.TestCase):
    """Chaque signal a une durée choisie et écrite, pas héritée d'un défaut."""

    def test_tempo_conserve_les_traces_trente_jours(self) -> None:
        tempo = yaml.safe_load((RACINE / "tempo-config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            duree_en_heures(tempo["compactor"]["compaction"]["block_retention"]),
            HEURES_30_JOURS,
        )

    def test_loki_conserve_les_journaux_quatre_vingt_dix_jours(self) -> None:
        loki = yaml.safe_load((RACINE / "loki-config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            duree_en_heures(loki["limits_config"]["retention_period"]),
            HEURES_90_JOURS,
        )

    @BESOIN_DOCKER
    def test_prometheus_conserve_les_metriques_quatre_vingt_dix_jours_avec_un_plafond(self) -> None:
        """Lu sur la configuration RÉSOLUE par Compose, pas sur le texte du fichier."""
        resultat = executer(
            ["docker", "compose", "--project-directory", str(RACINE),
             "-f", str(RACINE / "docker-compose.yml"), "config", "--format", "json"],
        )
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        commande = json.loads(resultat.stdout)["services"]["prometheus"]["command"]
        self.assertIn("--storage.tsdb.retention.time=90d", commande)
        self.assertTrue(
            any(a.startswith("--storage.tsdb.retention.size=") for a in commande),
            "un plafond de taille doit borner la rétention : le disque hôte était à 89,6 %",
        )


class EnvironnementDeDeploiement(unittest.TestCase):
    """C-350 : le Collector ne doit plus écraser l'environnement déclaré par un SDK."""

    configuration: dict[str, Any]
    actions: list[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = yaml.safe_load(
            (RACINE / "otel-collector-config.yaml").read_text(encoding="utf-8")
        )
        cls.actions = cls.configuration["processors"]["resource"]["attributes"]

    def test_aucune_action_upsert_sur_l_environnement(self) -> None:
        """`upsert` écrasait `deployment.environment=dev` des 9 composants par « prod »."""
        for action in self.actions:
            with self.subTest(cle=action["key"]):
                self.assertNotEqual(
                    action["action"], "upsert",
                    "upsert écrase la valeur du SDK : utiliser insert",
                )

    def test_la_cle_stable_de_la_convention_semantique_est_renseignee(self) -> None:
        """`deployment.environment` est déprécié, « Replaced by deployment.environment.name »."""
        cles = [a["key"] for a in self.actions]
        self.assertIn("deployment.environment.name", cles)

    def test_l_ancienne_valeur_est_migree_avant_le_defaut_de_la_plateforme(self) -> None:
        """L'ordre compte : recopier la valeur du SDK, PUIS seulement combler le vide."""
        indices = {}
        for rang, action in enumerate(self.actions):
            if action["key"] == "deployment.environment.name":
                indices["depuis_sdk" if "from_attribute" in action else "defaut"] = rang
        self.assertIn("depuis_sdk", indices)
        self.assertIn("defaut", indices)
        self.assertLess(indices["depuis_sdk"], indices["defaut"])

    def test_l_ancienne_cle_reste_alimentee_pour_la_compatibilite(self) -> None:
        heritage = [a for a in self.actions if a["key"] == "deployment.environment"]
        self.assertTrue(heritage, "l'ancienne clé doit rester renseignée le temps de la migration")
        self.assertEqual(heritage[0]["action"], "insert")


class RobustesseDeLExportDesMetriques(unittest.TestCase):
    """C-353 : 133 386 points jetés en 6 h faute de délai, de file et de reprise."""

    exporteur: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.exporteur = yaml.safe_load(
            (RACINE / "otel-collector-config.yaml").read_text(encoding="utf-8")
        )["exporters"]["prometheusremotewrite"]

    def test_un_delai_explicite_plus_genereux_que_le_defaut(self) -> None:
        """Le défaut de 5 s était dépassé dès que l'hôte saturait."""
        self.assertEqual(self.exporteur["timeout"], "30s")

    def test_la_file_d_envoi_est_dimensionnee(self) -> None:
        """`remote_write_queue` et non `sending_queue` : cet exportateur n'a pas le second."""
        self.assertNotIn("sending_queue", self.exporteur)
        file = self.exporteur["remote_write_queue"]
        self.assertTrue(file["enabled"])
        self.assertGreaterEqual(file["queue_size"], 10000)

    def test_les_lots_en_echec_sont_rejoues(self) -> None:
        self.assertTrue(self.exporteur["retry_on_failure"]["enabled"])

    def test_les_lots_sont_bornes(self) -> None:
        """Sans `send_batch_max_size`, un pic produit un lot qu'aucun délai ne suffit à pousser."""
        lot = yaml.safe_load(
            (RACINE / "otel-collector-config.yaml").read_text(encoding="utf-8")
        )["processors"]["batch"]
        self.assertIn("send_batch_max_size", lot)
        self.assertGreater(lot["send_batch_max_size"], 0)


@BESOIN_DOCKER
class EnvironnementDeDeploiementObserve(unittest.TestCase):
    """C-350, prouvé par le COMPORTEMENT et non par la lecture du YAML.

    La classe précédente vérifie l'ordre et les clés du processeur `resource`. C'est
    nécessaire — l'ordre est la moitié de la correction — mais insuffisant : un processeur
    devenu inopérant dans une version ultérieure du Collector passerait ces contrôles sans
    broncher, et la télémétrie de développement redeviendrait « prod » sans qu'aucun test ne
    bouge. On fait donc traverser un VRAI Collector à deux ressources et on lit ce qui sort.
    """

    # Annoncés au niveau de la classe pour que mypy --strict les suive (une annotation
    # posée sur `cls.x` dans setUpClass ne compte pas).
    sorties: list[dict[str, str]]
    _dossier: Path
    _conteneur: ConteneurJetable

    @classmethod
    def setUpClass(cls) -> None:
        dossier = Path(tempfile.mkdtemp(prefix="obs-test-collector-"))
        # Le Collector tourne sous un utilisateur non privilégié (10001) : sans ce droit,
        # l'exportateur fichier échoue et le test mesurerait le montage, pas le processeur.
        dossier.chmod(0o777)
        cls._dossier = dossier

        # Le processeur est RECOPIÉ depuis le fichier de production : si quelqu'un le modifie,
        # c'est la version modifiée qui est mise à l'épreuve, pas une copie figée dans le test.
        production = yaml.safe_load(
            (RACINE / "otel-collector-config.yaml").read_text(encoding="utf-8")
        )
        configuration = {
            "receivers": {"otlp": {"protocols": {"http": {"endpoint": "0.0.0.0:4318"}}}},
            "processors": {"resource": production["processors"]["resource"]},
            "exporters": {"file": {"path": "/sortie/telemetrie.json"}},
            "service": {
                "telemetry": {"metrics": {"level": "none"}},
                "pipelines": {
                    "traces": {
                        "receivers": ["otlp"],
                        "processors": ["resource"],
                        "exporters": ["file"],
                    }
                },
            },
        }
        (dossier / "config.yaml").write_text(
            yaml.safe_dump(configuration, sort_keys=False), encoding="utf-8"
        )

        port = port_libre()
        cls._conteneur = ConteneurJetable("obs-test-collector-environnement", [
            "-p", f"127.0.0.1:{port}:4318",
            # Valeur volontairement identique à celle du compose : c'est elle qui ne doit
            # s'appliquer QU'aux émetteurs muets.
            "-e", "DEPLOY_ENV=prod",
            "-v", f"{dossier / 'config.yaml'}:/etc/otelcol/config.yaml:ro",
            "-v", f"{dossier}:/sortie",
            IMAGE_COLLECTOR, "--config=/etc/otelcol/config.yaml",
        ])
        cls._conteneur.__enter__()
        cls._conteneur.attendre_journal("Everything is ready", timeout=90)

        charge = json.dumps({"resourceSpans": [
            _ressource_otlp("auth-service", {"deployment.environment": "dev"}, "a"),
            _ressource_otlp("muet", {}, "b"),
        ]}).encode("utf-8")
        requete = urllib.request.Request(  # noqa: S310 - URL locale de test
            f"http://127.0.0.1:{port}/v1/traces",
            data=charge,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(requete, timeout=30) as reponse:  # noqa: S310
            assert reponse.status == 200, reponse.status

        cls.sorties = _attendre_ressources_exportees(dossier / "telemetrie.json", attendues=2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._conteneur.__exit__()
        shutil.rmtree(cls._dossier, ignore_errors=True)

    def _ressource(self, service: str) -> dict[str, str]:
        for attributs in self.sorties:
            if attributs.get("service.name") == service:
                return attributs
        raise AssertionError(f"aucune ressource « {service} » exportée : {self.sorties}")

    def test_l_environnement_declare_par_un_sdk_survit_au_collector(self) -> None:
        """Le défaut d'origine : toute la télémétrie ressortait étiquetée « prod »."""
        attributs = self._ressource("auth-service")
        self.assertEqual(attributs["deployment.environment"], "dev")
        self.assertEqual(attributs["deployment.environment.name"], "dev")

    def test_un_emetteur_muet_recoit_le_defaut_de_la_plateforme(self) -> None:
        """L'autre moitié : sans valeur du SDK, la plateforme doit bien en poser une."""
        attributs = self._ressource("muet")
        self.assertEqual(attributs["deployment.environment.name"], "prod")
        self.assertEqual(attributs["deployment.environment"], "prod")



def load_tests(
    loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None
) -> unittest.TestSuite:
    """Injecte l'environnement minimal attendu par `docker compose config`."""
    os.environ.update(env_test())
    return tests


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

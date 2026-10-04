"""La corrélation trace → journaux → profil fonctionne-t-elle vraiment ? (C-168, C-355, C-488)

Trois maillons, trois tests de COMPORTEMENT :
  · Alloy pose-t-il sur les flux Loki le même `service_name` que celui porté par les traces ?
  · le motif des champs dérivés fabrique-t-il encore des liens vers des traces inexistantes ?
  · la source de données Tempo interroge-t-elle des étiquettes qui existent côté Loki ?
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import unittest
from typing import Any

import yaml

from outils import (
    BESOIN_DOCKER,
    IMAGE_ALLOY,
    RACINE,
    ConteneurJetable,
    attendre_http,
    executer,
    port_libre,
)


# Le test apporte ses propres projets Compose au lieu de dépendre de ce qui tourne sur le
# poste : deux conteneurs jetables étiquetés comme Compose, l'un déclaré dans
# `LOGS_COMPOSE_PROJECTS`, l'autre non. Un périmètre `.+` ferait du test C-355 une tautologie.
PROJET_DECLARE: str = "obs-test-declare"
PROJET_INTRUS: str = "obs-test-intrus"
IMAGE_LEURRE: str = "busybox:1.37"


def _leurre(projet: str) -> ConteneurJetable:
    """Conteneur nommé comme Compose le ferait (`<projet>-<service>-1`), sans Compose."""
    return ConteneurJetable(f"{projet}-appli-1", [
        "--label", f"com.docker.compose.project={projet}",
        "--label", "com.docker.compose.service=appli",
        IMAGE_LEURRE, "sleep", "300",
    ])


def _valeur_alloy(noeud: dict[str, Any]) -> Any:
    """Convertit la représentation typée de l'API d'Alloy en objets Python."""
    type_ = noeud.get("type")
    if type_ == "object":
        return {paire["key"]: _valeur_alloy(paire["value"]) for paire in noeud["value"]}
    if type_ == "array":
        return [_valeur_alloy(element) for element in noeud["value"]]
    return noeud.get("value")


@BESOIN_DOCKER
class EtiquetageDesFluxDeJournaux(unittest.TestCase):
    """Alloy doit produire `service_name` = nom de service Compose, et rien d'autre."""

    # Déclarés au niveau de la classe : `setUpClass` les renseigne, et les annoncer ici
    # permet à mypy --strict de les suivre (une annotation posée sur `cls.x` ne compte pas).
    port: int
    _conteneur: ConteneurJetable
    cibles: list[dict[str, Any]]
    _leurres: list[ConteneurJetable]

    @classmethod
    def setUpClass(cls) -> None:
        cls._leurres = [_leurre(PROJET_DECLARE), _leurre(PROJET_INTRUS)]
        for leurre in cls._leurres:
            leurre.__enter__()
        cls.port = port_libre()
        cls._conteneur = ConteneurJetable("obs-test-alloy-relabel", [
            "-p", f"127.0.0.1:{cls.port}:{cls.port}",
            "-v", f"{RACINE}/alloy-config.alloy:/cfg.alloy:ro",
            "-v", "/var/run/docker.sock:/var/run/docker.sock:ro",
            "-e", f"LOGS_COMPOSE_PROJECTS={PROJET_DECLARE}",
            "--entrypoint", "/bin/alloy", IMAGE_ALLOY,
            "run", "/cfg.alloy", f"--server.http.listen-addr=0.0.0.0:{cls.port}",
            "--storage.path=/tmp/alloy",
        ])
        cls._conteneur.__enter__()
        attendre_http(f"http://127.0.0.1:{cls.port}/-/ready", timeout=60)
        # `discovery.docker` interroge le démon APRÈS l'évaluation du graphe : la première
        # lecture de l'export rend une liste vide, il faut laisser passer un cycle.
        url = f"http://127.0.0.1:{cls.port}/api/v0/web/components/discovery.relabel.containers"
        cls.cibles = []
        limite = time.monotonic() + 60
        while time.monotonic() < limite:
            composant = json.loads(attendre_http(url, timeout=30))
            sortie = next(e for e in composant["exports"] if e["name"] == "output")
            cls.cibles = _valeur_alloy(sortie["value"])
            if cls.cibles:
                break
            time.sleep(1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._conteneur.__exit__()
        for leurre in cls._leurres:
            leurre.__exit__()

    def test_le_label_service_name_vaut_le_nom_de_service_compose(self) -> None:
        """C'est CE label que Grafana interroge depuis un span (`service.name` → `service_name`).

        Avant correction, Alloy ne posait que `container` et Loki dérivait lui-même
        `service_name="monprojet-gateway-1"` (nom de CONTENEUR), alors que Tempo et
        Prometheus portent `service_name="gateway"` : la requête ne rendait aucun flux.
        """
        self.assertTrue(self.cibles, "aucun conteneur découvert : le test ne prouve rien")
        for cible in self.cibles:
            with self.subTest(conteneur=cible.get("container")):
                self.assertIn("service_name", cible)
                self.assertTrue(cible["service_name"], "service_name vide")
                # Oracle indépendant : on relit l'étiquette Compose directement auprès du
                # démon Docker. Si la règle de relabel promouvait une autre méta-étiquette
                # (le nom de conteneur, par exemple, qui était le défaut), l'égalité tomberait.
                resultat = executer([
                    "docker", "inspect", cible["container"],
                    "-f", '{{index .Config.Labels "com.docker.compose.service"}}',
                ])
                self.assertEqual(resultat.returncode, 0, resultat.stderr)
                self.assertEqual(cible["service_name"], resultat.stdout.strip())

    def test_service_name_n_est_plus_le_nom_de_conteneur(self) -> None:
        """La régression exacte de C-168.

        Loki dérivait `service_name` du nom de conteneur (`monprojet-gateway-1`) quand
        aucun label n'était fourni. Un nom de service Compose n'est jamais égal au nom de
        conteneur par défaut, qui y ajoute projet et index.
        """
        defaut = [c for c in self.cibles
                  if c["container"] == f"{c['compose_project']}-{c['service_name']}-1"]
        self.assertTrue(defaut, "aucun conteneur au nommage Compose par défaut : test non concluant")
        for cible in defaut:
            with self.subTest(conteneur=cible["container"]):
                self.assertNotEqual(cible["service_name"], cible["container"])

    def test_seuls_les_projets_compose_declares_sont_ingeres(self) -> None:
        """C-355 : 84 conteneurs de l'hôte, dont d'autres projets clients, finissaient dans Loki."""
        projets = {c.get("compose_project") for c in self.cibles}
        self.assertEqual(projets, {PROJET_DECLARE}, "seul le projet déclaré doit être ingéré")

    def test_aucun_conteneur_hors_compose_n_est_ingere(self) -> None:
        for cible in self.cibles:
            self.assertTrue(
                cible.get("compose_project"),
                f"{cible.get('container')} n'appartient à aucun projet Compose",
            )


class MotifDesChampsDerives(unittest.TestCase):
    """C-488 : plus de bouton « Voir la trace » vers une trace qui n'existe pas."""

    motif: str

    @classmethod
    def setUpClass(cls) -> None:
        sources = yaml.safe_load((RACINE / "grafana/provisioning/datasources/datasources.yaml").read_text(encoding="utf-8"))
        loki = next(s for s in sources["datasources"] if s["uid"] == "loki")
        cls.motif = loki["jsonData"]["derivedFields"][0]["matcherRegex"]

    def test_un_identifiant_de_trace_reel_est_capture(self) -> None:
        trouve = re.search(self.motif, '{"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}')
        self.assertIsNotNone(trouve)
        assert trouve is not None
        self.assertEqual(trouve.group(1), "4bf92f3577b34da6a3ce929d0e0e4736")

    def test_l_identifiant_nul_n_est_plus_capture(self) -> None:
        """Les lignes hors requête (démarrage, crons, access logs) portent l'identifiant nul."""
        for ligne in (
            '{"trace_id": "00000000000000000000000000000000"}',
            '{"trace_id":"00000000000000000000000000000000"}',
        ):
            with self.subTest(ligne=ligne):
                self.assertIsNone(re.search(self.motif, ligne))

    def test_un_identifiant_commencant_par_des_zeros_reste_capture_en_entier(self) -> None:
        trouve = re.search(self.motif, '{"trace_id": "000092f3577b34da6a3ce929d0e0e473"}')
        self.assertIsNotNone(trouve)
        assert trouve is not None
        self.assertEqual(trouve.group(1), "000092f3577b34da6a3ce929d0e0e473")

    def test_le_motif_se_comporte_pareil_dans_le_moteur_javascript_de_grafana(self) -> None:
        """Les champs dérivés sont évalués côté navigateur : le motif doit valoir en JS aussi.

        C'est la raison pour laquelle il n'emploie AUCUNE anti-référence `(?!0{32})` : elle
        serait refusée par RE2 (Go) et dépendrait du moteur côté client.
        """
        if shutil.which("node") is None:
            self.skipTest("node absent : vérification du moteur JavaScript ignorée")
        script = (
            f"const m = new RegExp({json.dumps(self.motif)});\n"
            "const reel = '{\"trace_id\": \"4bf92f3577b34da6a3ce929d0e0e4736\"}'.match(m);\n"
            "const nul  = '{\"trace_id\": \"00000000000000000000000000000000\"}'.match(m);\n"
            "console.log(JSON.stringify({reel: reel && reel[1], nul: nul && nul[1]}));\n"
        )
        resultat = subprocess.run(  # noqa: S603 - node local, script construit ici
            ["node", "-e", script], capture_output=True, text=True, check=False, timeout=60
        )
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        rendu = json.loads(resultat.stdout)
        self.assertEqual(rendu["reel"], "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertIsNone(rendu["nul"])


class SourcesDeDonneesGrafana(unittest.TestCase):
    """Les sauts d'une source à l'autre doivent interroger des étiquettes qui EXISTENT."""

    sources: list[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = yaml.safe_load(
            (RACINE / "grafana/provisioning/datasources/datasources.yaml").read_text(encoding="utf-8")
        )["datasources"]

    def _tempo(self) -> dict[str, Any]:
        return next(s for s in self.sources if s["uid"] == "tempo")

    def test_le_saut_trace_vers_journaux_n_interroge_que_service_name(self) -> None:
        """Sans `tags` explicite, Grafana ajoute `service.namespace` → `service_namespace`,
        étiquette qu'aucun flux Loki issu d'un conteneur Docker ne porte : la requête
        `{service_name="gateway", service_namespace="monprojet"}` ne rendait rien."""
        tags = self._tempo()["jsonData"]["tracesToLogsV2"]["tags"]
        self.assertEqual(tags, [{"key": "service.name", "value": "service_name"}])

    def test_le_saut_trace_vers_profil_declare_ses_etiquettes(self) -> None:
        """Sans `tags`, le bouton existe mais n'ouvre aucun profil ciblé (C-488)."""
        profils = self._tempo()["jsonData"]["tracesToProfiles"]
        self.assertIn("tags", profils)
        self.assertEqual(profils["tags"], [{"key": "service.name", "value": "service_name"}])
        self.assertTrue(profils.get("profileTypeId"))

    def test_les_uid_references_existent_tous(self) -> None:
        connus = {s["uid"] for s in self.sources}
        references: set[str] = set()
        for source in self.sources:
            for cle, valeur in (source.get("jsonData") or {}).items():
                if isinstance(valeur, dict) and "datasourceUid" in valeur:
                    references.add(valeur["datasourceUid"])
                if cle == "derivedFields":
                    references.update(champ["datasourceUid"] for champ in valeur)
                if cle == "exemplarTraceIdDestinations":
                    references.update(champ["datasourceUid"] for champ in valeur)
        self.assertEqual(references - connus, set())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

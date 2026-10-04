"""Outils partagés des tests de la pile d'observabilité.

Ces tests valident des FICHIERS DE CONFIGURATION : il n'y a pas de code applicatif à
appeler. La seule preuve qui vaille est donc de faire lire chaque fichier par le binaire
qui le lira en production — `promtool`, `amtool`, `loki -verify-config`, `otelcol
validate`, `alloy` — et de vérifier le COMPORTEMENT obtenu, pas la présence d'une chaîne.
Les binaires viennent des images versionnées dans `docker-compose.yml`, pour que le test
et la production ne divergent jamais.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Final

RACINE: Final[Path] = Path(__file__).resolve().parent.parent

# Images alignées sur docker-compose.yml : un test qui valide avec une autre version ne
# prouve rien sur ce qui tourne réellement.
IMAGE_PROMETHEUS: Final[str] = "prom/prometheus:v3.1.0"
IMAGE_ALERTMANAGER: Final[str] = "prom/alertmanager:v0.27.0"
IMAGE_LOKI: Final[str] = "grafana/loki:3.3.2"
IMAGE_TEMPO: Final[str] = "grafana/tempo:2.7.0"
IMAGE_COLLECTOR: Final[str] = "otel/opentelemetry-collector-contrib:0.116.1"
IMAGE_ALLOY: Final[str] = "grafana/alloy:v1.6.1"
IMAGE_BLACKBOX: Final[str] = "prom/blackbox-exporter:v0.25.0"
# Générateur de règles SLO. Épinglé sur la MÊME version que `slo/regenerer.sh` : un
# binaire local d'une autre version produit un fichier différent à chaque exécution,
# et la porte anti-dérive se mettrait à échouer pour une raison sans rapport.
IMAGE_SLOTH: Final[str] = "ghcr.io/slok/sloth:v0.16.0"


def docker_disponible() -> bool:
    """Vrai si un démon Docker répond — sinon les tests d'exécution sont ignorés."""
    if shutil.which("docker") is None:
        return False
    resultat = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return resultat.returncode == 0


# Pas d'annotation explicite : le type inféré de `skipUnless` conserve la signature de la
# fonction décorée, ce qu'un `Any` effacerait (mypy déclarerait alors chaque test « non typé »).
BESOIN_DOCKER = unittest.skipUnless(
    docker_disponible(), "démon Docker indisponible : validation par les binaires réels ignorée"
)


def executer(commande: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Lance une commande et rend son résultat complet (sans lever sur code non nul)."""
    return subprocess.run(commande, capture_output=True, text=True, check=False, timeout=timeout)


def port_libre() -> int:
    """Réserve un port éphémère sur la boucle locale et rend son numéro."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prise:
        prise.bind(("127.0.0.1", 0))
        return int(prise.getsockname()[1])


def attendre_http(url: str, *, timeout: float = 60.0) -> str:
    """Interroge `url` jusqu'à obtenir une réponse, ou lève au bout de `timeout`."""
    limite = time.monotonic() + timeout
    derniere: Exception | None = None
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(url, timeout=5) as reponse:  # noqa: S310 - URL locale de test
                corps: bytes = reponse.read()
                return corps.decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, TimeoutError) as erreur:  # pragma: no cover
            derniere = erreur
            time.sleep(0.5)
    raise TimeoutError(f"{url} n'a pas répondu en {timeout:.0f} s ({derniere})")


def lire_json(chemin: Path) -> Any:
    """Charge un JSON en UTF-8 (les dashboards contiennent des accents)."""
    return json.loads(chemin.read_text(encoding="utf-8"))


def texte(chemin_relatif: str) -> str:
    """Contenu texte d'un fichier de la pile, chemin relatif à `observability/`."""
    return (RACINE / chemin_relatif).read_text(encoding="utf-8")


# Unités de durée acceptées par Prometheus et Loki, de la plus grande à la plus petite.
_SECONDES_PAR_UNITE: Final[dict[str, float]] = {
    "w": 604800.0,
    "d": 86400.0,
    "h": 3600.0,
    "m": 60.0,
    "s": 1.0,
    "ms": 0.001,
}


def duree_en_heures(valeur: str) -> float:
    """Convertit une durée Prometheus/Loki en heures, quelle que soit son écriture.

    Indispensable dès qu'on compare un FICHIER à la configuration EFFECTIVE d'un serveur :
    Loki relit `24h` et le réaffiche `1d`, relit `2160h` et le réaffiche `90d`. Comparer
    les chaînes ferait échouer un test sur une différence de mise en forme alors que la
    durée, elle, est exactement celle qu'on demande — un faux positif qui décrédibilise la
    suite entière.
    """
    reste = valeur.strip()
    if not reste:
        raise ValueError("durée vide")
    total = 0.0
    while reste:
        correspondance = re.match(r"(\d+(?:\.\d+)?)(ms|[wdhms])", reste)
        if correspondance is None:
            raise ValueError(f"durée illisible : {valeur!r}")
        total += float(correspondance.group(1)) * _SECONDES_PAR_UNITE[correspondance.group(2)]
        reste = reste[correspondance.end():]
    return total / 3600.0


class ConteneurJetable:
    """Conteneur de test démarré puis supprimé, quoi qu'il arrive.

    Volontairement indépendant de la pile qui tourne : aucun test ne doit toucher aux
    conteneurs `observability-*` ni `sgfe-*` en service.
    """

    def __init__(self, nom: str, arguments: list[str]) -> None:
        self.nom = nom
        self._arguments = arguments

    def __enter__(self) -> ConteneurJetable:
        executer(["docker", "rm", "-f", self.nom])
        resultat = executer(["docker", "run", "--rm", "-d", "--name", self.nom, *self._arguments])
        if resultat.returncode != 0:
            raise RuntimeError(f"démarrage de {self.nom} impossible : {resultat.stderr}")
        return self

    def __exit__(self, *_: object) -> None:
        executer(["docker", "rm", "-f", self.nom])

    def journaux(self) -> str:
        """Sortie standard et d'erreur cumulées du conteneur."""
        resultat = executer(["docker", "logs", self.nom])
        return resultat.stdout + resultat.stderr

    def attendre_journal(self, marqueur: str, *, timeout: float = 60.0) -> str:
        """Attend que `marqueur` apparaisse dans les journaux, et rend le journal complet.

        Lire les journaux une seule fois juste après `/-/ready` rend le test dépendant de
        la charge de la machine : un serveur HTTP peut répondre avant que la ligne attendue
        ne soit écrite. On attend donc l'ÉVÉNEMENT, pas un délai — et, s'il ne vient jamais,
        le test échoue quand même, avec le journal entier sous les yeux.
        """
        limite = time.monotonic() + timeout
        journal = ""
        while time.monotonic() < limite:
            journal = self.journaux()
            if marqueur in journal:
                return journal
            time.sleep(0.5)
        return journal


def env_test() -> dict[str, str]:
    """Environnement minimal pour que `docker compose config` résolve les variables."""
    environnement = dict(os.environ)
    environnement.setdefault("GRAFANA_ADMIN_PASSWORD", "test-non-secret")
    environnement.setdefault("GT_DB_PASSWORD", "test-non-secret")
    environnement.setdefault("GT_SECRET_KEY", "test-non-secret")
    return environnement

"""Les tableaux de bord interrogent-ils des séries qui EXISTENT ? (constat C-173)

Un dashboard ne « casse » jamais : il affiche « No data », ce qui ressemble à du calme. Les
sept écrans du socle en étaient là — `metier.json` interrogeait une convention `metier_*`
qu'aucun composant du projet observé n'émettait, `slo.json` montrait la conformité de
l'application de DÉMONSTRATION, et le panneau Web Vitals agrégeait `by (name)` une étiquette que le récepteur
Faro n'écrit pas (557 mesures pliées sous une série vide `{}`).

Deux familles de contrôles, dans l'ordre de ce qui peut mentir :
  1. la SYNTAXE, relue par les moteurs réels — `promtool` pour PromQL, Loki pour LogQL ;
  2. la RÉFÉRENCE : toute règle d'enregistrement et toute source de données citée existe.
L'accord entre les écrans d'un projet et les compteurs qu'il émet se vérifie dans le dépôt de
ce projet, qui fournit l'un et l'autre (README, « Ce que le projet fournit »).
"""

from __future__ import annotations

import fnmatch
import re
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterator

import yaml

from outils import (
    BESOIN_DOCKER,
    IMAGE_LOKI,
    IMAGE_PROMETHEUS,
    RACINE,
    ConteneurJetable,
    attendre_http,
    executer,
    lire_json,
    port_libre,
)

DASHBOARDS: Path = RACINE / "grafana/provisioning/dashboards"

# Règles d'enregistrement que Sloth (v0.16) produit pour tout SLO. Le socle ne les définit pas :
# elles viennent des SLO générés — ceux de la démo (`rules-slo.yml`, git-ignoré) ou ceux que le
# projet monte dans `rules/consommateur/`. Les nommer ici garde le contrôle des fautes de frappe.
REGLES_SLOTH: frozenset[str] = frozenset({
    "slo:current_burn_rate:ratio", "slo:error_budget:ratio", "slo:objective:ratio",
    "slo:period_burn_rate:ratio", "slo:period_error_budget_remaining:ratio",
    "slo:time_period:days", "sloth_slo_info",
    *(f"slo:sli_error:ratio_rate{fenetre}" for fenetre in
      ("5m", "30m", "1h", "2h", "6h", "1d", "3d", "30d")),
})


def _concretiser(expression: str) -> str:
    """Remplace les variables de Grafana par des valeurs littérales.

    Les moteurs PromQL et LogQL ne connaissent pas `$__interval` ni les variables de
    tableau de bord : sans cette substitution, on testerait la syntaxe de Grafana et non
    celle de la requête. Les valeurs choisies sont sans importance — seule la structure de
    l'expression est vérifiée ici.
    """
    expression = re.sub(r"\$__(rate_)?interval|\$__range|\$__auto", "5m", expression)
    expression = re.sub(r"\$\{?__from\}?|\$\{?__to\}?", "0", expression)
    return re.sub(r"\$\{(\w+)(:\w+)?\}|\$(\w+)", "sonde", expression)


def _panneaux(dashboard: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Parcourt les panneaux, y compris ceux repliés dans une ligne."""
    for panneau in dashboard.get("panels") or []:
        yield panneau
        yield from _panneaux(panneau)


def _requetes(fichier: Path) -> Iterator[tuple[str, str, str]]:
    """Rend (titre du panneau, uid de la source, expression) pour chaque requête."""
    dashboard = lire_json(fichier)
    for panneau in _panneaux(dashboard):
        for cible in panneau.get("targets") or []:
            expression = cible.get("expr")
            if not expression:
                continue
            uid = (cible.get("datasource") or {}).get("uid") or ""
            yield panneau.get("title", "(sans titre)"), uid, expression


def _tous_les_dashboards() -> list[Path]:
    return sorted(DASHBOARDS.rglob("*.json"))


class StructureDesTableauxDeBord(unittest.TestCase):
    """Ce qui se vérifie sans démarrer quoi que ce soit."""

    def test_chaque_fichier_est_un_dashboard_lisible(self) -> None:
        fichiers = _tous_les_dashboards()
        self.assertTrue(fichiers, "aucun dashboard provisionné")
        for fichier in fichiers:
            with self.subTest(dashboard=fichier.name):
                dashboard = lire_json(fichier)
                self.assertTrue(dashboard.get("title"))
                self.assertTrue(dashboard.get("uid"))

    def test_les_identifiants_sont_uniques(self) -> None:
        """Deux dashboards de même `uid` : Grafana n'en provisionne qu'un, sans le dire."""
        vus: dict[str, str] = {}
        for fichier in _tous_les_dashboards():
            uid = lire_json(fichier)["uid"]
            self.assertNotIn(uid, vus, f"{fichier.name} et {vus.get(uid)} partagent l'uid {uid}")
            vus[uid] = fichier.name

    def test_chaque_source_de_donnees_citee_est_provisionnee(self) -> None:
        sources = yaml.safe_load(
            (RACINE / "grafana/provisioning/datasources/datasources.yaml").read_text(encoding="utf-8")
        )["datasources"]
        connus = {source["uid"] for source in sources}
        for fichier in _tous_les_dashboards():
            for titre, uid, _ in _requetes(fichier):
                with self.subTest(dashboard=fichier.name, panneau=titre):
                    self.assertIn(uid, connus)

    def test_chaque_dossier_declare_par_le_fournisseur_existe(self) -> None:
        """Un `path` erroné se solde par un dossier Grafana vide, sans erreur visible."""
        fournisseurs = {
            declaration["name"]: Path(declaration["options"]["path"])
            for fichier in sorted(DASHBOARDS.glob("*.yaml"))
            for declaration in yaml.safe_load(fichier.read_text(encoding="utf-8"))["providers"]
        }
        self.assertEqual(set(fournisseurs), {"socle", "consommateur"})
        for nom, chemin in fournisseurs.items():
            with self.subTest(fournisseur=nom):
                self.assertTrue((DASHBOARDS / chemin.name).is_dir(), f"{chemin.name} n'existe pas")
        self.assertTrue(sorted((DASHBOARDS / "socle").glob("*.json")), "le socle n'a aucun écran")
        # Le point de montage du projet reste VIDE dans le dépôt : le `.gitkeep`, rien d'autre.
        self.assertEqual(
            [f.name for f in (DASHBOARDS / "consommateur").iterdir()], [".gitkeep"]
        )

    def test_toute_regle_d_enregistrement_citee_est_definie(self) -> None:
        """`instance:…`, `slo:…` ne viennent d'aucun exportateur : une faute de frappe y
        produit un panneau définitivement vide."""
        definies: set[str] = set(REGLES_SLOTH)
        for fichier in (RACINE / "prometheus" / "rules").glob("*.yml"):
            contenu = yaml.safe_load(fichier.read_text(encoding="utf-8"))
            for groupe in contenu.get("groups") or []:
                definies.update(
                    regle["record"] for regle in groupe.get("rules") or [] if "record" in regle
                )

        motif = re.compile(r"\b([a-z_][a-z0-9_]*:[a-z0-9_:]+)")
        for fichier in _tous_les_dashboards():
            for titre, uid, expression in _requetes(fichier):
                if uid != "prometheus":
                    continue
                for nom in motif.findall(expression):
                    with self.subTest(dashboard=fichier.name, panneau=titre, regle=nom):
                        self.assertIn(nom, definies)


class ContenuDesTableauxDeBord(unittest.TestCase):
    """C-173 : les écrans doivent lire les champs réellement écrits."""

    def test_le_panneau_web_vitals_lit_les_champs_reellement_ecrits(self) -> None:
        """Le récepteur Faro écrit `kind=measurement type=web-vitals lcp=… fcp=…` : UN CHAMP
        PAR MESURE, sans champ `name` ni `value`. L'ancienne requête `unwrap value … by
        (name)` ne pouvait donc rendre qu'une série vide."""
        requetes = [
            expression
            for titre, uid, expression in _requetes(DASHBOARDS / "socle" / "gateway.json")
            if uid == "loki" and "measurement" in expression
        ]
        self.assertTrue(requetes, "le panneau Web Vitals a disparu")
        mesures = {"lcp", "fcp", "ttfb", "inp", "cls"}
        for expression in requetes:
            self.assertNotIn("unwrap value", expression)
            self.assertNotIn("by (name)", expression)
            self.assertIn('type="web-vitals"', expression)
        deballees = {
            correspondance.group(1)
            for expression in requetes
            for correspondance in [re.search(r"unwrap (\w+)", expression)]
            if correspondance
        }
        self.assertEqual(deballees, mesures)


class OperationsGraphQLDuGateway(unittest.TestCase):
    """Le tableau gateway lit les dimensions GraphQL que le Collector produit RÉELLEMENT.

    Le Collector écrit `graphql.operation.name` ; l'exportateur remote-write en fait
    `graphql_operation_name`. Une étiquette mal recopiée ne lève aucune erreur : le panneau
    reste vide, ce qui ressemble à « aucune opération ».
    """

    def test_latence_et_erreurs_sont_ventilees_par_operation(self) -> None:
        dimensions = {
            dimension["name"].replace(".", "_")
            for dimension in yaml.safe_load(
                (RACINE / "otel-collector-config.yaml").read_text(encoding="utf-8")
            )["connectors"]["spanmetrics"]["dimensions"]
        }
        self.assertEqual(dimensions, {"graphql_operation_type", "graphql_operation_name"})
        requetes = [
            expression
            for _, uid, expression in _requetes(DASHBOARDS / "socle" / "gateway.json")
            if uid == "prometheus" and "graphql_operation" in expression
        ]
        ventilees = [e for e in requetes if all(d in e for d in dimensions)]
        self.assertTrue(
            any("duration_milliseconds_bucket" in e for e in ventilees),
            "aucune latence ventilée par opération GraphQL",
        )
        self.assertTrue(
            any("STATUS_CODE_ERROR" in e for e in ventilees),
            "aucun taux d'erreur ventilé par opération GraphQL",
        )
        for expression in requetes:
            for etiquette in re.findall(r"graphql_operation_\w+", expression):
                with self.subTest(etiquette=etiquette):
                    self.assertIn(etiquette, dimensions)


@BESOIN_DOCKER
class SyntaxeDesRequetes(unittest.TestCase):
    """Les expressions sont relues par les moteurs qui les exécuteront."""

    def test_toutes_les_requetes_promql_sont_analysables(self) -> None:
        """`promtool check rules` fait analyser chaque expression par le parseur de Prometheus."""
        regles: list[dict[str, str]] = []
        index: list[tuple[str, str]] = []
        for fichier in _tous_les_dashboards():
            for titre, uid, expression in _requetes(fichier):
                if uid != "prometheus":
                    continue
                nom = f"verification:panneau{len(regles)}:requete"
                regles.append({"record": nom, "expr": _concretiser(expression)})
                index.append((f"{fichier.name} → {titre}", expression))
        self.assertTrue(regles, "aucune requête PromQL trouvée")

        chemin = RACINE / "tests" / ".requetes-dashboards.yml"
        try:
            chemin.write_text(
                yaml.safe_dump({"groups": [{"name": "verification", "rules": regles}]},
                               allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            resultat = executer([
                "docker", "run", "--rm", "-v", f"{chemin}:/regles.yml:ro",
                "--entrypoint", "promtool", IMAGE_PROMETHEUS, "check", "rules", "/regles.yml",
            ])
            detail = resultat.stdout + resultat.stderr
            for rang, (origine, expression) in enumerate(index):
                if f"panneau{rang}:" in detail and "FAILED" in detail:
                    detail += f"\n→ {origine} : {expression}"
            self.assertEqual(resultat.returncode, 0, detail)
        finally:
            chemin.unlink(missing_ok=True)

    def test_toutes_les_requetes_logql_sont_analysables(self) -> None:
        """Loki lui-même refuse une requête mal formée par un 400 « parse error ».

        Contrôle indispensable : `count by (…) ({…} [5m])` — qui semble naturel — est refusé
        par LogQL (« unexpected RANGE »), et le panneau concerné n'avait jamais rien affiché.
        """
        requetes = [
            (fichier.name, titre, expression)
            for fichier in _tous_les_dashboards()
            for titre, uid, expression in _requetes(fichier)
            if uid == "loki"
        ]
        self.assertTrue(requetes, "aucune requête LogQL trouvée")

        port = port_libre()
        with ConteneurJetable("obs-test-loki-logql", [
            "-p", f"127.0.0.1:{port}:3100",
            "-v", f"{RACINE}/loki-config.yaml:/etc/loki/config.yaml:ro",
            IMAGE_LOKI, "-config.file=/etc/loki/config.yaml",
        ]):
            attendre_http(f"http://127.0.0.1:{port}/ready", timeout=120)
            fin = int(time.time())
            for fichier, titre, expression in requetes:
                with self.subTest(dashboard=fichier, panneau=titre):
                    parametres = urllib.parse.urlencode({
                        "query": _concretiser(expression),
                        "start": f"{fin - 300}000000000",
                        "end": f"{fin}000000000",
                        "step": "60",
                        "limit": "1",
                    })
                    url = f"http://127.0.0.1:{port}/loki/api/v1/query_range?{parametres}"
                    try:
                        with urllib.request.urlopen(url, timeout=30) as reponse:  # noqa: S310
                            self.assertEqual(reponse.status, 200)
                    except urllib.error.HTTPError as erreur:
                        corps = erreur.read().decode("utf-8", "replace")
                        self.fail(f"Loki refuse la requête ({erreur.code}) : {corps}\n{expression}")


@BESOIN_DOCKER
class SondesDeLApplicationObservee(unittest.TestCase):
    """C-172 : la plateforme doit sonder l'application consommatrice, pas seulement elle-même."""

    def test_blackbox_accepte_ses_modules(self) -> None:
        resultat = executer([
            "docker", "run", "--rm",
            "-v", f"{RACINE}/blackbox.yml:/etc/blackbox_exporter/config.yml:ro",
            "prom/blackbox-exporter:v0.25.0", "--config.check",
            "--config.file=/etc/blackbox_exporter/config.yml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_prometheus_declare_des_cibles_de_l_application(self) -> None:
        """Les jobs existent, et chacun sait relire le fichier que son profil écrira.

        `blackbox-demo` vit dans `scrape.d/` depuis qu'il est sorti de l'image : on lit donc
        les jobs comme Prometheus en compose, fichier principal ET `scrape_config_files`.
        """
        dossier = RACINE / "prometheus"
        configuration = yaml.safe_load((dossier / "prometheus.yml").read_text(encoding="utf-8"))
        travaux = list(configuration["scrape_configs"])
        for motif in configuration.get("scrape_config_files") or []:
            for fichier in sorted(dossier.glob(motif)):
                travaux += yaml.safe_load(fichier.read_text(encoding="utf-8"))["scrape_configs"]
        jobs = {travail["job_name"]: travail for travail in travaux}
        # La démonstration de ce dépôt ne voyage pas dans l'image.
        for nom in (travail["job_name"] for travail in configuration["scrape_configs"]):
            with self.subTest(job_de_l_image=nom):
                self.assertNotIn("demo", nom.lower())
        for attendu in ("blackbox-application-graphql", "blackbox-application-http", "alertmanager",
                        "consommateur"):
            with self.subTest(job=attendu):
                self.assertIn(attendu, jobs)

        # La cible GraphQL était la SEULE cible versionnée non vide, et c'était un défaut :
        # partout où le consommateur ne tourne pas sur `obs-edge`, la sonde échoue vraiment et
        # `ProbeDown` (severity=page) sonne en permanence — le défaut qu'on venait de
        # corriger sur `demo.yml`, reproduit ailleurs. Elle vaut « [] » et s'active par
        # profil ; ce qui doit être prouvé, c'est que le job relira bien ce que le profil
        # écrit, sinon l'activation serait sans effet.
        for job, modele, ecrit in (
            ("blackbox-application-graphql", "application-graphql.yml.example",
             "application-graphql.local.yml"),
            ("blackbox-demo", "demo.yml.example", "demo.local.yml"),
        ):
            with self.subTest(job=job, modele=modele):
                cibles = yaml.safe_load(
                    (RACINE / "prometheus" / "targets" / modele).read_text(encoding="utf-8")
                )
                self.assertTrue(cibles and cibles[0]["targets"], f"{modele} n'active rien")
                motifs = [
                    motif
                    for decouverte in jobs[job]["file_sd_configs"]
                    for motif in decouverte["files"]
                ]
                self.assertTrue(
                    any(
                        fnmatch.fnmatch(f"/etc/prometheus/targets/{ecrit}", motif)
                        for motif in motifs
                    ),
                    f"{job} ne lirait pas {ecrit} (motifs : {motifs})",
                )

        # Le point d'entrée des cibles fournies par le projet : le job lit le répertoire
        # qu'il monte, et le dépôt n'y met rien d'autre que le point de montage.
        self.assertEqual(
            jobs["consommateur"]["file_sd_configs"],
            [{"files": ["/etc/prometheus/targets/consommateur/*.yml"]}],
        )
        self.assertEqual(
            [f.name for f in (dossier / "targets" / "consommateur").iterdir()], [".gitkeep"]
        )

    def test_les_cibles_de_la_demonstration_ne_sont_pas_actives_par_defaut(self) -> None:
        """Deux `ProbeDown` (severity=page) permanents venaient de ce fichier."""
        demo = yaml.safe_load(
            (RACINE / "prometheus" / "targets" / "demo.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(demo, [])
        exemple = yaml.safe_load(
            (RACINE / "prometheus" / "targets" / "demo.yml.example").read_text(encoding="utf-8")
        )
        self.assertTrue(exemple[0]["targets"], "le profil démo doit rester activable")

    def test_le_module_graphql_distingue_une_reponse_valide_d_une_page_d_erreur(self) -> None:
        """Un 200 ne suffit pas : une passerelle qui rend du HTML en 200 serait comptée saine.

        On sonde deux serveurs locaux — l'un répond comme une passerelle GraphQL, l'autre
        rend un 200 sans le corps attendu — et l'on vérifie que `probe_success` les sépare.
        """
        import http.server
        import threading

        class _Passerelle(http.server.BaseHTTPRequestHandler):
            corps = b'{"data":{"__typename":"Query"}}'

            def do_POST(self) -> None:  # noqa: N802 - imposé par BaseHTTPRequestHandler
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(self.corps)

            def log_message(self, *_: object) -> None:
                """Silence."""

        class _PageDErreur(_Passerelle):
            corps = b"<html><body>502 Bad Gateway</body></html>"

        serveurs = []
        for classe in (_Passerelle, _PageDErreur):
            port = port_libre()
            serveur = http.server.ThreadingHTTPServer(("0.0.0.0", port), classe)
            threading.Thread(target=serveur.serve_forever, daemon=True).start()
            self.addCleanup(serveur.server_close)
            self.addCleanup(serveur.shutdown)
            serveurs.append(port)

        port_blackbox = port_libre()
        with ConteneurJetable("obs-test-blackbox-graphql", [
            "-p", f"127.0.0.1:{port_blackbox}:9115",
            "--add-host", "host.docker.internal:host-gateway",
            "-v", f"{RACINE}/blackbox.yml:/etc/blackbox_exporter/config.yml:ro",
            "prom/blackbox-exporter:v0.25.0",
            "--config.file=/etc/blackbox_exporter/config.yml",
        ]):
            attendre_http(f"http://127.0.0.1:{port_blackbox}/-/healthy", timeout=60)
            resultats = []
            for port in serveurs:
                cible = urllib.parse.quote(f"http://host.docker.internal:{port}/graphql", safe="")
                metriques = attendre_http(
                    f"http://127.0.0.1:{port_blackbox}/probe?module=http_graphql&target={cible}",
                    timeout=30,
                )
                ligne = next(m for m in metriques.splitlines() if m.startswith("probe_success "))
                resultats.append(float(ligne.split()[1]))

        self.assertEqual(resultats[0], 1.0, "une vraie réponse GraphQL doit être comptée saine")
        self.assertEqual(resultats[1], 0.0, "un 200 sans corps GraphQL ne doit PAS compter comme sain")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

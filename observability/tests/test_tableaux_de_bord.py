"""Les tableaux de bord interrogent-ils des séries qui EXISTENT ? (constat C-173)

Un dashboard ne « casse » jamais : il affiche « No data », ce qui ressemble à du calme. Les
sept écrans du socle en étaient là — `metier.json` interrogeait une convention `metier_*`
qu'aucun composant SGFE n'émet, `slo.json` montrait la conformité de l'application de
DÉMONSTRATION, et le panneau Web Vitals agrégeait `by (name)` une étiquette que le récepteur
Faro n'écrit pas (557 mesures pliées sous une série vide `{}`).

Trois familles de contrôles, dans l'ordre de ce qui peut mentir :
  1. la SYNTAXE, relue par les moteurs réels — `promtool` pour PromQL, Loki pour LogQL ;
  2. la RÉFÉRENCE : toute règle d'enregistrement et toute source de données citée existe ;
  3. l'ACCORD AVEC LE PRODUCTEUR : les compteurs `sgfe_*` affichés sont ceux que les neuf
     composants déclarent réellement dans leur code.
"""

from __future__ import annotations

import difflib
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
    IMAGE_SLOTH,
    RACINE,
    ConteneurJetable,
    attendre_http,
    executer,
    lire_json,
    port_libre,
)

DASHBOARDS: Path = RACINE / "grafana/provisioning/dashboards"

# Dépôt du projet consommateur, à côté de celui de la plateforme sur le poste de travail.
# Absent en intégration continue : les contrôles qui en dépendent se déclarent ignorés
# plutôt que de prétendre avoir vérifié quelque chose.
BACKEND_SGFE: Path = Path.home() / "Documents" / "SGFE" / "SGFE-backend"

# Séries que le consommateur n'émet PAS encore et que la plateforme réclame explicitement :
# `SGFECronsNonInstrumentes` (prometheus/rules/sgfe.yml) sonne tant qu'elles n'existent pas.
# Les afficher est le seul moyen de voir la lacune se combler ; les interdire ici reviendrait
# à obliger la plateforme à ne demander que ce qu'on lui donne déjà.
ATTENDUS_DU_BACKEND: frozenset[str] = frozenset({"sgfe_cron_last_success_timestamp_seconds"})


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
        fournisseur = yaml.safe_load(
            (DASHBOARDS / "provider.yaml").read_text(encoding="utf-8")
        )["providers"]
        self.assertGreaterEqual(len(fournisseur), 2, "le dossier SGFE doit être provisionné")
        for declaration in fournisseur:
            chemin = Path(declaration["options"]["path"])
            with self.subTest(fournisseur=declaration["name"]):
                local = DASHBOARDS / chemin.name
                self.assertTrue(local.is_dir(), f"{local} n'existe pas")
                self.assertTrue(sorted(local.glob("*.json")), f"{local} ne contient aucun dashboard")

    def test_toute_regle_d_enregistrement_citee_est_definie(self) -> None:
        """`instance:…`, `sgfe:…`, `slo:…` ne viennent d'aucun exportateur : une faute de
        frappe y produit un panneau définitivement vide."""
        definies: set[str] = set()
        for fichier in (RACINE / "prometheus" / "rules").glob("*.yml"):
            contenu = yaml.safe_load(fichier.read_text(encoding="utf-8"))
            for groupe in contenu.get("groups") or []:
                definies.update(
                    regle["record"] for regle in groupe.get("rules") or [] if "record" in regle
                )
        self.assertIn("sgfe:composant_attendu:info", definies, "les règles SGFE ne sont pas chargées")

        motif = re.compile(r"\b([a-z_][a-z0-9_]*:[a-z0-9_:]+)")
        for fichier in _tous_les_dashboards():
            for titre, uid, expression in _requetes(fichier):
                if uid != "prometheus":
                    continue
                for nom in motif.findall(expression):
                    with self.subTest(dashboard=fichier.name, panneau=titre, regle=nom):
                        self.assertIn(nom, definies)


class ContenuMetierDesTableauxDeBord(unittest.TestCase):
    """C-173 : les écrans doivent parler des séries de CE projet, pas d'un autre."""

    # Déclaré au niveau de la classe : `setUpClass` le renseigne, et l'annoncer ici permet
    # à mypy --strict de le suivre (une annotation posée sur `cls.x` ne compte pas).
    expressions_sgfe: list[tuple[str, str, str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.expressions_sgfe = [
            (fichier.name, titre, expression)
            for fichier in sorted((DASHBOARDS / "sgfe").glob("*.json"))
            for titre, uid, expression in _requetes(fichier)
            if uid == "prometheus"
        ]

    def test_un_dossier_sgfe_est_provisionne(self) -> None:
        self.assertTrue(sorted((DASHBOARDS / "sgfe").glob("*.json")))

    def test_les_ecrans_sgfe_n_interrogent_aucune_convention_etrangere(self) -> None:
        """`metier_*` (convention du socle), `pg_*` et `rabbitmq_*` n'existent pas ici :
        SGFE émet `sgfe_*`, stocke dans PostgreSQL sans exportateur branché, et utilise
        Redis Streams — pas RabbitMQ."""
        for fichier, titre, expression in self.expressions_sgfe:
            with self.subTest(dashboard=fichier, panneau=titre):
                for prefixe in ("metier_", "pg_", "rabbitmq_", "units-service"):
                    self.assertNotIn(prefixe, expression)

    def test_les_compteurs_affiches_sont_ceux_que_le_backend_declare(self) -> None:
        """L'accord entre l'écran et le producteur, vérifié sur le code du producteur.

        C'est le contrôle qui manquait : `metier_tickets_crees_total` était syntaxiquement
        irréprochable et ne correspondait à aucun instrument déclaré.
        """
        if not BACKEND_SGFE.is_dir():
            self.skipTest(f"dépôt du consommateur absent ({BACKEND_SGFE})")
        declares: set[str] = set()
        for source in BACKEND_SGFE.rglob("metrics.py"):
            for point in re.findall(r'"(sgfe\.[a-z0-9_.]+)"', source.read_text(encoding="utf-8")):
                # Le Collector traduit les points en tirets bas et suffixe les compteurs.
                declares.add(point.replace(".", "_"))
        self.assertTrue(declares, "aucun instrument trouvé dans le dépôt du consommateur")

        # Majuscules comprises : l'unité déclarée au SDK est reprise telle quelle dans le
        # nom exporté (`sgfe_paiement_montant_encaisse_FCFA_total`).
        motif = re.compile(r"\bsgfe_[A-Za-z0-9_]*[A-Za-z0-9]")
        for fichier, titre, expression in self.expressions_sgfe:
            for nom in motif.findall(expression):
                if nom.endswith(":info") or ":" in nom:
                    continue
                with self.subTest(dashboard=fichier, panneau=titre, compteur=nom):
                    # `_total` est le suffixe que Prometheus ajoute aux compteurs ; l'unité
                    # déclarée au SDK (`FCFA`) s'insère juste avant. On accepte donc le nom
                    # sans suffixe, et le même amputé de son unité.
                    racine = nom[: -len("_total")] if nom.endswith("_total") else nom
                    candidats = {racine, re.sub(r"_[A-Za-z]+$", "", racine)}
                    self.assertTrue(
                        candidats & declares or nom in ATTENDUS_DU_BACKEND,
                        f"{nom} n'est déclaré par aucun metrics.py du consommateur",
                    )

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
    """C-172 : la plateforme doit sonder SGFE, pas seulement elle-même et une démo."""

    def test_blackbox_accepte_ses_modules(self) -> None:
        resultat = executer([
            "docker", "run", "--rm",
            "-v", f"{RACINE}/blackbox.yml:/etc/blackbox_exporter/config.yml:ro",
            "prom/blackbox-exporter:v0.25.0", "--config.check",
            "--config.file=/etc/blackbox_exporter/config.yml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)

    def test_prometheus_declare_des_cibles_sgfe(self) -> None:
        """Les jobs existent, et chacun sait relire le fichier que son profil écrira."""
        configuration = yaml.safe_load(
            (RACINE / "prometheus" / "prometheus.yml").read_text(encoding="utf-8")
        )
        jobs = {travail["job_name"]: travail for travail in configuration["scrape_configs"]}
        for attendu in ("blackbox-sgfe-graphql", "blackbox-sgfe-http", "alertmanager"):
            with self.subTest(job=attendu):
                self.assertIn(attendu, jobs)

        # La cible GraphQL était la SEULE cible versionnée non vide, et c'était un défaut :
        # partout où SGFE ne tourne pas sur `obs-edge`, la sonde échoue vraiment et
        # `ProbeDown` (severity=page) sonne en permanence — le défaut qu'on venait de
        # corriger sur `demo.yml`, reproduit ailleurs. Elle vaut « [] » et s'active par
        # profil ; ce qui doit être prouvé, c'est que le job relira bien ce que le profil
        # écrit, sinon l'activation serait sans effet.
        for job, modele, ecrit in (
            ("blackbox-sgfe-graphql", "sgfe-graphql.yml.example", "sgfe-graphql.local.yml"),
            ("blackbox-demo", "demo.yml.example", "demo.local.yml"),
        ):
            with self.subTest(job=job):
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



@BESOIN_DOCKER
class SLOGeneresEtVersionnes(unittest.TestCase):
    """L'artefact Sloth versionné correspond-il encore à sa source ? (C-173)

    Le dépôt pose que les règles produites par Sloth ne sont pas commitées
    (`.gitignore` : `prometheus/rules/rules-slo.yml`). `slo-sgfe.yml` fait exception, et
    délibérément : sans lui, une installation sans binaire `sloth` n'a AUCUN SLO SGFE et les
    écrans « budget d'erreur » restent vides sans que rien ne le dise. Mais versionner un
    artefact généré crée deux sources de vérité — rien n'empêcherait `slo/sgfe.yml` de
    diverger des règles réellement chargées par Prometheus.

    C'est cette porte qui rend l'exception tenable : elle régénère depuis l'image officielle
    épinglée (celle de `slo/regenerer.sh`) et compare octet pour octet. Même principe que le
    `generated.ts` du frontend : livré, et gardé par un test.
    """

    def test_le_fichier_versionne_est_exactement_celui_que_sloth_produit(self) -> None:
        resultat = executer([
            "docker", "run", "--rm", "-v", f"{RACINE}:/w:ro", "-w", "/w",
            IMAGE_SLOTH, "generate", "-i", "slo/sgfe.yml",
        ])
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        attendu = resultat.stdout
        obtenu = (RACINE / "prometheus" / "rules" / "slo-sgfe.yml").read_text(encoding="utf-8")
        if attendu != obtenu:
            difference = "\n".join(difflib.unified_diff(
                obtenu.splitlines(), attendu.splitlines(),
                fromfile="prometheus/rules/slo-sgfe.yml (versionné)",
                tofile="sloth generate -i slo/sgfe.yml (attendu)",
                lineterm="",
            ))
            self.fail(
                "slo-sgfe.yml a dérivé de slo/sgfe.yml. Régénérer : `sh slo/regenerer.sh`.\n"
                + difference
            )

    def test_la_convention_de_versionnement_est_celle_qui_est_documentee(self) -> None:
        """Deux artefacts, deux traitements : la différence doit être voulue, pas subie."""
        for fichier, ignore in (("rules-slo.yml", True), ("slo-sgfe.yml", False)):
            with self.subTest(fichier=fichier):
                resultat = executer([
                    "git", "-C", str(RACINE), "check-ignore", "-q",
                    f"prometheus/rules/{fichier}",
                ])
                self.assertEqual(
                    resultat.returncode == 0, ignore,
                    f"{fichier} : statut Git contraire à ce que le README et regenerer.sh annoncent",
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

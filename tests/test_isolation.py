"""
Garde-fou sur l'isolation des tests.

Les services importent SessionLocal dans leur propre namespace. Si un
module est déplacé ou renommé sans mettre à jour SERVICE_MODULES dans
conftest, les tests continueraient de passer — mais en écrivant dans
la vraie base de développement.

Ces tests échouent explicitement dans ce cas.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from conftest import SERVICE_MODULES, add_candidate


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _modules_important_session_local() -> set[str]:
    """
    Trouve, par analyse statique, tous les modules de services/ qui
    importent SessionLocal.

    Volontairement statique : importer les modules pour les inspecter
    déclencherait leurs effets de bord.
    """

    trouves: set[str] = set()

    for chemin in (PROJECT_ROOT / "services").rglob("*.py"):

        arbre = ast.parse(
            chemin.read_text(encoding="utf-8"),
            filename=str(chemin),
        )

        for noeud in ast.walk(arbre):

            if not isinstance(noeud, ast.ImportFrom):
                continue

            noms = {alias.name for alias in noeud.names}

            if "SessionLocal" not in noms:
                continue

            relatif = chemin.relative_to(PROJECT_ROOT)

            trouves.add(
                ".".join(relatif.with_suffix("").parts)
            )

    return trouves


def test_tout_module_ouvrant_une_session_est_isole():
    """
    Le piège que ce test ferme : ajouter un service qui ouvre des
    sessions sans l'inscrire dans SERVICE_MODULES. Les tests
    liraient alors la vraie base de développement.
    """

    non_isoles = (
        _modules_important_session_local()
        - set(SERVICE_MODULES)
    )

    assert not non_isoles, (
        "ces modules ouvrent des sessions mais ne sont pas isolés "
        f"par conftest : {sorted(non_isoles)}"
    )


def test_les_modules_a_patcher_existent_tous():
    """
    Un nom obsolète dans SERVICE_MODULES doit casser bruyamment,
    pas être ignoré silencieusement.
    """

    for module_name in SERVICE_MODULES:

        module = importlib.import_module(module_name)

        assert hasattr(module, "SessionLocal"), (
            f"{module_name} n'expose plus SessionLocal : la liste "
            "SERVICE_MODULES de conftest est à mettre à jour."
        )


def test_le_moteur_de_matching_ecrit_bien_dans_la_base_de_test(
    session_factory,
):
    """
    Vérifie que le SessionLocal vu par le moteur pointe vers la base
    temporaire du test, et non vers data/job_assistant.db.
    """

    import services.matching.analysis as analysis

    session = session_factory()
    add_candidate(session)
    session.close()

    url = str(analysis.SessionLocal.kw["bind"].url)

    assert "test_job_assistant.db" in url, (
        f"le moteur écrit dans {url!r} au lieu de la base de test"
    )

    assert "data/job_assistant.db" not in url.replace("\\", "/")


def test_le_cache_d_alias_est_bien_reinitialise(session_factory):
    """
    Le cache d'index d'alias est global au module : sans reset entre
    les tests, le catalogue d'un test fuiterait dans le suivant.
    """

    import services.matching.normalization as normalization

    assert normalization._canonical_alias_index_cache is None

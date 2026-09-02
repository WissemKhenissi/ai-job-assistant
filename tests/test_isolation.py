"""
Garde-fou sur l'isolation des tests.

Les services importent SessionLocal dans leur propre namespace. Si un
module est déplacé ou renommé sans mettre à jour SERVICE_MODULES dans
conftest, les tests continueraient de passer — mais en écrivant dans
la vraie base de développement.

Ces tests échouent explicitement dans ce cas.
"""

from __future__ import annotations

import importlib

from conftest import SERVICE_MODULES, add_candidate


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

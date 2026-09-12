"""
Un terme écarté par l'utilisateur cesse de compter.

Écarter un terme depuis l'écran Référentiel rangeait la file de tri
sans rien changer au calcul : le terme continuait de peser comme
exigence manquante, annonce après annonce. « Anglais professionnel »,
écarté comme langue, abaissait encore chaque score.

Un jugement qu'on recueille et qu'on n'applique pas vaut moins que pas
de jugement du tout : l'utilisateur croit avoir corrigé quelque chose.

Ces tests bornent la règle — elle écarte sur décision explicite, et
sur rien d'autre.
"""

from __future__ import annotations

import pytest

from tests.conftest import add_catalog_skill

from services.requirement_cleaning import clean_required_skills
from services.skill_candidate_service import (
    IGNORE,
    ignore_candidate,
    record_unknown_terms,
    termes_ignores,
)


@pytest.fixture
def referentiel(session_factory):

    session = session_factory()

    add_catalog_skill(session, "Jira", aliases=["Jira"])
    add_catalog_skill(
        session, "Gestion de projet", aliases=["Gestion de projet"]
    )

    session.close()


def _ecarter(terme: str) -> None:
    """Enregistre un terme inconnu, puis l'écarte."""

    record_unknown_terms([terme])

    from services.skill_candidate_service import get_candidates

    for candidat in get_candidates(only_pending=True):
        if candidat["term"] == terme:
            ignore_candidate(candidat["id"])
            return

    raise AssertionError(f"terme non enregistré : {terme}")


def test_un_terme_ecarte_ne_compte_plus(referentiel):
    """
    Le défaut d'origine, dans sa forme la plus simple.
    """

    _ecarter("Anglais professionnel")

    retenues, ecartees = clean_required_skills(
        ["Jira", "Anglais professionnel"]
    )

    assert retenues == ["Jira"]
    assert "Anglais professionnel" in ecartees


def test_l_ecart_survit_a_une_autre_orthographe(referentiel):
    """
    La décision est enregistrée sous forme canonique : elle doit
    valoir quelle que soit la casse ou les accents employés par
    l'annonce suivante.
    """

    _ecarter("Anglais professionnel")

    retenues, _ = clean_required_skills(["ANGLAIS PROFESSIONNEL"])

    assert retenues == []


def test_un_terme_non_ecarte_compte_toujours(referentiel):
    """
    La règle n'écarte que sur décision explicite.
    """

    _ecarter("Anglais professionnel")

    retenues, _ = clean_required_skills(["Marketplace B2B"])

    assert retenues == ["Marketplace B2B"]


def test_un_terme_seulement_rencontre_compte_encore(referentiel):
    """
    Enregistrer un terme inconnu n'est pas le juger : tant que
    l'utilisateur n'a rien décidé, il reste une exigence.
    """

    record_unknown_terms(["Marketplace B2B"])

    retenues, _ = clean_required_skills(["Marketplace B2B"])

    assert retenues == ["Marketplace B2B"]


def test_les_formes_ecartees_sont_canoniques(referentiel):

    _ecarter("Anglais professionnel")

    formes = termes_ignores()

    assert formes
    assert all(forme == forme.casefold() for forme in formes)


def test_sans_aucune_decision_rien_n_est_ecarte(referentiel):

    assert termes_ignores() == set()

    retenues, ecartees = clean_required_skills(["Jira"])

    assert retenues == ["Jira"]
    assert ecartees == []

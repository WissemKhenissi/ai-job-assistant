"""
Refuser une exigence que le référentiel reconnaît pourtant.

record_unknown_terms ne retient que les termes qu'aucune compétence ne
reconnaît — c'est sa raison d'être : repérer les trous. Mais l'erreur
inverse existe. Une taxonomie importée en masse connaît
« écosystèmes », « moulins » et « philosophie » comme concepts, qui
deviennent des exigences dès qu'une annonce prononce le mot.

ecarter_terme ouvre la même décision à ces termes-là. Ces tests
vérifient qu'elle porte, qu'elle ne détruit rien au référentiel, et
qu'elle se défait.
"""

from __future__ import annotations

import pytest

from tests.conftest import add_catalog_skill

from services.requirement_cleaning import clean_required_skills
from services.skill_candidate_service import (
    IGNORE,
    ecarter_terme,
    get_candidates,
    termes_ignores,
    undo_decision,
)
from services.skill_catalog_service import find_skill_by_name


@pytest.fixture
def referentiel(session_factory):

    session = session_factory()

    add_catalog_skill(session, "Jira", aliases=["Jira"])
    add_catalog_skill(
        session,
        "écosystèmes",
        aliases=["écosystèmes"],
        skill_id="esco-ecosystemes",
    )

    session.close()


def test_une_competence_reconnue_peut_etre_refusee(referentiel):
    """
    Le cas qui motive la fonction : le référentiel connaît le terme,
    et c'est justement le problème.
    """

    assert find_skill_by_name("écosystèmes") is not None

    ecarter_terme("écosystèmes")

    retenues, ecartees = clean_required_skills(["Jira", "écosystèmes"])

    assert retenues == ["Jira"]
    assert "écosystèmes" in ecartees


def test_le_referentiel_n_est_pas_amputé(referentiel):
    """
    Refuser une exigence ne supprime pas la compétence : elle reste
    disponible pour le Master CV et pour le matching. Seule sa lecture
    comme exigence d'annonce est refusée.
    """

    ecarter_terme("écosystèmes")

    assert find_skill_by_name("écosystèmes") is not None


def test_la_decision_est_reversible(referentiel):
    """
    Une décision de vocabulaire se prend sur un terme sorti de son
    contexte : se tromper est facile.
    """

    ecarter_terme("écosystèmes")

    ecarte = [
        candidat
        for candidat in get_candidates(only_pending=False)
        if candidat["term"] == "écosystèmes"
    ]

    assert ecarte and ecarte[0]["status"] == IGNORE

    undo_decision(ecarte[0]["id"])

    retenues, _ = clean_required_skills(["écosystèmes"])

    assert retenues == ["écosystèmes"]


def test_refuser_deux_fois_ne_cree_qu_une_decision(referentiel):

    ecarter_terme("écosystèmes")
    ecarter_terme("ÉCOSYSTÈMES")

    lignes = [
        candidat
        for candidat in get_candidates(only_pending=False)
        if candidat["term"].casefold() == "écosystèmes"
    ]

    assert len(lignes) == 1


def test_un_terme_vide_ne_cree_rien(referentiel):

    assert ecarter_terme("   ") == ""
    assert termes_ignores() == set()

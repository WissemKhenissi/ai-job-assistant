"""
Fusion des exigences du catalogue et de celles proposées par l'IA.

La comparaison portait sur la forme des chaînes. Une annonce qui
écrit « la maîtrise de la méthode Agile est indispensable » produisait
donc deux exigences : « Agile / Scrum », reconnu par le catalogue, et
« méthode Agile », proposé par l'IA. Elles se contredisaient — l'une
prouvée, l'autre manquante et posée comme condition d'entrée — pour
une seule phrase.

Ces tests verrouillent l'arbitrage : c'est le référentiel qui dit si
deux termes désignent la même compétence, et un terme qu'il ignore
reste une exigence à part entière.
"""

from __future__ import annotations

import pytest

from tests.conftest import add_catalog_skill

from services.requirement_cleaning import merge_ai_requirements


@pytest.fixture
def referentiel(session_factory):

    session = session_factory()

    add_catalog_skill(
        session,
        "Agile / Scrum",
        aliases=["Agile / Scrum", "Agile", "Scrum", "Méthode Agile"],
    )
    add_catalog_skill(session, "Jira", aliases=["Jira"])

    session.close()


def test_un_synonyme_reconnu_ne_fait_pas_une_seconde_exigence(
    referentiel,
):
    """
    Le cas qui a motivé la fonction.
    """

    exigences = merge_ai_requirements(
        ["Agile / Scrum"],
        ["méthode Agile"],
    )

    assert exigences == ["Agile / Scrum"]


def test_une_proposition_est_ramenee_a_son_nom_canonique(referentiel):
    """
    L'IA dit « Scrum », le référentiel dit « Agile / Scrum ». C'est le
    nom du référentiel qui entre, sans quoi le moteur aurait à
    résoudre deux fois le même terme sous deux orthographes.
    """

    assert merge_ai_requirements([], ["Scrum"]) == ["Agile / Scrum"]


def test_un_terme_inconnu_du_referentiel_est_conserve(referentiel):
    """
    C'est peut-être une exigence réelle et un trou du référentiel.
    L'écarter masquerait les deux.
    """

    exigences = merge_ai_requirements(
        ["Jira"],
        ["Marketplace B2B"],
    )

    assert exigences == ["Jira", "Marketplace B2B"]


def test_l_ordre_du_catalogue_est_preserve(referentiel):
    """
    L'ordre d'apparition dans l'annonce porte une information : ce
    qu'elle cite en premier pèse davantage. Les propositions de l'IA
    s'ajoutent après, sans bousculer ce qui précède.
    """

    exigences = merge_ai_requirements(
        ["Jira", "Agile / Scrum"],
        ["Marketplace B2B"],
    )

    assert exigences == ["Jira", "Agile / Scrum", "Marketplace B2B"]


def test_deux_propositions_equivalentes_ne_comptent_qu_une_fois(
    referentiel,
):

    exigences = merge_ai_requirements([], ["Agile", "Scrum"])

    assert exigences == ["Agile / Scrum"]


def test_les_propositions_vides_sont_ignorees(referentiel):

    assert merge_ai_requirements(["Jira"], ["", "   ", None]) == ["Jira"]


def test_sans_proposition_les_exigences_ne_bougent_pas(referentiel):

    assert merge_ai_requirements(["Jira"], []) == ["Jira"]

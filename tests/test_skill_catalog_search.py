"""
Recherche plein texte dans le référentiel.

Cette fonction existe pour une raison précise : le popover « Ajouter »
de l'onglet Compétences passait les 13 476 entrées du référentiel en
options d'un `st.multiselect`. Un popover Streamlit rend son contenu
qu'il soit ouvert ou non — le catalogue entier partait donc au
navigateur à chaque affichage de l'onglet, et la page ne finissait
plus de s'afficher.

Ces tests verrouillent les deux propriétés qui empêchent le défaut de
revenir : une recherche vide ne propose rien, et une recherche large
est plafonnée sans mentir sur le nombre de correspondances.
"""

from __future__ import annotations

import pytest

from tests.conftest import add_catalog_skill

from services.skill_catalog_service import search_active_skills


@pytest.fixture
def referentiel(session_factory):

    session = session_factory()

    add_catalog_skill(
        session,
        "Agile / Scrum",
        aliases=["Agile / Scrum", "Scrum", "Kanban", "Méthode agile"],
    )
    add_catalog_skill(session, "Gestion de projet", aliases=["Gestion de projet"])
    add_catalog_skill(session, "Gestion du budget", aliases=["Gestion du budget"])
    add_catalog_skill(session, "SQL", aliases=["SQL"])

    session.close()


def test_une_recherche_vide_ne_propose_rien(referentiel):
    """
    C'est le cœur du correctif : sans terme, on ne déverse pas le
    catalogue. Le total retourné vaut zéro, pas la taille du
    référentiel.
    """

    resultats, total = search_active_skills("")

    assert resultats == []
    assert total == 0

    assert search_active_skills("   ") == ([], 0)


def test_cherche_dans_le_nom_canonique(referentiel):

    resultats, total = search_active_skills("budget")

    assert [skill.canonical_name for skill in resultats] == [
        "Gestion du budget"
    ]
    assert total == 1


def test_cherche_aussi_dans_les_alias(referentiel):
    """
    Le nom canonique est « Agile / Scrum » : quelqu'un qui tape
    « kanban » doit quand même la trouver.
    """

    resultats, _ = search_active_skills("kanban")

    assert [skill.canonical_name for skill in resultats] == [
        "Agile / Scrum"
    ]


def test_la_recherche_ignore_accents_et_casse(referentiel):

    resultats, _ = search_active_skills("METHODE AGILE")

    assert [skill.canonical_name for skill in resultats] == [
        "Agile / Scrum"
    ]


def test_les_competences_deja_declarees_sont_ecartees(referentiel):
    """
    Proposer d'ajouter une compétence que le candidat possède déjà
    n'a pas de sens.
    """

    resultats, total = search_active_skills(
        "gestion",
        exclure=("gestion de projet",),
    )

    assert [skill.canonical_name for skill in resultats] == [
        "Gestion du budget"
    ]
    assert total == 1


def test_le_nombre_de_resultats_est_plafonne(referentiel):
    """
    Une recherche large est tronquée, mais le total dit la vérité :
    l'interface peut alors demander de préciser plutôt que de laisser
    croire qu'il n'existe que deux correspondances.
    """

    resultats, total = search_active_skills("gestion", limite=1)

    assert len(resultats) == 1
    assert total == 2


def test_aucune_correspondance(referentiel):

    assert search_active_skills("radiologie") == ([], 0)

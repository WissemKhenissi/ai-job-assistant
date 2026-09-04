"""
Cloisonnement entre profils (services.profile_service).

L'application n'a longtemps connu qu'un seul candidat, et le code le
supposait : `get_candidate` prenait le premier venu, `get_experiences`
retournait le parcours de tout le monde. Tant qu'une seule fiche
existait le défaut restait invisible ; à la deuxième, les parcours se
seraient mélangés — un CV généré aurait pu porter l'expérience de
quelqu'un d'autre.

Ces tests ferment ce piège, et vérifient qu'une suppression emporte
tout ce qui pend au profil sans toucher au voisin.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import add_candidate, add_candidate_skill, add_evidence
from services.profile_service import (
    add_experience,
    count_candidate_data,
    create_candidate,
    delete_candidate,
    get_candidate,
    get_experiences,
    get_skills,
    list_candidates,
)


PREMIER = "candidate-test"
SECOND = "candidate-autre"


@pytest.fixture
def deux_profils(session_factory):
    """Deux candidats, chacun avec son parcours."""

    session = session_factory()
    add_candidate(session, candidate_id=PREMIER)
    add_candidate(session, candidate_id=SECOND)

    skill = add_candidate_skill(
        session, candidate_id=PREMIER, name="Réanimation"
    )
    add_evidence(
        session,
        candidate_id=PREMIER,
        skill_id=skill.id,
        description="Prise en charge de patients critiques.",
    )

    add_candidate_skill(
        session, candidate_id=SECOND, name="Product Discovery"
    )

    session.close()

    add_experience(
        candidate_id=PREMIER,
        company="CHU de Lyon",
        job_title="Infirmière",
        start_date=date(2019, 1, 1),
    )

    add_experience(
        candidate_id=SECOND,
        company="Groupe Meridiem",
        job_title="Chef de projet",
        start_date=date(2018, 1, 1),
    )


# ============================================================
# CLOISONNEMENT
# ============================================================

def test_chaque_profil_ne_voit_que_ses_experiences(deux_profils):
    """
    Le défaut d'origine : sans filtre, les deux parcours se
    mélangeaient.
    """

    premier = get_experiences(PREMIER)
    second = get_experiences(SECOND)

    assert [item.company for item in premier] == ["CHU de Lyon"]
    assert [item.company for item in second] == ["Groupe Meridiem"]


def test_chaque_profil_ne_voit_que_ses_competences(deux_profils):
    assert [item.name for item in get_skills(PREMIER)] == [
        "Réanimation"
    ]
    assert [item.name for item in get_skills(SECOND)] == [
        "Product Discovery"
    ]


def test_le_profil_demande_est_bien_celui_retourne(deux_profils):
    assert get_candidate(SECOND).id == SECOND
    assert get_candidate(PREMIER).id == PREMIER


def test_sans_identifiant_le_premier_profil_est_retourne(
    deux_profils,
):
    """
    Repli du démarrage, quand aucun profil n'a encore été choisi.
    """

    assert get_candidate() is not None


def test_un_identifiant_inconnu_ne_retourne_rien(deux_profils):
    assert get_candidate("candidate-fantome") is None


# ============================================================
# CREATION
# ============================================================

def test_un_profil_peut_etre_cree(session_factory):
    identifiant = create_candidate("Camille", "Durand")

    profils = list_candidates()

    assert len(profils) == 1
    assert profils[0]["id"] == identifiant
    assert profils[0]["full_name"] == "Camille Durand"


def test_un_profil_sans_nom_reste_identifiable(session_factory):
    create_candidate()

    assert list_candidates()[0]["full_name"] == "Profil sans nom"


def test_un_profil_neuf_est_vide(session_factory):
    identifiant = create_candidate("Camille", "Durand")

    assert get_experiences(identifiant) == []
    assert get_skills(identifiant) == []


# ============================================================
# SUPPRESSION
# ============================================================

def test_le_decompte_precede_la_suppression(deux_profils):
    """
    On ne détruit pas un parcours sans dire ce qu'il contenait.
    """

    decompte = count_candidate_data(PREMIER)

    assert decompte["experiences"] == 1
    assert decompte["competences"] == 1
    assert decompte["preuves"] == 1


def test_supprimer_un_profil_emporte_ses_donnees(deux_profils):
    from database.models import EvidenceDB

    delete_candidate(PREMIER)

    assert get_candidate(PREMIER) is None
    assert get_experiences(PREMIER) == []
    assert get_skills(PREMIER) == []

    from database.db import SessionLocal

    session = SessionLocal()
    restantes = (
        session.query(EvidenceDB)
        .filter(EvidenceDB.candidate_id == PREMIER)
        .count()
    )
    session.close()

    assert restantes == 0


def test_supprimer_un_profil_ne_touche_pas_a_l_autre(deux_profils):
    delete_candidate(PREMIER)

    assert get_candidate(SECOND) is not None
    assert [item.company for item in get_experiences(SECOND)] == [
        "Groupe Meridiem"
    ]
    assert len(get_skills(SECOND)) == 1


def test_la_suppression_annonce_ce_qu_elle_emporte(deux_profils):
    decompte = delete_candidate(PREMIER)

    assert decompte["experiences"] == 1
    assert decompte["preuves"] == 1


def test_supprimer_un_profil_inexistant_est_refuse(deux_profils):
    with pytest.raises(ValueError, match="introuvable"):
        delete_candidate("candidate-fantome")

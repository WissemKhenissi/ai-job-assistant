"""
Nouveaux champs d'affichage du profil (accroche, disponibilité,
langues, centres d'intérêt, localisation d'une expérience).

Ces champs ont été ajoutés par une migration ALTER TABLE sur des
tables déjà peuplées (candidat, expérience Ticketis) : ce test
verrouille le fait qu'ils sont bien écrivables/lisibles via la couche
de service, sans se substituer à une vérification manuelle de la
migration elle-même sur la vraie base.
"""

from __future__ import annotations

from datetime import date

from conftest import add_candidate


CANDIDATE_ID = "candidate-test"


def test_les_nouveaux_champs_candidat_sont_vides_par_defaut(
    session_factory,
):
    from services.profile_service import get_candidate

    session = session_factory()
    add_candidate(session)
    session.close()

    candidate = get_candidate()

    assert candidate.headline == ""
    assert candidate.availability == ""
    assert candidate.languages == ""
    assert candidate.interests == ""


def test_update_candidate_ecrit_les_nouveaux_champs(
    session_factory,
):
    from services.profile_service import get_candidate, update_candidate

    session = session_factory()
    add_candidate(session)
    session.close()

    update_candidate(
        CANDIDATE_ID,
        headline="Product / Chef de projet digital — E-commerce & Tech",
        availability="Disponible immédiatement",
        languages="Français : natif | Anglais : B2",
        interests="Entrepreneuriat • IA • Product Management",
    )

    candidate = get_candidate()

    assert candidate.headline == (
        "Product / Chef de projet digital — E-commerce & Tech"
    )
    assert candidate.availability == "Disponible immédiatement"


def test_add_experience_accepte_une_localisation(session_factory):
    from services.profile_service import add_experience, get_experiences

    session = session_factory()
    add_candidate(session)
    session.close()

    add_experience(
        candidate_id=CANDIDATE_ID,
        company="Cobalt Studio",
        job_title="Traffic Manager",
        location="Paris",
        start_date=date(2015, 1, 1),
    )

    assert get_experiences()[0].location == "Paris"


def test_une_experience_sans_localisation_reste_vide(
    session_factory,
):
    """L'ancienne façon d'appeler add_experience doit continuer de marcher."""

    from services.profile_service import add_experience, get_experiences

    session = session_factory()
    add_candidate(session)
    session.close()

    add_experience(
        candidate_id=CANDIDATE_ID,
        company="Groupe Meridiem",
        job_title="Account Manager",
        start_date=date(2016, 1, 1),
    )

    assert get_experiences()[0].location == ""

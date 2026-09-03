"""
Historique des entretiens (services.interview_history_service).

Ce que ces tests verrouillent, c'est la correction d'un défaut vécu :
les réponses ne vivaient qu'en session Streamlit et disparaissaient au
moindre rechargement, sans que rien n'ait jamais été envoyé.
"""

from __future__ import annotations

from conftest import add_candidate
from services.ai.interview import InterviewQuestion
from services.interview_history_service import (
    delete_exchange,
    get_asked_questions,
    get_exchanges,
    save_answer,
    save_questions,
)


CANDIDATE_ID = "candidate-test"


def _questions():
    return [
        InterviewQuestion(
            question="Avez-vous géré un budget ?",
            experience_id="experience-test",
            experience_label="Chef de projet — Groupe Meridiem",
        ),
        InterviewQuestion(question="Quelles langues parlez-vous ?"),
    ]


def test_les_questions_generees_sont_persistees(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    identifiants = save_questions(
        CANDIDATE_ID, _questions(), target_role="Product Owner"
    )

    assert len(identifiants) == 2

    echanges = get_exchanges(CANDIDATE_ID)

    assert len(echanges) == 2
    assert {e["question"] for e in echanges} == {
        "Avez-vous géré un budget ?",
        "Quelles langues parlez-vous ?",
    }
    assert all(e["answer"] == "" for e in echanges)


def test_une_reponse_est_enregistree_et_relisible(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    identifiants = save_questions(CANDIDATE_ID, _questions())

    save_answer(identifiants[0], "Oui, 50k€ par trimestre.")

    echanges = {e["id"]: e for e in get_exchanges(CANDIDATE_ID)}

    assert echanges[identifiants[0]]["answer"] == "Oui, 50k€ par trimestre."
    assert echanges[identifiants[1]]["answer"] == ""


def test_une_reponse_peut_etre_corrigee(session_factory):
    """Revenir compléter une réponse donnée trop vite est le besoin d'origine."""

    session = session_factory()
    add_candidate(session)
    session.close()

    identifiants = save_questions(CANDIDATE_ID, _questions())

    save_answer(identifiants[0], "Oui.")
    save_answer(identifiants[0], "Oui, un budget de 50k€ par trimestre.")

    echanges = {e["id"]: e for e in get_exchanges(CANDIDATE_ID)}

    assert (
        echanges[identifiants[0]]["answer"]
        == "Oui, un budget de 50k€ par trimestre."
    )


def test_only_answered_filtre_les_questions_sans_reponse(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    identifiants = save_questions(CANDIDATE_ID, _questions())
    save_answer(identifiants[0], "Une réponse.")

    assert len(get_exchanges(CANDIDATE_ID, only_answered=True)) == 1


def test_les_questions_posees_sont_restituees(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    save_questions(CANDIDATE_ID, _questions())

    posees = get_asked_questions(CANDIDATE_ID)

    assert "Avez-vous géré un budget ?" in posees
    assert len(posees) == 2


def test_un_echange_peut_etre_supprime(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    identifiants = save_questions(CANDIDATE_ID, _questions())

    delete_exchange(identifiants[0])

    assert len(get_exchanges(CANDIDATE_ID)) == 1


def test_l_historique_est_cloisonne_par_candidat(session_factory):
    session = session_factory()
    add_candidate(session)
    add_candidate(session, candidate_id="candidate-autre")
    session.close()

    save_questions(CANDIDATE_ID, _questions())

    assert get_exchanges("candidate-autre") == []
    assert get_asked_questions("candidate-autre") == []

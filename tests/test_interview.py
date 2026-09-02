"""
Entretien IA d'enrichissement du Master CV
(services.ai.interview).

Aucun test n'appelle la vraie API : is_configured/generate_multimodal
sont remplacés directement dans le module, comme pour les autres
tests services.ai.*.

Le garde-fou le plus important à couvrir : une proposition de preuve
dont l'extrait source ne correspond à AUCUNE réponse réellement
donnée doit être écartée — c'est ce qui empêche l'IA d'inventer un
fait qui ne serait pas retrouvable dans les mots du candidat.
"""

from __future__ import annotations

import json
from datetime import date

import services.ai.interview as interview
from conftest import add_candidate


CANDIDATE_ID = "candidate-test"
EXPERIENCE_ID = "experience-test"


def _preparer_candidat_avec_experience(session_factory):
    from database.models import ExperienceDB

    session = session_factory()
    add_candidate(session)

    session.add(
        ExperienceDB(
            id=EXPERIENCE_ID,
            candidate_id=CANDIDATE_ID,
            company="Groupe Meridiem",
            job_title="Chef de projet",
            start_date=date(2018, 1, 1),
            end_date=date(2024, 12, 31),
            description="",
            business_context="",
            team_context="",
        )
    )

    session.commit()
    session.close()


# ============================================================
# GENERATION DES QUESTIONS
# ============================================================

def test_sans_cle_configuree_retourne_un_avertissement(
    session_factory, monkeypatch
):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: False)

    questions, avertissement = interview.generate_interview_questions(
        CANDIDATE_ID
    )

    assert questions == []
    assert "GEMINI_API_KEY" in avertissement


def test_un_candidat_introuvable_retourne_un_avertissement(
    session_factory, monkeypatch
):
    session_factory()  # base vide, aucun candidat

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    questions, avertissement = interview.generate_interview_questions(
        "candidat-inconnu"
    )

    assert questions == []
    assert avertissement


def test_des_questions_valides_sont_extraites(session_factory, monkeypatch):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                {
                    "question": "Avez-vous géré un budget sur ce poste ?",
                    "experience_id": EXPERIENCE_ID,
                },
                {
                    "question": "Quelles langues parlez-vous couramment ?",
                    "experience_id": None,
                },
            ]
        ),
    )

    questions, avertissement = interview.generate_interview_questions(
        CANDIDATE_ID
    )

    assert avertissement == ""
    assert len(questions) == 2
    assert questions[0].experience_id == EXPERIENCE_ID
    assert questions[0].experience_label == "Chef de projet — Groupe Meridiem"
    assert questions[1].experience_id is None


def test_un_experience_id_inconnu_est_ignore(session_factory, monkeypatch):
    """
    Un identifiant d'expérience halluciné par l'IA (n'existant pas
    dans le Master CV) ne doit jamais être conservé tel quel.
    """

    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                {
                    "question": "Question orpheline ?",
                    "experience_id": "experience-qui-n-existe-pas",
                }
            ]
        ),
    )

    questions, _avertissement = interview.generate_interview_questions(
        CANDIDATE_ID
    )

    assert questions[0].experience_id is None


def test_une_reponse_illisible_retourne_un_avertissement(
    session_factory, monkeypatch
):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview, "generate_multimodal", lambda *a, **k: "pas du JSON"
    )

    questions, avertissement = interview.generate_interview_questions(
        CANDIDATE_ID
    )

    assert questions == []
    assert avertissement


def test_le_prompt_mentionne_le_poste_recherche(session_factory, monkeypatch):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    parts_recus = []

    def _generate_multimodal(parts, *a, **k):
        parts_recus.append(parts)
        return json.dumps([])

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    interview.generate_interview_questions(
        CANDIDATE_ID, target_role="Product Owner"
    )

    assert parts_recus
    # Le texte est encapsulé dans un Part Gemini : on vérifie sa présence
    # via la représentation du premier élément (le prompt texte).
    texte_prompt = str(parts_recus[0][0])
    assert "Product Owner" in texte_prompt


# ============================================================
# PROPOSITION DE PREUVES
# ============================================================

def _reponse(question="Q ?", answer="", experience_id=None, label=""):
    return interview.InterviewAnswer(
        question=question,
        answer=answer,
        experience_id=experience_id,
        experience_label=label,
    )


def test_aucune_reponse_ne_declenche_aucun_appel(monkeypatch):
    appele = False

    def _generate_multimodal(*a, **k):
        nonlocal appele
        appele = True
        return "[]"

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    propositions, avertissement = interview.propose_evidence_from_answers(
        [_reponse(answer="   ")]
    )

    assert propositions == []
    assert "Aucune réponse" in avertissement
    assert not appele


def test_sans_cle_configuree(monkeypatch):
    monkeypatch.setattr(interview, "is_configured", lambda: False)

    propositions, avertissement = interview.propose_evidence_from_answers(
        [_reponse(answer="J'ai géré un budget de 50k€.")]
    )

    assert propositions == []
    assert "GEMINI_API_KEY" in avertissement


def test_une_proposition_tracable_est_acceptee(monkeypatch):
    monkeypatch.setattr(interview, "is_configured", lambda: True)

    reponses = [
        _reponse(
            question="Avez-vous géré un budget ?",
            answer="Oui, j'ai géré un budget marketing de 50k€ par trimestre.",
            experience_id=EXPERIENCE_ID,
            label="Chef de projet — Groupe Meridiem",
        )
    ]

    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                {
                    "text": "Gestion d'un budget marketing de 50k€ par trimestre.",
                    "skill_name": "Gestion de budget",
                    "source_excerpt": "j'ai géré un budget marketing de 50k€ par trimestre",
                }
            ]
        ),
    )

    propositions, avertissement = interview.propose_evidence_from_answers(
        reponses
    )

    assert avertissement == ""
    assert len(propositions) == 1
    assert propositions[0].skill_name == "Gestion de budget"
    assert propositions[0].experience_id == EXPERIENCE_ID
    assert propositions[0].experience_label == "Chef de projet — Groupe Meridiem"


def test_une_proposition_non_tracable_est_ecartee(monkeypatch):
    """
    Garde-fou central : si l'extrait source cité par l'IA n'apparaît
    dans AUCUNE réponse réellement donnée, la proposition est
    rejetée — c'est ce qui empêche une invention pure et simple.
    """

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    reponses = [
        _reponse(
            question="Avez-vous géré un budget ?",
            answer="Non, ce n'était pas mon rôle.",
        )
    ]

    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                {
                    "text": "Gestion d'un budget de 200k€.",
                    "skill_name": "Gestion de budget",
                    "source_excerpt": "j'ai géré un budget de 200k€",
                }
            ]
        ),
    )

    propositions, _avertissement = interview.propose_evidence_from_answers(
        reponses
    )

    assert propositions == []


def test_une_reponse_illisible_retourne_un_avertissement_evidence(
    monkeypatch,
):
    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview, "generate_multimodal", lambda *a, **k: "pas du JSON"
    )

    propositions, avertissement = interview.propose_evidence_from_answers(
        [_reponse(answer="Une réponse quelconque.")]
    )

    assert propositions == []
    assert avertissement

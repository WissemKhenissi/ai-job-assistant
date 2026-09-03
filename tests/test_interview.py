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


def test_les_questions_d_inspiration_atteignent_le_prompt(monkeypatch):
    """
    Mode "réponse libre" : les questions générées sont transmises
    comme contexte, mais ne doivent jamais servir de source de preuve
    — seul le texte des réponses compte pour le garde-fou.
    """

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    prompts_recus = []

    def _generate_multimodal(parts, *a, **k):
        prompts_recus.append(parts[0])
        return "[]"

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    interview.propose_evidence_from_answers(
        [_reponse(answer="Réponse libre à tout.")],
        inspiration_questions=[
            interview.InterviewQuestion(question="Avez-vous géré un budget ?")
        ],
    )

    assert prompts_recus
    assert "Avez-vous géré un budget ?" in prompts_recus[0]


# ============================================================
# TRANSCRIPTION AUDIO
# ============================================================

def test_un_audio_vide_ne_declenche_aucun_appel(monkeypatch):
    appele = False

    def _generate_multimodal(*a, **k):
        nonlocal appele
        appele = True
        return "peu importe"

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    texte, avertissement = interview.transcribe_audio(b"")

    assert texte == ""
    assert avertissement == ""
    assert not appele


def test_transcription_sans_cle_configuree(monkeypatch):
    monkeypatch.setattr(interview, "is_configured", lambda: False)

    texte, avertissement = interview.transcribe_audio(b"donnees-audio")

    assert texte == ""
    assert "GEMINI_API_KEY" in avertissement


def test_transcription_reussie(monkeypatch):
    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: "J'ai géré un budget marketing de 50k€.",
    )

    texte, avertissement = interview.transcribe_audio(
        b"donnees-audio", mime_type="audio/wav"
    )

    assert texte == "J'ai géré un budget marketing de 50k€."
    assert avertissement == ""


def test_transcription_utilise_un_delai_allonge(monkeypatch):
    """
    Un enregistrement de plusieurs minutes dépasse largement le délai
    par défaut de 30 s : la transcription doit demander explicitement
    le délai long, sinon elle échoue systématiquement sur les réponses
    orales un peu développées — exactement le cas d'usage visé.
    """

    from services.ai.gemini_client import GEMINI_AUDIO_TIMEOUT_MS

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    delais_recus = []

    def _generate_multimodal(parts, temperature=0.4, timeout_ms=None):
        delais_recus.append(timeout_ms)
        return "transcription"

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    interview.transcribe_audio(b"donnees-audio")

    assert delais_recus == [GEMINI_AUDIO_TIMEOUT_MS]


def test_transcription_erreur_api(monkeypatch):
    from services.ai.gemini_client import GeminiRequestError

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    def _generate_multimodal(*a, **k):
        raise GeminiRequestError("quota dépassé")

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    texte, avertissement = interview.transcribe_audio(b"donnees-audio")

    assert texte == ""
    assert "quota dépassé" in avertissement


# ============================================================
# QUESTIONS DEJA POSEES
# ============================================================

def test_une_question_deja_posee_est_ecartee(session_factory, monkeypatch):
    """
    Le prompt demande à l'IA de ne pas se répéter, mais rien ne
    garantit qu'il soit suivi : le filtre déterministe est la vraie
    protection contre une question reposée à l'identique.
    """

    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                {"question": "Avez-vous géré un budget ?", "experience_id": None},
                {"question": "Parlez-vous anglais ?", "experience_id": None},
            ]
        ),
    )

    questions, _avertissement = interview.generate_interview_questions(
        CANDIDATE_ID,
        already_asked=["Avez-vous géré un budget ?"],
    )

    intitules = [q.question for q in questions]

    assert "Avez-vous géré un budget ?" not in intitules
    assert "Parlez-vous anglais ?" in intitules


def test_le_filtre_ignore_casse_accents_et_ponctuation(
    session_factory, monkeypatch
):
    """
    Une même question reformulée en changeant la casse ou la
    ponctuation reste la même question pour le candidat.
    """

    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [{"question": "AVEZ-VOUS GERE UN BUDGET ???", "experience_id": None}]
        ),
    )

    questions, avertissement = interview.generate_interview_questions(
        CANDIDATE_ID,
        already_asked=["Avez-vous géré un budget ?"],
    )

    assert questions == []
    assert avertissement


def test_les_questions_deja_posees_atteignent_le_prompt(
    session_factory, monkeypatch
):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    parts_recus = []

    def _generate_multimodal(parts, *a, **k):
        parts_recus.append(parts)
        return json.dumps([])

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    interview.generate_interview_questions(
        CANDIDATE_ID, already_asked=["Une question déjà posée ?"]
    )

    # .text plutôt que str() : la repr d'un Part Gemini tronque le contenu.
    assert "Une question déjà posée ?" in parts_recus[0][0].text

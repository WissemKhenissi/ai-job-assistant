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
# RELANCES SUR UNE EXPERIENCE
# ============================================================

NARRATION = (
    "J'ai piloté la refonte du tunnel d'achat pendant deux ans, avec "
    "une équipe de cinq développeurs."
)


def test_sans_cle_configuree_retourne_un_avertissement(
    session_factory, monkeypatch
):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: False)

    questions, avertissement = interview.generate_followup_questions(
        CANDIDATE_ID, EXPERIENCE_ID, NARRATION
    )

    assert questions == []
    assert "GEMINI_API_KEY" in avertissement


def test_sans_recit_aucune_relance(session_factory, monkeypatch):
    """
    Les relances se construisent sur le récit : sans récit, il n'y a
    rien à creuser.
    """

    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    questions, avertissement = interview.generate_followup_questions(
        CANDIDATE_ID, EXPERIENCE_ID, "   "
    )

    assert questions == []
    assert "Racontez" in avertissement


def test_une_experience_inconnue_est_signalee(session_factory, monkeypatch):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    questions, avertissement = interview.generate_followup_questions(
        CANDIDATE_ID, "experience-inexistante", NARRATION
    )

    assert questions == []
    assert "introuvable" in avertissement.lower()


def test_des_relances_valides_sont_extraites(session_factory, monkeypatch):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                "Quels outils utilisiez-vous pour le suivi ?",
                "Quels résultats chiffrés avez-vous obtenus ?",
            ]
        ),
    )

    questions, avertissement = interview.generate_followup_questions(
        CANDIDATE_ID, EXPERIENCE_ID, NARRATION
    )

    assert avertissement == ""
    assert len(questions) == 2

    # Toutes les relances sont rattachées à l'expérience traitée :
    # c'est ce rattachement qui permet ensuite un CV ciblé cohérent.
    assert all(q.experience_id == EXPERIENCE_ID for q in questions)
    assert all(
        q.experience_label == "Chef de projet — Groupe Meridiem" for q in questions
    )


def test_une_reponse_illisible_retourne_un_avertissement(
    session_factory, monkeypatch
):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview, "generate_multimodal", lambda *a, **k: "pas du JSON"
    )

    questions, avertissement = interview.generate_followup_questions(
        CANDIDATE_ID, EXPERIENCE_ID, NARRATION
    )

    assert questions == []
    assert avertissement


def test_le_recit_et_le_poste_atteignent_le_prompt(
    session_factory, monkeypatch
):
    _preparer_candidat_avec_experience(session_factory)

    monkeypatch.setattr(interview, "is_configured", lambda: True)

    parts_recus = []

    def _generate_multimodal(parts, *a, **k):
        parts_recus.append(parts)
        return json.dumps([])

    monkeypatch.setattr(interview, "generate_multimodal", _generate_multimodal)

    interview.generate_followup_questions(
        CANDIDATE_ID,
        EXPERIENCE_ID,
        NARRATION,
        target_role="Product Owner",
    )

    prompt = parts_recus[0][0].text

    assert "Product Owner" in prompt
    assert "tunnel d'achat" in prompt
    # La fiche de l'expérience traitée doit être présente.
    assert "Groupe Meridiem" in prompt


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
            ["Quels outils utilisiez-vous ?", "Combien étiez-vous ?"]
        ),
    )

    questions, _avertissement = interview.generate_followup_questions(
        CANDIDATE_ID,
        EXPERIENCE_ID,
        NARRATION,
        already_asked=["Quels outils utilisiez-vous ?"],
    )

    intitules = [q.question for q in questions]

    assert "Quels outils utilisiez-vous ?" not in intitules
    assert "Combien étiez-vous ?" in intitules


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
        lambda *a, **k: json.dumps(["QUELS OUTILS UTILISIEZ-VOUS ???"]),
    )

    questions, avertissement = interview.generate_followup_questions(
        CANDIDATE_ID,
        EXPERIENCE_ID,
        NARRATION,
        already_asked=["Quels outils utilisiez-vous ?"],
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

    interview.generate_followup_questions(
        CANDIDATE_ID,
        EXPERIENCE_ID,
        NARRATION,
        already_asked=["Une question déjà posée ?"],
    )

    # .text plutôt que str() : la repr d'un Part Gemini tronque le contenu.
    assert "Une question déjà posée ?" in parts_recus[0][0].text


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
# QUESTIONS SUR UNE COMPETENCE DECLAREE
# ============================================================
#
# Une compétence déclarée sans preuve reste « declared » : l'entretien
# doit amener le candidat à raconter UNE occasion précise où il l'a
# exercée. Une preuve est un fait situé, pas une affirmation répétée.


def test_les_questions_portent_sur_la_competence(
    session_factory, monkeypatch
):
    import services.ai.interview as interview

    session = session_factory()
    add_candidate(session)
    session.close()

    prompts = []

    def _faux_appel(parts, **kwargs):
        prompts.append(parts[0])
        return json.dumps(
            [
                "Sur quel projet avez-vous fait cette veille ?",
                "Comment restituiez-vous vos observations ?",
            ]
        )

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(interview, "generate_multimodal", _faux_appel)

    questions, avertissement = interview.generate_skill_questions(
        candidate_id=CANDIDATE_ID,
        skill_name="Veille concurrentielle",
    )

    assert avertissement == ""
    assert len(questions) == 2

    # La compétence voyage jusqu'aux propositions : c'est elle que la
    # preuve devra documenter.
    assert questions[0].experience_label == "Veille concurrentielle"
    assert questions[0].experience_id is None

    assert "Veille concurrentielle" in prompts[0]


def test_une_question_deja_posee_est_ecartee(
    session_factory, monkeypatch
):
    """
    La consigne ne suffit pas : le modèle reformule volontiers une
    question déjà posée. Le filtre est déterministe, comme pour les
    relances d'expérience.
    """

    import services.ai.interview as interview

    session = session_factory()
    add_candidate(session)
    session.close()

    monkeypatch.setattr(interview, "is_configured", lambda: True)
    monkeypatch.setattr(
        interview,
        "generate_multimodal",
        lambda *a, **k: json.dumps(
            [
                "Sur quel projet avez-vous fait cette veille ?",
                "Quel outil utilisiez-vous ?",
            ]
        ),
    )

    questions, _ = interview.generate_skill_questions(
        candidate_id=CANDIDATE_ID,
        skill_name="Veille concurrentielle",
        already_asked=["sur quel projet avez vous fait cette veille"],
    )

    assert [q.question for q in questions] == [
        "Quel outil utilisiez-vous ?"
    ]


def test_sans_cle_configuree_aucune_question(session_factory, monkeypatch):
    import services.ai.interview as interview

    monkeypatch.setattr(interview, "is_configured", lambda: False)

    questions, avertissement = interview.generate_skill_questions(
        candidate_id=CANDIDATE_ID, skill_name="Veille concurrentielle"
    )

    assert questions == []
    assert "GEMINI_API_KEY" in avertissement


def test_sans_competence_aucune_question(session_factory):
    import services.ai.interview as interview

    questions, avertissement = interview.generate_skill_questions(
        candidate_id=CANDIDATE_ID, skill_name="   "
    )

    assert questions == []
    assert avertissement


# ============================================================
# UNE PREUVE EST UN FAIT SITUE
# ============================================================


def test_une_declaration_reformulee_n_est_pas_un_fait_situe():
    """
    Mesuré en conditions réelles : à la réponse « oui je fais de la
    veille, c'est important dans mon métier », le modèle a proposé
    « Réalisation régulière de veille concurrentielle ». Rien n'est
    inventé — mais valider cette ligne ferait de la déclaration sa
    propre preuve.
    """

    assert not interview.evidence_is_situated(
        "Réalisation régulière de veille concurrentielle et "
        "information sur les pratiques du marché"
    )

    assert not interview.evidence_is_situated("")
    assert not interview.evidence_is_situated("   ")


def test_un_chiffre_un_rythme_ou_un_nom_propre_situent():

    assert interview.evidence_is_situated(
        "Pilotage d'un budget de 100 k€"
    )

    assert interview.evidence_is_situated(
        "Suivi de cinq plateformes concurrentes"
    )

    assert interview.evidence_is_situated(
        "Présentation d'une synthèse mensuelle au comité produit"
    )

    assert interview.evidence_is_situated(
        "Animation des cérémonies agiles chez Ticketis"
    )


def test_une_majuscule_de_debut_de_phrase_ne_situe_pas(
):
    """
    Sans cette précaution, la majuscule initiale de n'importe quelle
    ligne suffirait à la faire passer pour un fait situé, et le
    contrôle ne servirait à rien.
    """

    assert not interview.evidence_is_situated(
        "Veille sur le marché. Analyse des pratiques."
    )


def test_le_controle_juge_la_reponse_autant_que_la_ligne():
    """
    Étendu ligne à ligne au parcours par expérience, le contrôle
    décochait quatre propositions sur cinq d'un récit ordinaire —
    « rédaction de spécifications fonctionnelles », « animation des
    points de suivi » : des faits réels, sans chiffre.

    Le récit qui les porte, lui, est situé. C'est donc lui qui situe
    ses lignes.
    """

    recit = (
        "Je coordonnais les équipes techniques et métier au "
        "quotidien. Je rédigeais les spécifications fonctionnelles "
        "et j'animais les points de suivi."
    )

    assert interview.evidence_is_situated(recit)

    # Les lignes qui en sortent, prises isolément, n'en portent pas
    # la trace — et n'ont pas à en porter une.
    assert not interview.evidence_is_situated(
        "Rédaction de spécifications fonctionnelles"
    )

    vague = (
        "Oui je fais de la veille, c'est important dans mon métier, "
        "je regarde ce que font les autres et je m'informe."
    )

    assert not interview.evidence_is_situated(vague)

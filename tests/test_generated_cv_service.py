"""
Trace des CV générés (services.generated_cv_service).

Ce que ces tests verrouillent : la trace conserve les *décisions*
(identifiants retenus, compétences écartées avec leur motif), pas une
copie du contenu — sinon le Master CV cesserait d'être la source
unique et deux vérités coexisteraient.
"""

from __future__ import annotations

from datetime import date

from conftest import add_candidate
from services.cv.results import CVEvidenceLine, CVExperience, TargetedCV
from services.generated_cv_service import (
    get_generated_cvs,
    record_generated_cv,
)


CANDIDATE_ID = "candidate-test"
JOB_OFFER_ID = "job-test"


def _cv():
    return TargetedCV(
        candidate_id=CANDIDATE_ID,
        full_name="Test Candidat",
        email="",
        phone="",
        location="",
        linkedin_url="",
        summary="",
        job_offer_id=JOB_OFFER_ID,
        job_offer_title="Product Owner",
        skills=["Product Discovery"],
        experiences=[
            CVExperience(
                experience_id="experience-test",
                job_title="Chef de projet",
                company="Groupe Meridiem",
                location="",
                start_date=date(2018, 1, 1),
                end_date=date(2024, 12, 31),
                business_context="",
                lines=[
                    CVEvidenceLine(
                        text="Conception de produits digitaux.",
                        skill="Product Discovery",
                        evidence_id="evidence-1",
                    )
                ],
            )
        ],
        declared_skills=["Roadmap produit"],
        inferred_skills=["Agile / Scrum"],
        missing_skills=["Kubernetes"],
    )


def test_la_trace_conserve_les_identifiants_retenus(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    record_generated_cv(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv=_cv(),
        match_score=68.0,
    )

    traces = get_generated_cvs(CANDIDATE_ID)

    assert len(traces) == 1

    trace = traces[0]

    assert trace["selected_experience_ids"] == ["experience-test"]
    assert trace["selected_evidence_ids"] == ["evidence-1"]
    assert trace["selected_skills"] == ["Product Discovery"]
    assert trace["match_score_at_generation"] == 68.0


def test_les_competences_ecartees_gardent_leur_motif(session_factory):
    """
    Savoir qu'une compétence a été écartée ne suffit pas : il faut
    savoir si c'était faute de preuve, parce qu'elle était seulement
    déduite, ou parce qu'elle est absente du parcours.
    """

    session = session_factory()
    add_candidate(session)
    session.close()

    record_generated_cv(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv=_cv(),
    )

    exclues = get_generated_cvs(CANDIDATE_ID)[0]["excluded_skills"]

    motifs = {item["skill"]: item["motif"] for item in exclues}

    assert motifs["Roadmap produit"] == "declaree_sans_preuve"
    assert motifs["Agile / Scrum"] == "seulement_deduite"
    assert motifs["Kubernetes"] == "absente_du_master_cv"


def test_le_mode_et_le_modele_sont_conserves(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    record_generated_cv(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv=_cv(),
        mode="ia",
        llm_model="gemini-flash-lite-latest",
    )

    trace = get_generated_cvs(CANDIDATE_ID)[0]

    assert trace["mode"] == "ia"
    assert trace["llm_model"] == "gemini-flash-lite-latest"


def test_le_resultat_de_validation_est_conserve(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    record_generated_cv(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        cv=_cv(),
        validation_status="avertissements",
        validation_issues=[
            {
                "code": "chiffre_invente",
                "message": "Chiffre absent de la preuve.",
                "severity": "bloquant",
            }
        ],
    )

    trace = get_generated_cvs(CANDIDATE_ID)[0]

    assert trace["validation_status"] == "avertissements"
    assert trace["validation_issues"][0]["code"] == "chiffre_invente"


def test_l_historique_peut_etre_filtre_par_offre(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    record_generated_cv(CANDIDATE_ID, JOB_OFFER_ID, _cv())
    record_generated_cv(CANDIDATE_ID, "autre-offre", _cv())

    assert len(get_generated_cvs(CANDIDATE_ID)) == 2
    assert len(get_generated_cvs(CANDIDATE_ID, JOB_OFFER_ID)) == 1


def test_l_historique_est_cloisonne_par_candidat(session_factory):
    session = session_factory()
    add_candidate(session)
    add_candidate(session, candidate_id="candidate-autre")
    session.close()

    record_generated_cv(CANDIDATE_ID, JOB_OFFER_ID, _cv())

    assert get_generated_cvs("candidate-autre") == []

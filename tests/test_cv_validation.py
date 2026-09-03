"""
Contrôle déterministe d'un CV ciblé (services.cv.validation).

Ces tests sont le filet de sécurité du filet de sécurité : ils
vérifient que le validateur repère bien ce qu'il est censé repérer.
Chaque cas correspond à une façon dont un CV pourrait mentir — chiffre
apparu à la reformulation, compétence non prouvée affichée, date
divergente du Master CV, ligne sans preuve.
"""

from __future__ import annotations

from datetime import date

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)
from services.cv.results import CVEvidenceLine, CVExperience, TargetedCV
from services.cv.validation import validate_targeted_cv


CANDIDATE_ID = "candidate-test"
JOB_OFFER_ID = "job-test"
EXPERIENCE_ID = "experience-test"

DEBUT = date(2018, 1, 1)
FIN = date(2024, 12, 31)


def _preparer(session, competence="Product Discovery", avec_preuve=True):
    """Un candidat, une expérience, une compétence, une preuve, une offre analysée."""

    from database.models import EvidenceDB, ExperienceDB
    from models.job import JobOfferDB

    add_candidate(session)

    session.add(
        ExperienceDB(
            id=EXPERIENCE_ID,
            candidate_id=CANDIDATE_ID,
            company="Groupe Meridiem",
            job_title="Chef de projet",
            start_date=DEBUT,
            end_date=FIN,
            description="",
            business_context="",
            team_context="",
        )
    )

    add_catalog_skill(session, canonical_name=competence, aliases=[competence])

    skill = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name=competence
    )

    if avec_preuve:
        add_evidence(
            session,
            candidate_id=CANDIDATE_ID,
            skill_id=skill.id,
            description="Marge publicitaire passée de 1,4 M€ à 2,5 M€.",
        )

    session.add(
        JobOfferDB(
            id=JOB_OFFER_ID,
            title="Product Owner",
            company="Cdiscount",
            description=f"Nous cherchons du {competence}.",
            status="selected",
        )
    )

    session.commit()

    for evidence in session.query(EvidenceDB).all():
        evidence.experience_id = EXPERIENCE_ID

    session.commit()


def _analyser(competences):
    from services.matching import analyze_and_save_job_match

    return analyze_and_save_job_match(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        required_skills=competences,
    )


def _cv(lignes=None, skills=None, summary="", debut=DEBUT, fin=FIN):
    """Construit un TargetedCV minimal, modifiable cas par cas."""

    return TargetedCV(
        candidate_id=CANDIDATE_ID,
        full_name="Test Candidat",
        email="",
        phone="",
        location="",
        linkedin_url="",
        summary=summary,
        job_offer_id=JOB_OFFER_ID,
        job_offer_title="Product Owner",
        skills=skills if skills is not None else ["Product Discovery"],
        experiences=[
            CVExperience(
                experience_id=EXPERIENCE_ID,
                job_title="Chef de projet",
                company="Groupe Meridiem",
                location="",
                start_date=debut,
                end_date=fin,
                business_context="",
                lines=lignes if lignes is not None else [],
            )
        ],
    )


def _premiere_preuve(session_factory):
    from database.models import EvidenceDB

    session = session_factory()
    preuve = session.query(EvidenceDB).first()
    identifiant, texte = preuve.id, preuve.description
    session.close()

    return identifiant, texte


# ============================================================
# CAS CONFORME
# ============================================================

def test_un_cv_fidele_ne_declenche_aucun_signalement(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    identifiant, texte = _premiere_preuve(session_factory)

    rapport = validate_targeted_cv(
        _cv(
            lignes=[
                CVEvidenceLine(
                    text=texte,
                    skill="Product Discovery",
                    evidence_id=identifiant,
                )
            ]
        ),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert rapport.issues == []
    assert rapport.is_valid
    assert rapport.status == "ok"


def test_une_reformulation_sans_chiffre_nouveau_reste_valide(session_factory):
    """
    Reformuler est autorisé : seul l'ajout d'un chiffre absent de la
    preuve d'origine est fautif.
    """

    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    identifiant, _texte = _premiere_preuve(session_factory)

    rapport = validate_targeted_cv(
        _cv(
            lignes=[
                CVEvidenceLine(
                    text="Marge portée de 1,4 M€ à 2,5 M€ sur la période.",
                    skill="Product Discovery",
                    evidence_id=identifiant,
                )
            ]
        ),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert rapport.is_valid


# ============================================================
# CHIFFRES INVENTES
# ============================================================

def test_un_chiffre_invente_dans_une_ligne_est_signale(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    identifiant, _texte = _premiere_preuve(session_factory)

    rapport = validate_targeted_cv(
        _cv(
            lignes=[
                CVEvidenceLine(
                    text="Marge publicitaire en hausse de 79 %.",
                    skill="Product Discovery",
                    evidence_id=identifiant,
                )
            ]
        ),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert not rapport.is_valid
    assert any(i.code == "chiffre_invente" for i in rapport.issues)


def test_un_chiffre_invente_dans_le_resume_est_signale(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv(summary="Profil produit avec 12 ans d'expérience."),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert any(
        i.code == "chiffre_invente_resume" for i in rapport.issues
    )


# ============================================================
# PREUVES
# ============================================================

def test_une_ligne_sans_preuve_est_signalee(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv(
            lignes=[
                CVEvidenceLine(
                    text="Une ligne apparue de nulle part.",
                    skill="Product Discovery",
                    evidence_id="evidence-inexistante",
                )
            ]
        ),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert not rapport.is_valid
    assert any(i.code == "preuve_introuvable" for i in rapport.issues)


def test_une_ligne_repetee_est_signalee_sans_bloquer(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    identifiant, texte = _premiere_preuve(session_factory)

    ligne = CVEvidenceLine(
        text=texte, skill="Product Discovery", evidence_id=identifiant
    )

    rapport = validate_targeted_cv(
        _cv(lignes=[ligne, ligne]), CANDIDATE_ID, JOB_OFFER_ID
    )

    assert any(i.code == "ligne_en_double" for i in rapport.issues)
    # Une répétition abîme la lisibilité, elle ne rend pas le CV faux.
    assert rapport.is_valid


# ============================================================
# REALISATIONS
# ============================================================

def _ajouter_realisation(
    session,
    result: str = "Marge passée d'environ 1,4 M€ à environ 2,5 M€.",
    metrics: str = "≈ +79 % sur 7 ans",
):
    from database.models import AchievementDB

    session.add(
        AchievementDB(
            id="achievement-test",
            experience_id=EXPERIENCE_ID,
            title="Structuration de l'offre publicitaire",
            situation="",
            action="",
            result=result,
            metrics=metrics,
        )
    )
    session.commit()


def _cv_avec_realisation(titre="Structuration de l'offre publicitaire", detail=""):
    from services.cv.results import CVAchievementLine

    cv = _cv()

    cv.experiences[0].achievement_lines = [
        CVAchievementLine(
            title=titre,
            detail=detail,
            achievement_id="achievement-test",
        )
    ]

    return cv


def test_une_realisation_fidele_ne_declenche_rien(session_factory):
    session = session_factory()
    _preparer(session)
    _ajouter_realisation(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv_avec_realisation(
            detail="marge passée de 1,4 M€ à 2,5 M€ (≈ +79 % sur 7 ans)"
        ),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert rapport.is_valid


def test_un_chiffre_invente_dans_une_realisation_est_signale(
    session_factory,
):
    """
    C'est là que l'exactitude compte le plus : les réalisations
    portent tous les chiffres du parcours.
    """

    session = session_factory()
    _preparer(session)
    _ajouter_realisation(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv_avec_realisation(detail="marge triplée en 3 ans"),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert not rapport.is_valid
    assert any(
        i.code == "chiffre_invente_realisation" for i in rapport.issues
    )


def test_une_realisation_sans_source_est_signalee(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv_avec_realisation(),
        CANDIDATE_ID,
        JOB_OFFER_ID,
    )

    assert not rapport.is_valid
    assert any(
        i.code == "realisation_introuvable" for i in rapport.issues
    )


# ============================================================
# COMPETENCES
# ============================================================

def test_une_competence_non_prouvee_affichee_est_signalee(session_factory):
    """
    Le garde-fou central : une compétence déclarée sans preuve ne doit
    jamais figurer au CV comme acquise.
    """

    session = session_factory()
    _preparer(session, avec_preuve=False)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv(skills=["Product Discovery"]), CANDIDATE_ID, JOB_OFFER_ID
    )

    assert not rapport.is_valid
    assert any(i.code == "competence_non_prouvee" for i in rapport.issues)


def test_une_competence_absente_de_l_analyse_est_signalee(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv(skills=["Kubernetes"]), CANDIDATE_ID, JOB_OFFER_ID
    )

    assert not rapport.is_valid
    assert any(
        i.code == "competence_hors_analyse" for i in rapport.issues
    )


def test_sans_analyse_le_controle_le_signale(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    rapport = validate_targeted_cv(
        _cv(skills=[]), CANDIDATE_ID, JOB_OFFER_ID
    )

    assert any(i.code == "analyse_absente" for i in rapport.issues)


# ============================================================
# DATES
# ============================================================

def test_des_dates_divergentes_du_master_cv_sont_signalees(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    rapport = validate_targeted_cv(
        _cv(debut=date(2010, 1, 1)), CANDIDATE_ID, JOB_OFFER_ID
    )

    assert not rapport.is_valid
    assert any(i.code == "dates_divergentes" for i in rapport.issues)


def test_une_experience_absente_du_master_cv_est_signalee(session_factory):
    session = session_factory()
    _preparer(session)
    session.close()

    _analyser(["Product Discovery"])

    cv = _cv()
    cv.experiences[0].experience_id = "experience-inexistante"

    rapport = validate_targeted_cv(cv, CANDIDATE_ID, JOB_OFFER_ID)

    assert not rapport.is_valid
    assert any(
        i.code == "experience_introuvable" for i in rapport.issues
    )

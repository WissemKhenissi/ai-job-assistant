"""
Écriture d'un profil importé (services.profile_import_service).

Ce que ces tests verrouillent : un import **ajoute**, il n'écrase
jamais ce qui a été saisi à la main, et il ne double pas un parcours
si le même CV est déposé deux fois.

Le point le plus important est le dernier : une puce importée devient
une **preuve**. Sans cela les compétences resteraient « déclarées » et
ne pourraient jamais figurer sur un CV généré — l'import n'aurait
presque rien apporté.
"""

from __future__ import annotations

from datetime import date

from conftest import add_candidate
from services.ai.profile_extraction import (
    ExtractedCertification,
    ExtractedEducation,
    ExtractedExperience,
    ExtractedLine,
    ExtractedProfile,
)
from services.profile_import_service import import_profile


CANDIDATE_ID = "candidate-test"


def _profil(**surcharges) -> ExtractedProfile:

    defauts = dict(
        first_name="Camille",
        last_name="Durand",
        email="camille.durand@example.com",
        summary="Infirmière en réanimation.",
        skills=("Réanimation", "Encadrement"),
        experiences=(
            ExtractedExperience(
                company="CHU de Lyon",
                job_title="Infirmière",
                start_date=date(2019, 1, 1),
                end_date=date(2025, 1, 1),
                lines=(
                    ExtractedLine(
                        text="Prise en charge de patients critiques.",
                        skill="Réanimation",
                    ),
                    ExtractedLine(
                        text="Encadrement de 4 étudiants.",
                        skill="Encadrement",
                    ),
                ),
            ),
        ),
        educations=(
            ExtractedEducation(
                institution="IFSI de Lyon",
                degree="Diplôme d'État d'infirmier",
                end_year=2017,
            ),
        ),
        certifications=(
            ExtractedCertification(name="AFGSU 2", obtained_year=2021),
        ),
    )

    defauts.update(surcharges)

    return ExtractedProfile(**defauts)


# ============================================================
# CE QUI EST ECRIT
# ============================================================

def test_un_profil_complet_est_importe(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    resume = import_profile(CANDIDATE_ID, _profil())

    assert resume.experiences == 1
    assert resume.lines == 2
    assert resume.skills == 2
    assert resume.educations == 1
    assert resume.certifications == 1


def test_les_puces_deviennent_des_preuves(session_factory):
    """
    C'est ce qui fait la valeur de l'import : sans preuve, une
    compétence reste « déclarée » et ne peut pas figurer sur un CV.
    """

    from database.models import EvidenceDB

    session = session_factory()
    add_candidate(session)
    session.close()

    import_profile(CANDIDATE_ID, _profil())

    session = session_factory()
    preuves = session.query(EvidenceDB).all()

    assert len(preuves) == 2
    assert all(preuve.experience_id for preuve in preuves)
    assert all(preuve.skill_id for preuve in preuves)

    session.close()


def test_l_identite_vide_est_completee(session_factory):
    from database.models import CandidateDB

    session = session_factory()
    add_candidate(session)
    session.close()

    resume = import_profile(CANDIDATE_ID, _profil())

    session = session_factory()
    candidat = session.get(CandidateDB, CANDIDATE_ID)

    assert candidat.summary == "Infirmière en réanimation."
    assert "summary" in resume.fields_filled

    session.close()


# ============================================================
# CE QUI N'EST JAMAIS ECRASE
# ============================================================

def test_un_champ_deja_rempli_est_conserve(session_factory):
    """
    Un import ne doit jamais faire perdre ce qui a été saisi à la
    main.
    """

    from database.models import CandidateDB

    session = session_factory()
    add_candidate(session)
    candidat = session.get(CandidateDB, CANDIDATE_ID)
    candidat.summary = "Mon résumé, écrit par moi."
    session.commit()
    session.close()

    import_profile(CANDIDATE_ID, _profil())

    session = session_factory()

    assert (
        session.get(CandidateDB, CANDIDATE_ID).summary
        == "Mon résumé, écrit par moi."
    )

    session.close()


def test_l_ecrasement_reste_possible_sur_demande(session_factory):
    from database.models import CandidateDB

    session = session_factory()
    add_candidate(session)
    candidat = session.get(CandidateDB, CANDIDATE_ID)
    candidat.summary = "Ancien résumé."
    session.commit()
    session.close()

    import_profile(
        CANDIDATE_ID, _profil(), overwrite_identity=True
    )

    session = session_factory()

    assert (
        session.get(CandidateDB, CANDIDATE_ID).summary
        == "Infirmière en réanimation."
    )

    session.close()


def test_reimporter_le_meme_cv_ne_double_pas_le_parcours(
    session_factory,
):
    session = session_factory()
    add_candidate(session)
    session.close()

    import_profile(CANDIDATE_ID, _profil())
    second = import_profile(CANDIDATE_ID, _profil())

    assert second.experiences == 0
    assert second.skills == 0
    assert any("déjà présente" in item for item in second.skipped)


# ============================================================
# CE QUI EST IGNORE, ET DIT
# ============================================================

def test_une_experience_sans_date_est_ignoree_et_signalee(
    session_factory,
):
    """
    Une date manquante casserait le calcul d'ancienneté et le tri du
    parcours : mieux vaut la refuser en le disant.
    """

    session = session_factory()
    add_candidate(session)
    session.close()

    resume = import_profile(
        CANDIDATE_ID,
        _profil(
            experiences=(
                ExtractedExperience(
                    company="CHU de Lyon",
                    job_title="Infirmière",
                    start_date=None,
                ),
            )
        ),
    )

    assert resume.experiences == 0
    assert any("sans date de début" in item for item in resume.skipped)


def test_une_puce_sans_competence_est_ignoree_et_signalee(
    session_factory,
):
    session = session_factory()
    add_candidate(session)
    session.close()

    resume = import_profile(
        CANDIDATE_ID,
        _profil(
            skills=(),
            experiences=(
                ExtractedExperience(
                    company="CHU de Lyon",
                    job_title="Infirmière",
                    start_date=date(2019, 1, 1),
                    lines=(
                        ExtractedLine(text="Une puce orpheline."),
                    ),
                ),
            ),
        ),
    )

    assert resume.lines == 0
    assert any(
        "sans compétence associée" in item for item in resume.skipped
    )


def test_un_profil_vide_n_ecrit_rien(session_factory):
    session = session_factory()
    add_candidate(session)
    session.close()

    resume = import_profile(CANDIDATE_ID, ExtractedProfile())

    assert resume.total == 0

"""
Génération du CV ciblé.

Ces tests portent sur le principe non négociable du projet : rien
n'est inventé, et seules les compétences réellement prouvées peuvent
figurer comme compétences du CV.
"""

from __future__ import annotations

import pytest

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)


CANDIDATE_ID = "candidate-test"
JOB_OFFER_ID = "job-test"
EXPERIENCE_ID = "experience-test"


def _add_experience(session):
    from datetime import date

    from database.models import ExperienceDB

    session.add(
        ExperienceDB(
            id=EXPERIENCE_ID,
            candidate_id=CANDIDATE_ID,
            company="Groupe Meridiem",
            job_title="Chef de projet",
            start_date=date(2018, 1, 1),
            end_date=date(2024, 12, 31),
            description="",
            business_context="Contexte e-commerce.",
            team_context="",
        )
    )
    session.commit()


def _add_job_offer(session, description: str):
    from models.job import JobOfferDB

    session.add(
        JobOfferDB(
            id=JOB_OFFER_ID,
            title="Product Owner",
            description=description,
            status="selected",
        )
    )
    session.commit()


def _prepare_profile(
    session,
    competence: str = "Gestion de projet",
    avec_preuve: bool = True,
    preuves: list[str] | None = None,
):
    add_candidate(session)
    _add_experience(session)

    add_catalog_skill(
        session,
        canonical_name=competence,
        aliases=[competence],
    )

    skill = add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name=competence,
    )

    if avec_preuve:
        for index, texte in enumerate(
            preuves or ["Pilotage de projets de bout en bout."]
        ):
            add_evidence(
                session,
                candidate_id=CANDIDATE_ID,
                skill_id=skill.id,
                description=texte,
                evidence_id=f"evidence-{index}",
            )

    return skill


def _lier_preuves_a_l_experience(session):
    """Rattache les preuves à l'expérience (le helper ne le fait pas)."""

    from database.models import EvidenceDB

    for evidence in session.query(EvidenceDB).all():
        evidence.experience_id = EXPERIENCE_ID

    session.commit()


def _analyser(required_skills: list[str]):
    from services.matching import analyze_and_save_job_match

    return analyze_and_save_job_match(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        required_skills=required_skills,
    )


# ============================================================
# GARANTIE CENTRALE : SEULES LES COMPETENCES PROUVEES
# ============================================================

def test_une_competence_prouvee_figure_au_cv(session_factory):
    from services.cv import build_targeted_cv

    session = session_factory()
    _prepare_profile(session)
    _add_job_offer(session, "Nous cherchons de la gestion de projet.")
    _lier_preuves_a_l_experience(session)
    session.close()

    _analyser(["Gestion de projet"])

    cv = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

    assert cv.skills == ["Gestion de projet"]
    assert cv.total_lines == 1


def test_une_competence_declaree_sans_preuve_ne_figure_pas_au_cv(
    session_factory,
):
    """
    Le cœur du principe : une compétence que le candidat ne peut pas
    prouver ne doit pas apparaître comme compétence du CV.
    """

    from services.cv import build_targeted_cv

    session = session_factory()
    _prepare_profile(session, avec_preuve=False)
    _add_job_offer(session, "Nous cherchons de la gestion de projet.")
    session.close()

    _analyser(["Gestion de projet"])

    cv = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

    assert cv.skills == []
    assert cv.declared_skills == ["Gestion de projet"]
    assert cv.total_lines == 0


def test_une_competence_manquante_ne_figure_pas_au_cv(
    session_factory,
):
    from services.cv import build_targeted_cv

    session = session_factory()
    _prepare_profile(session)

    add_catalog_skill(
        session,
        canonical_name="Python",
        aliases=["Python"],
        skill_id="catalog-python",
    )

    _add_job_offer(session, "Gestion de projet et Python.")
    _lier_preuves_a_l_experience(session)
    session.close()

    _analyser(["Gestion de projet", "Python"])

    cv = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

    assert "Python" not in cv.skills
    assert "Python" in cv.missing_skills


# ============================================================
# TRACABILITE
# ============================================================

def test_chaque_ligne_du_cv_remonte_a_une_preuve_du_master_cv(
    session_factory,
):
    from database.models import EvidenceDB
    from services.cv import build_targeted_cv

    session = session_factory()
    _prepare_profile(
        session,
        preuves=[
            "Pilotage de projets de bout en bout.",
            "Coordination d'équipes IT et métiers.",
        ],
    )
    _add_job_offer(session, "Gestion de projet.")
    _lier_preuves_a_l_experience(session)
    session.close()

    _analyser(["Gestion de projet"])

    cv = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

    session = session_factory()

    for experience in cv.experiences:
        for line in experience.lines:

            evidence = session.get(EvidenceDB, line.evidence_id)

            assert evidence is not None, (
                f"la ligne {line.text!r} ne remonte à aucune preuve"
            )

            assert evidence.description.strip() == line.text

    session.close()


def test_le_cv_ne_repete_jamais_la_meme_ligne(session_factory):
    """
    Un même énoncé du Master CV est rattaché à toutes les compétences
    qu'il démontre : il existe donc en plusieurs exemplaires en base.
    Le CV ne doit en retenir qu'un.
    """

    from services.cv import build_targeted_cv

    session = session_factory()

    add_candidate(session)
    _add_experience(session)

    for competence in ("Gestion de projet", "Coordination transverse"):

        add_catalog_skill(
            session,
            canonical_name=competence,
            aliases=[competence],
            skill_id=f"catalog-{competence[:10]}",
        )

        skill = add_candidate_skill(
            session,
            candidate_id=CANDIDATE_ID,
            name=competence,
        )

        # Le même texte, rattaché aux deux compétences.
        add_evidence(
            session,
            candidate_id=CANDIDATE_ID,
            skill_id=skill.id,
            description="Coordination d'équipes IT, UX et métiers.",
            evidence_id=f"evidence-{skill.id}",
        )

    _add_job_offer(
        session,
        "Gestion de projet et coordination transverse.",
    )
    _lier_preuves_a_l_experience(session)
    session.close()

    _analyser(["Gestion de projet", "Coordination transverse"])

    cv = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

    textes = [
        line.text
        for experience in cv.experiences
        for line in experience.lines
    ]

    assert len(textes) == len(set(textes)), (
        f"lignes répétées dans le CV : {textes}"
    )


# ============================================================
# DETERMINISME ET GARDE-FOUS
# ============================================================

def test_deux_generations_donnent_le_meme_cv(session_factory):
    from services.cv import build_targeted_cv

    session = session_factory()
    _prepare_profile(
        session,
        preuves=[
            "Pilotage de projets de bout en bout.",
            "Coordination d'équipes IT et métiers.",
            "Mise en place d'une logique MVP.",
        ],
    )
    _add_job_offer(session, "Gestion de projet.")
    _lier_preuves_a_l_experience(session)
    session.close()

    _analyser(["Gestion de projet"])

    premier = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)
    second = build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

    assert premier == second


def test_le_nombre_de_lignes_est_plafonne(session_factory):
    from services.cv import build_targeted_cv

    session = session_factory()
    _prepare_profile(
        session,
        preuves=[
            f"Réalisation numéro {index}." for index in range(10)
        ],
    )
    _add_job_offer(session, "Gestion de projet.")
    _lier_preuves_a_l_experience(session)
    session.close()

    _analyser(["Gestion de projet"])

    cv = build_targeted_cv(
        CANDIDATE_ID,
        JOB_OFFER_ID,
        max_lines_per_skill=2,
    )

    assert cv.total_lines == 2


def test_generer_un_cv_sans_analyse_prealable_echoue(
    session_factory,
):
    """
    Le CV reflète une analyse : sans analyse, il ne doit pas être
    fabriqué à partir de rien.
    """

    from services.cv import MissingAnalysisError, build_targeted_cv

    session = session_factory()
    _prepare_profile(session)
    _add_job_offer(session, "Gestion de projet.")
    session.close()

    with pytest.raises(MissingAnalysisError):
        build_targeted_cv(CANDIDATE_ID, JOB_OFFER_ID)

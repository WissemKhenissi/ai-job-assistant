"""
Historisation du détail du matching, compétence par compétence.

Avant l'introduction de job_skill_matches, seuls des noms et des
scores agrégés étaient conservés : le score individuel, l'explication
et les preuves étaient perdus dès la fin de l'analyse.
"""

from __future__ import annotations

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)


CANDIDATE_ID = "candidate-test"
JOB_OFFER_ID = "job-test"


def _prepare(session, with_evidence: bool = True):
    """Un candidat, une compétence au catalogue, une annonce."""

    from models.job import JobOfferDB

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet", "Project Management"],
    )

    skill = add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Gestion de projet",
    )

    if with_evidence:
        add_evidence(
            session,
            candidate_id=CANDIDATE_ID,
            skill_id=skill.id,
            description="Refonte du tunnel d'achat.",
        )

    session.add(
        JobOfferDB(
            id=JOB_OFFER_ID,
            title="Chef de projet",
            description="Nous cherchons quelqu'un en gestion de projet.",
            status="selected",
        )
    )

    session.commit()


def test_le_detail_par_competence_est_historise(session_factory):
    from models.skill_match import JobSkillMatchDB
    from services.matching import analyze_and_save_job_match

    session = session_factory()
    _prepare(session)
    session.close()

    analyze_and_save_job_match(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        required_skills=["Project Management", "Python"],
    )

    session = session_factory()

    rows = (
        session.query(JobSkillMatchDB)
        .order_by(JobSkillMatchDB.skill)
        .all()
    )

    assert len(rows) == 2

    par_competence = {row.skill: row for row in rows}

    projet = par_competence["Project Management"]

    assert projet.status == "proven"
    assert projet.score == 1.0
    assert projet.explanation, "l'explication doit être conservée"
    assert projet.evidence, "les preuves doivent être conservées"

    # La forme canonique permet d'agréger malgré l'écriture de
    # l'annonce ("Project Management" est un alias).
    assert projet.canonical_skill == "gestion de projet"

    python = par_competence["Python"]

    assert python.status == "missing"
    assert python.score == 0.0
    assert python.evidence == []

    session.close()


def test_une_reanalyse_remplace_le_detail_sans_le_dupliquer(
    session_factory,
):
    from models.skill_match import JobSkillMatchDB
    from services.matching import analyze_and_save_job_match

    session = session_factory()
    _prepare(session)
    session.close()

    for _ in range(3):
        analyze_and_save_job_match(
            candidate_id=CANDIDATE_ID,
            job_offer_id=JOB_OFFER_ID,
            required_skills=["Gestion de projet"],
        )

    session = session_factory()

    rows = session.query(JobSkillMatchDB).all()

    assert len(rows) == 1, (
        "le détail doit décrire l'analyse courante, "
        "pas s'accumuler à chaque relance"
    )

    session.close()


def test_le_detail_est_rattache_au_matching_parent(session_factory):
    from models.matching import JobMatchDB
    from models.skill_match import JobSkillMatchDB
    from services.matching import analyze_and_save_job_match

    session = session_factory()
    _prepare(session)
    session.close()

    analyze_and_save_job_match(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        required_skills=["Gestion de projet"],
    )

    session = session_factory()

    parent = session.query(JobMatchDB).one()
    detail = session.query(JobSkillMatchDB).one()

    assert detail.job_match_id == parent.id

    session.close()


def test_le_statut_declared_est_historise(session_factory):
    """
    Une compétence déclarée sans preuve doit être traçable comme
    telle, et non confondue avec une compétence prouvée.
    """

    from models.skill_match import JobSkillMatchDB
    from services.matching import analyze_and_save_job_match

    session = session_factory()
    _prepare(session, with_evidence=False)
    session.close()

    analyze_and_save_job_match(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        required_skills=["Gestion de projet"],
    )

    session = session_factory()

    detail = session.query(JobSkillMatchDB).one()

    assert detail.status == "declared"
    assert detail.score < 1.0

    session.close()

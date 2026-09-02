"""
Mémoire de marché : agrégation des compétences demandées.

Points sensibles couverts ici :

- comportement à 0 annonce (pas de division par zéro) ;
- prudence des libellés de priorité tant que l'échantillon est
  trop petit (< 3 annonces) ;
- filtrage par statut d'annonce, qui est ce qui empêche les
  annonces de test / démo de polluer la mémoire.
"""

from __future__ import annotations

from conftest import add_candidate


CANDIDATE_ID = "candidate-test"


def _add_analyzed_job(
    session,
    job_id: str,
    matched_skills: list[str],
    inferred_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
    status: str = "selected",
):
    """Crée une annonce et son résultat de matching."""

    from models.job import JobOfferDB
    from models.matching import JobMatchDB

    session.add(
        JobOfferDB(
            id=job_id,
            title=f"Annonce {job_id}",
            status=status,
        )
    )

    session.add(
        JobMatchDB(
            id=f"match-{job_id}",
            candidate_id=CANDIDATE_ID,
            job_offer_id=job_id,
            score_global=50.0,
            score_skills=50.0,
            score_experience=50.0,
            score_domain=50.0,
            matched_skills=matched_skills,
            inferred_skills=inferred_skills or [],
            missing_skills=missing_skills or [],
            strengths=[],
            weaknesses=[],
        )
    )

    session.commit()


# ============================================================
# 0 ANNONCE
# ============================================================

def test_memoire_de_marche_sans_aucune_annonce(session_factory):
    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)
    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    assert result.analyzed_jobs_count == 0
    assert result.skills == []


# ============================================================
# 1, 2 PUIS 3 ANNONCES
# ============================================================

def test_une_seule_annonce_reste_un_signal_initial(session_factory):
    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)

    _add_analyzed_job(
        session,
        "job-1",
        matched_skills=[],
        missing_skills=["Python"],
    )

    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    assert result.analyzed_jobs_count == 1

    python = next(
        skill for skill in result.skills if skill.skill == "Python"
    )

    assert python.demand_count == 1
    assert python.missing_count == 1
    assert python.frequency_percent == 100.0
    assert python.priority == "Signal initial"


def test_deux_annonces_restent_un_signal_initial(session_factory):
    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)

    _add_analyzed_job(
        session,
        "job-1",
        matched_skills=[],
        missing_skills=["Python"],
    )

    _add_analyzed_job(
        session,
        "job-2",
        matched_skills=[],
        missing_skills=["Python"],
    )

    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    assert result.analyzed_jobs_count == 2

    python = next(
        skill for skill in result.skills if skill.skill == "Python"
    )

    assert python.demand_count == 2
    assert python.priority == "Signal initial"


def test_a_trois_annonces_la_priorite_devient_significative(
    session_factory,
):
    """
    Au-delà de 3 annonces, une compétence systématiquement manquante
    doit être remontée comme prioritaire, plus comme simple signal.
    """

    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)

    for index in range(1, 4):
        _add_analyzed_job(
            session,
            f"job-{index}",
            matched_skills=[],
            missing_skills=["Python"],
        )

    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    assert result.analyzed_jobs_count == 3

    python = next(
        skill for skill in result.skills if skill.skill == "Python"
    )

    assert python.demand_count == 3
    assert python.gap_rate_percent == 100.0
    assert python.priority == "Prioritaire"


# ============================================================
# STATUTS ET COUVERTURE
# ============================================================

def test_les_annonces_non_selectionnees_sont_ignorees(
    session_factory,
):
    """
    C'est ce filtre qui empêche une annonce de test ou de démo de
    fausser la mémoire de marché.
    """

    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)

    _add_analyzed_job(
        session,
        "job-reel",
        matched_skills=["Gestion de projet"],
        status="selected",
    )

    _add_analyzed_job(
        session,
        "job-brouillon",
        matched_skills=["Compétence parasite"],
        status="new",
    )

    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    assert result.analyzed_jobs_count == 1

    noms = {skill.skill for skill in result.skills}

    assert noms == {"Gestion de projet"}


def test_une_competence_toujours_prouvee_est_consideree_couverte(
    session_factory,
):
    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)

    for index in range(1, 4):
        _add_analyzed_job(
            session,
            f"job-{index}",
            matched_skills=["Gestion de projet"],
        )

    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    gestion = next(
        skill
        for skill in result.skills
        if skill.skill == "Gestion de projet"
    )

    assert gestion.proven_count == 3
    assert gestion.missing_count == 0
    assert gestion.priority == "Couvert"


def test_une_competence_seulement_deduite_est_a_documenter(
    session_factory,
):
    """
    Une compétence jamais manquante mais seulement déduite n'est pas
    "couverte" : elle reste une hypothèse à documenter.
    """

    from services.market_memory_service import get_market_skill_memory

    session = session_factory()
    add_candidate(session)

    for index in range(1, 4):
        _add_analyzed_job(
            session,
            f"job-{index}",
            matched_skills=[],
            inferred_skills=["Product Strategy"],
        )

    session.close()

    result = get_market_skill_memory(
        CANDIDATE_ID,
        included_job_statuses={"selected"},
    )

    strategy = next(
        skill
        for skill in result.skills
        if skill.skill == "Product Strategy"
    )

    assert strategy.inferred_count == 3
    assert strategy.missing_count == 0
    assert strategy.priority == "À documenter"

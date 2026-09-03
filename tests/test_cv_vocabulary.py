"""
Vocabulaire autorisé et interdit (services.cv.vocabulary).

Ce que ces tests verrouillent : la frontière entre « mot que le
candidat peut employer » et « mot qui affirmerait une compétence
qu'il n'a pas » est tracée par le code, à partir de l'analyse de
l'offre et du référentiel — jamais par le jugement du modèle.
"""

from __future__ import annotations

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)
from services.cv.vocabulary import (
    build_offer_vocabulary,
    forbidden_terms_used,
    mentions_term,
    seniority_terms_added,
)


CANDIDATE_ID = "candidate-test"
JOB_OFFER_ID = "job-test"


def _offre(session):
    from models.job import JobOfferDB

    session.add(
        JobOfferDB(
            id=JOB_OFFER_ID,
            title="Product Owner",
            company="Cdiscount",
            description="Product Discovery et Kubernetes.",
            status="selected",
        )
    )

    session.commit()


def _analyser(competences):
    from services.matching import analyze_and_save_job_match

    return analyze_and_save_job_match(
        candidate_id=CANDIDATE_ID,
        job_offer_id=JOB_OFFER_ID,
        required_skills=competences,
    )


# ============================================================
# CONSTRUCTION DU VOCABULAIRE
# ============================================================

def test_une_competence_prouvee_autorise_ses_alias(session_factory):
    """
    Le référentiel est ce qui permet d'employer le mot de l'annonce
    plutôt que celui du Master CV : sans lui, aucune adaptation de
    vocabulaire ne serait honnête.
    """

    session = session_factory()

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery", "Découverte produit"],
    )

    skill = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name="Product Discovery"
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description="Cadrage des besoins utilisateurs.",
    )

    _offre(session)
    session.close()

    _analyser(["Découverte produit"])

    vocabulaire = build_offer_vocabulary(CANDIDATE_ID, JOB_OFFER_ID)

    assert "Product Discovery" in vocabulaire.authorized
    assert "Découverte produit" in vocabulaire.authorized
    assert vocabulaire.forbidden == ()


def test_une_competence_declaree_sans_preuve_est_interdite(
    session_factory,
):
    """
    Déclarée n'est pas prouvée : le mot reste interdit au CV, comme
    la compétence elle-même.
    """

    session = session_factory()

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery"],
    )

    add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name="Product Discovery"
    )

    _offre(session)
    session.close()

    _analyser(["Product Discovery"])

    vocabulaire = build_offer_vocabulary(CANDIDATE_ID, JOB_OFFER_ID)

    assert "Product Discovery" in vocabulaire.forbidden
    assert vocabulaire.authorized == ()


def test_une_competence_absente_du_profil_est_interdite(session_factory):
    session = session_factory()

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Kubernetes",
        aliases=["Kubernetes", "K8s"],
    )

    _offre(session)
    session.close()

    _analyser(["Kubernetes"])

    vocabulaire = build_offer_vocabulary(CANDIDATE_ID, JOB_OFFER_ID)

    assert "Kubernetes" in vocabulaire.forbidden
    assert "K8s" in vocabulaire.forbidden


def test_le_libelle_du_candidat_est_autorise(session_factory):
    """
    Le candidat nomme parfois une compétence prouvée autrement que
    l'annonce et que le référentiel : ses propres mots restent
    utilisables.
    """

    session = session_factory()

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery", "Cadrage produit"],
    )

    skill = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name="Cadrage produit"
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description="Cadrage des besoins utilisateurs.",
    )

    _offre(session)
    session.close()

    _analyser(["Product Discovery"])

    vocabulaire = build_offer_vocabulary(CANDIDATE_ID, JOB_OFFER_ID)

    assert "Cadrage produit" in vocabulaire.authorized


def test_une_preuve_l_emporte_sur_un_libelle_non_prouve(session_factory):
    """
    Une annonce peut demander deux fois la même compétence sous deux
    libellés : c'est la preuve qui tranche, pas l'ordre des lignes.
    """

    session = session_factory()

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery", "Découverte produit"],
    )

    skill = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name="Product Discovery"
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description="Cadrage des besoins utilisateurs.",
    )

    add_catalog_skill(
        session,
        canonical_name="Kubernetes",
        aliases=["Kubernetes"],
    )

    _offre(session)
    session.close()

    _analyser(["Product Discovery", "Kubernetes"])

    vocabulaire = build_offer_vocabulary(CANDIDATE_ID, JOB_OFFER_ID)

    assert "Product Discovery" in vocabulaire.authorized
    assert "Product Discovery" not in vocabulaire.forbidden
    assert "Kubernetes" in vocabulaire.forbidden


def test_sans_analyse_le_vocabulaire_est_vide(session_factory):
    """
    Une offre non analysée ne doit pas faire échouer la rédaction :
    elle la laisse simplement sans ce cadrage-là.
    """

    session = session_factory()
    add_candidate(session)
    _offre(session)
    session.close()

    vocabulaire = build_offer_vocabulary(CANDIDATE_ID, JOB_OFFER_ID)

    assert vocabulaire.is_empty


# ============================================================
# DETECTION DANS UN TEXTE
# ============================================================

def test_un_terme_est_reconnu_malgre_la_casse_et_les_accents():
    assert mentions_term("Pilotage de la decouverte PRODUIT.", "Découverte produit")


def test_un_terme_n_est_pas_reconnu_dans_un_mot_plus_long():
    assert not mentions_term("Base embarquée SQLite.", "SQL")


def test_un_terme_deja_present_dans_la_source_n_est_pas_signale():
    signales = forbidden_terms_used(
        "Requêtes SQL optimisées.",
        ("SQL",),
        source_text="Écriture de requêtes SQL.",
    )

    assert signales == []


def test_un_terme_apparu_a_la_reformulation_est_signale():
    signales = forbidden_terms_used(
        "Requêtes SQL optimisées.",
        ("SQL",),
        source_text="Extraction de données.",
    )

    assert signales == ["SQL"]


# ============================================================
# SENIORITE (§26)
# ============================================================

def test_une_experience_devenue_expertise_est_signalee():
    signales = seniority_terms_added(
        "Expert en pilotage de projets digitaux.",
        "Une expérience de pilotage de projets digitaux.",
    )

    assert "expert" in signales


def test_un_niveau_deja_present_dans_la_source_n_est_pas_signale():
    signales = seniority_terms_added(
        "Responsable de l'équipe produit à Paris.",
        "Responsable d'une équipe produit.",
    )

    assert signales == []


def test_une_reformulation_sans_inflation_ne_signale_rien():
    signales = seniority_terms_added(
        "Pilotage de projets digitaux à fort volume.",
        "Pilotage de projets digitaux.",
    )

    assert signales == []

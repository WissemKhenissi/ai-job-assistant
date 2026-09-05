"""
Score de domaine (services.matching.analysis).

Le moteur cherchait trois mots dans le texte de l'annonce :
« e-commerce », « adtech », « digital ». Mesuré sur les treize
annonces du corpus de l'utilisateur, ce score valait 100 sur les
treize — toutes contiennent « digital », et son profil aussi. Il ne
mesurait plus rien et ajoutait dix points à tout le monde. Pour un
autre métier il n'aurait rien mesuré non plus, mais dans l'autre
sens.

Les domaines viennent du référentiel : la catégorie de chaque
exigence qu'il reconnaît.
"""

from __future__ import annotations

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)
from services.matching import analyze_candidate_against_skills


CANDIDATE_ID = "candidate-test"

ANNONCE = "Une annonce quelconque, dans un métier quelconque."


def _prouve(session, nom: str, categorie: str):
    """Une compétence du référentiel, prouvée par le candidat."""

    add_catalog_skill(
        session,
        canonical_name=nom,
        aliases=[nom],
        category=categorie,
    )

    skill = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name=nom
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description=f"Pratique quotidienne de {nom}.",
        evidence_id=f"evidence-{nom}",
    )


def test_couvrir_tous_les_domaines_vaut_cent(session_factory):

    session = session_factory()
    add_candidate(session)

    _prouve(session, "Pose de carrelage", "Second oeuvre")
    _prouve(session, "Lecture de plans", "Etudes")

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Pose de carrelage", "Lecture de plans"],
        job_text=ANNONCE,
    )

    assert resultat.score_domain == 100.0


def test_un_domaine_sur_deux_vaut_cinquante(session_factory):
    """
    Couvrir deux exigences d'un même domaine n'est pas couvrir deux
    domaines : c'est ce que ce score ajoute au décompte des
    compétences.
    """

    session = session_factory()
    add_candidate(session)

    _prouve(session, "Pose de carrelage", "Second oeuvre")
    _prouve(session, "Pose de faience", "Second oeuvre")

    add_catalog_skill(
        session,
        canonical_name="Chiffrage de travaux",
        aliases=["Chiffrage de travaux"],
        category="Etudes",
    )

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Pose de carrelage",
            "Pose de faience",
            "Chiffrage de travaux",
        ],
        job_text=ANNONCE,
    )

    assert resultat.score_domain == 50.0


def test_aucun_domaine_couvert_vaut_zero(session_factory):

    session = session_factory()
    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Soudure TIG",
        aliases=["Soudure TIG"],
        category="Metallerie",
    )

    # Le candidat existe, mais ne prouve rien de ce que l'annonce
    # demande.
    _prouve(session, "Pose de carrelage", "Second oeuvre")

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Soudure TIG"],
        job_text=ANNONCE,
    )

    assert resultat.score_domain == 0.0


def test_sans_exigence_reconnue_le_score_ne_s_invente_pas(
    session_factory,
):
    """
    Aucune exigence rattachée au référentiel : il n'y a pas de
    domaine à comparer. Le score reprend celui des compétences plutôt
    que d'inventer une valeur — c'est le comportement d'origine.
    """

    session = session_factory()
    add_candidate(session)
    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Un terme que le référentiel ignore"],
        job_text=ANNONCE,
    )

    assert resultat.score_domain == resultat.score_skills


def test_le_score_ne_depend_plus_du_vocabulaire_du_produit(
    session_factory,
):
    """
    Le garde-fou de la correction : deux annonces identiques, l'une
    truffée du mot « digital », l'autre non, doivent obtenir le même
    score de domaine. C'est précisément ce que l'ancienne version ne
    faisait pas.
    """

    session = session_factory()
    add_candidate(session)

    _prouve(session, "Pose de carrelage", "Second oeuvre")

    session.close()

    avec = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Pose de carrelage"],
        job_text="Un chantier digital, e-commerce et adtech.",
    )

    sans = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Pose de carrelage"],
        job_text="Un chantier de rénovation en second oeuvre.",
    )

    assert avec.score_domain == sans.score_domain

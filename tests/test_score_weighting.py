"""
Pondération des exigences dans le score (services.matching.analysis).

Le score moyennait toutes les exigences à égalité. Tant que le
référentiel n'en reconnaissait que quelques-unes par annonce, cela
passait inaperçu. Après l'import d'une taxonomie de 13 500 entrées,
une annonce énumérant « Jira, Miro, GitLab, Planner, MS Project »
voyait son score s'effondrer sur des détails d'outillage : le score
mesurait la longueur de l'énumération autant que l'adéquation.

Les exigences arrivent dans leur ordre d'apparition dans l'annonce.
Ce qu'elle cite en premier pèse davantage — heuristique assumée, qui
correspond à la façon dont une offre est rédigée.
"""

from __future__ import annotations

from conftest import (
    add_candidate,
    add_candidate_skill,
    add_catalog_skill,
    add_evidence,
)
from services.matching import analyze_candidate_against_skills
from services.matching.config import SKILL_WEIGHT_DECAY


CANDIDATE_ID = "candidate-test"


def _profil(session, competence: str = "Gestion de projet"):
    """Un candidat qui prouve une seule compétence."""

    add_candidate(session)

    add_catalog_skill(
        session, canonical_name=competence, aliases=[competence]
    )

    skill = add_candidate_skill(
        session, candidate_id=CANDIDATE_ID, name=competence
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description="Pilotage de projets digitaux de bout en bout.",
    )

    for absente in ("Kubernetes", "Terraform", "Ansible", "Puppet"):
        add_catalog_skill(
            session, canonical_name=absente, aliases=[absente]
        )


def test_une_exigence_citee_en_premier_pese_davantage(
    session_factory,
):
    """
    Le cœur de la correction : la même compétence prouvée doit valoir
    plus quand l'annonce la cite en tête que noyée en fin de liste.
    """

    session = session_factory()
    _profil(session)
    session.close()

    en_tete = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Gestion de projet",
            "Kubernetes",
            "Terraform",
            "Ansible",
            "Puppet",
        ],
    )

    en_fin = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Kubernetes",
            "Terraform",
            "Ansible",
            "Puppet",
            "Gestion de projet",
        ],
    )

    assert en_tete.score_skills > en_fin.score_skills


def test_une_exigence_unique_garde_son_score_plein(session_factory):
    """
    La pondération ne doit pas changer le cas simple : une seule
    exigence, prouvée, vaut toujours 100.
    """

    session = session_factory()
    _profil(session)
    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet"],
    )

    assert resultat.score_skills == 100.0


def test_des_exigences_toutes_prouvees_valent_toujours_cent(
    session_factory,
):
    """
    Pondérer ne doit pas abaisser un profil qui couvre tout : la
    somme des poids est au dénominateur.
    """

    session = session_factory()

    add_candidate(session)

    for nom in ("Gestion de projet", "SQL", "Python"):

        add_catalog_skill(session, canonical_name=nom, aliases=[nom])

        skill = add_candidate_skill(
            session, candidate_id=CANDIDATE_ID, name=nom
        )

        add_evidence(
            session,
            candidate_id=CANDIDATE_ID,
            skill_id=skill.id,
            description=f"Usage quotidien de {nom}.",
            evidence_id=f"evidence-{nom}",
        )

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet", "SQL", "Python"],
    )

    assert resultat.score_skills == 100.0


def test_une_longue_liste_d_outils_ne_domine_plus(session_factory):
    """
    Cas observé : une annonce citant la compétence cœur puis dix
    outils absents tombait sous 20 points. La compétence citée en
    premier doit continuer de porter le score.
    """

    session = session_factory()
    _profil(session)

    for indice in range(10):
        add_catalog_skill(
            session,
            canonical_name=f"Outil {indice}",
            aliases=[f"Outil {indice}"],
        )

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Gestion de projet",
            *[f"Outil {indice}" for indice in range(10)],
        ],
    )

    # Moyenne simple : 1 prouvée sur 11 exigences = 9,1 points.
    # Pondérée : la première pèse 1,00 et la onzième 0,33, pour une
    # somme de poids de 6,18 — soit 1,00 / 6,18 = 16,2 points.
    #
    # Le score reste bas, et c'est juste : le candidat ne couvre
    # qu'une exigence sur onze. Ce que la pondération corrige, c'est
    # que cette exigence-là était la première citée.
    assert resultat.score_skills > 14.0


def test_la_decroissance_reste_douce():
    """
    Une décroissance trop brutale ferait dépendre le score de la
    seule première exigence, et une annonce mal ordonnée deviendrait
    illisible.
    """

    assert SKILL_WEIGHT_DECAY >= 3.0

    poids_dernier = 1.0 / (1.0 + 19 / SKILL_WEIGHT_DECAY)

    # La vingtième exigence garde une voix, même faible.
    assert 0.1 < poids_dernier < 0.5


# ============================================================
# NIVEAU D'EXIGENCE
# ============================================================
#
# Le rang seul ne suffisait pas. À l'intérieur d'une énumération
# d'outils, l'ordre ne veut plus rien dire : le score continuait de
# s'effondrer sur des détails d'outillage que l'annonce ne pose pas
# comme conditions. Ce que l'annonce DIT du terme s'y ajoute.


def test_une_enumeration_d_outils_pese_moins_qu_une_condition(
    session_factory,
):
    """
    Cas observé sur une annonce réelle : une compétence cœur exigée,
    puis dix outils cités en environnement. Le score doit refléter la
    condition, pas la longueur de l'énumération.
    """

    session = session_factory()
    _profil(session)

    for indice in range(10):
        add_catalog_skill(
            session,
            canonical_name=f"Outil {indice}",
            aliases=[f"Outil {indice}"],
        )

    session.close()

    exigences = [
        "Gestion de projet",
        *[f"Outil {indice}" for indice in range(10)],
    ]

    annonce = (
        "Compétences requises : la maîtrise de la gestion de projet "
        "est indispensable.\n"
        "Environnement technique : "
        + ", ".join(f"Outil {indice}" for indice in range(10))
        + "."
    )

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=exigences,
        job_text=annonce,
    )

    # La condition pèse 1,00 ; chacun des dix outils pèse 0,20 fois
    # son poids de rang, soit 1,04 pour les dix réunis. Le score
    # devient 1,00 / 2,04 = 49 points, contre 16 sans niveau
    # d'exigence.
    #
    # Le candidat ne couvre toujours qu'une exigence sur onze — mais
    # l'annonce n'en pose qu'une comme condition, et il la couvre.
    assert resultat.score_skills > 45.0


def test_une_mention_absente_reste_un_ecart(session_factory):
    """
    Pondérer n'est pas dissimuler : un outil cité et non maîtrisé
    reste une compétence manquante, visible comme telle. Seule la
    liste des conditions non couvertes l'exclut.
    """

    session = session_factory()
    _profil(session)

    add_catalog_skill(session, canonical_name="Jira", aliases=["Jira"])

    session.close()

    annonce = (
        "Compétences requises : la gestion de projet est "
        "indispensable.\n"
        "Environnement : Jira, Confluence, Miro, Notion."
    )

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet", "Jira"],
        job_text=annonce,
    )

    assert "Jira" in resultat.missing_skills
    assert "Jira" not in resultat.missing_essential_skills


def test_une_condition_non_couverte_est_isolee(session_factory):
    """
    C'est la liste qui décide d'une candidature : ce que l'annonce
    pose comme condition et que le profil ne couvre pas.
    """

    session = session_factory()

    # _profil() inscrit déjà Kubernetes au référentiel, sans le
    # rattacher au candidat : l'exigence existe, la preuve non.
    _profil(session)

    session.close()

    annonce = (
        "Compétences requises : gestion de projet.\n"
        "La maîtrise de Kubernetes est indispensable."
    )

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet", "Kubernetes"],
        job_text=annonce,
    )

    assert resultat.missing_essential_skills == ["Kubernetes"]


def test_sans_texte_d_annonce_le_score_ne_bouge_pas(session_factory):
    """
    Le classement ne s'invente pas un niveau sans annonce à lire :
    les appels qui ne fournissent pas de texte gardent exactement le
    comportement d'avant.
    """

    session = session_factory()
    _profil(session)

    for indice in range(3):
        add_catalog_skill(
            session,
            canonical_name=f"Outil {indice}",
            aliases=[f"Outil {indice}"],
        )

    session.close()

    exigences = [
        "Gestion de projet",
        *[f"Outil {indice}" for indice in range(3)],
    ]

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=exigences,
    )

    # 1,00 / (1,00 + 0,833 + 0,714 + 0,625) = 31,3 points, la valeur
    # obtenue par la seule pondération de rang.
    assert 31.0 < resultat.score_skills < 31.6

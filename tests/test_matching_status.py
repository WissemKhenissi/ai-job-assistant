"""
Statuts de matching : proven / inferred / missing.

Ces tests portent sur les deux garde-fous d'honnêteté du moteur :

- une compétence technique ne doit jamais être déduite par proximité
  sémantique ;
- le statut attribué à une compétence déclarée doit refléter
  l'existence (ou l'absence) d'une preuve.
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


def _match_for(result, skill_name: str):
    """Retrouve le SkillMatch correspondant à une compétence."""

    for match in result.matches:
        if match.skill == skill_name:
            return match

    raise AssertionError(
        f"Aucun match trouvé pour {skill_name!r} "
        f"(présents : {[m.skill for m in result.matches]})"
    )


# ============================================================
# STATUT PROVEN : AVEC ET SANS PREUVE
# ============================================================

def test_competence_declaree_avec_preuve_est_prouvee(
    session_factory,
):
    from services.matching import analyze_candidate_against_skills
    from services.matching.config import PROVEN_SCORE

    session = session_factory()

    add_candidate(session)
    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet"],
    )

    skill = add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Gestion de projet",
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description="Pilotage du projet de refonte du tunnel d'achat.",
    )

    session.close()

    result = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet"],
    )

    match = _match_for(result, "Gestion de projet")

    assert match.status == "proven"
    assert match.score == PROVEN_SCORE
    assert match.evidence, "une preuve doit être rattachée"


def test_competence_declaree_sans_preuve_est_moins_bien_notee(
    session_factory,
):
    """
    Une compétence déclarée sans preuve reçoit le statut "declared"
    et un score dégradé (DECLARED_SCORE).
    """

    from services.matching import analyze_candidate_against_skills
    from services.matching.config import (
        DECLARED_SCORE,
        PROVEN_SCORE,
    )

    session = session_factory()

    add_candidate(session)
    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet"],
    )

    add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Gestion de projet",
    )

    session.close()

    result = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet"],
    )

    match = _match_for(result, "Gestion de projet")

    assert match.status == "declared"
    assert match.score == DECLARED_SCORE
    assert match.score < PROVEN_SCORE


def test_une_competence_sans_preuve_n_est_pas_listee_comme_prouvee(
    session_factory,
):
    """
    Garde-fou central du projet.

    Le principe de cadrage dit : "seules les compétences prouvées
    (avec une preuve EvidenceDB liée) peuvent apparaître comme ligne
    de compétence explicite" sur un CV généré.

    proven_skills est la liste sur laquelle la génération de CV doit
    s'appuyer : une compétence déclarée sans preuve doit en être
    absente, tout en restant visible dans matched_skills (vision
    "est-ce que je couvre cette compétence ?").
    """

    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    add_candidate(session)
    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet"],
    )

    add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Gestion de projet",
    )

    session.close()

    result = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet"],
    )

    assert result.proven_skills == []
    assert result.declared_skills == ["Gestion de projet"]
    assert result.matched_skills == ["Gestion de projet"]


def test_une_competence_avec_preuve_est_listee_comme_prouvee(
    session_factory,
):
    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    add_candidate(session)
    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet"],
    )

    skill = add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Gestion de projet",
    )

    add_evidence(
        session,
        candidate_id=CANDIDATE_ID,
        skill_id=skill.id,
        description="Refonte du tunnel d'achat, -18 % d'abandons.",
    )

    session.close()

    result = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Gestion de projet"],
    )

    assert result.proven_skills == ["Gestion de projet"]
    assert result.declared_skills == []
    assert result.matched_skills == ["Gestion de projet"]


# ============================================================
# EXCLUSION DES COMPETENCES TECHNIQUES DE L'INFERENCE
# ============================================================

@pytest.mark.parametrize(
    "technical_skill",
    [
        "Python",
        "SQL",
        "AWS",
        "Machine Learning",
        "Jira",
    ],
)
def test_une_competence_technique_non_declaree_est_manquante(
    session_factory,
    monkeypatch,
    technical_skill,
):
    """
    Même si le moteur sémantique renvoie une correspondance très
    forte, une compétence technique non déclarée doit rester
    "missing" : on ne déduit pas qu'un candidat sait coder en Python
    parce que son parcours "ressemble" à de la data.
    """

    import services.matching.inference as inference

    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    add_candidate(session)
    add_catalog_skill(
        session,
        canonical_name=technical_skill,
        aliases=[technical_skill],
    )

    # Un parcours riche, mais qui ne déclare aucune compétence
    # technique.
    add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Product Discovery",
        description=(
            "Analyse de données produit, pilotage d'indicateurs "
            "et automatisation de reportings."
        ),
    )

    session.close()

    # Le moteur sémantique est forcé au maximum : si l'exclusion
    # fonctionne, elle doit résister à ça.
    def _always_strong_match(*args, **kwargs):
        raise AssertionError(
            "Le moteur sémantique ne doit pas être sollicité "
            "pour une compétence exclue de l'inférence."
        )

    monkeypatch.setattr(
        inference,
        "find_semantic_skill_matches",
        _always_strong_match,
    )

    result = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[technical_skill],
    )

    match = _match_for(result, technical_skill)

    assert match.status == "missing"
    assert match.score == 0.0
    assert technical_skill in result.missing_skills
    assert technical_skill not in result.inferred_skills


def test_la_liste_des_exclusions_couvre_les_competences_techniques():
    """
    Garde-fou sur le contenu de la liste elle-même : une régression
    silencieuse consisterait à en retirer une entrée.
    """

    from services.matching.config import SEMANTIC_INFERENCE_EXCLUDED

    attendues = {
        "python",
        "sql",
        "r",
        "aws",
        "azure",
        "google cloud",
        "machine learning",
        "data science",
        "artificial intelligence",
        "jira",
        "product management",
    }

    assert attendues <= SEMANTIC_INFERENCE_EXCLUDED

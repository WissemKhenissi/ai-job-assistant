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

    # C'est le référentiel qui range cette compétence parmi celles
    # qui ne se déduisent pas — le moteur n'en tient plus la liste.
    add_catalog_skill(
        session,
        canonical_name=technical_skill,
        aliases=[technical_skill],
        is_inferable=False,
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

    # On enregistre les appels au lieu de lever : l'inférence
    # sémantique enveloppe l'appel dans un try/except, une exception
    # y serait avalée et le test passerait pour une mauvaise raison.
    appels: list[tuple] = []

    def _mouchard(*args, **kwargs):
        appels.append((args, kwargs))
        return []

    monkeypatch.setattr(
        inference,
        "find_semantic_skill_matches",
        _mouchard,
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

    assert not appels, (
        "Le moteur sémantique ne doit pas être sollicité pour une "
        "compétence que le référentiel dit non déductible."
    )


def test_le_referentiel_seul_decide_de_ce_qui_est_deductible(
    session_factory,
    monkeypatch,
):
    """
    Le garde-fou tenait dans deux listes écrites à la main. Elles ont
    été remplacées par une propriété du référentiel : ce test vérifie
    que c'est bien elle, et rien d'autre, qui ouvre ou ferme la porte.

    Deux compétences identiques en tout point, sauf ce drapeau.
    """

    import services.matching.inference as inference

    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    add_candidate(session)

    add_catalog_skill(
        session,
        canonical_name="Savoir-faire",
        aliases=["Savoir-faire"],
        is_inferable=True,
    )

    add_catalog_skill(
        session,
        canonical_name="Outil maison",
        aliases=["Outil maison"],
        is_inferable=False,
    )

    add_candidate_skill(
        session,
        candidate_id=CANDIDATE_ID,
        name="Product Discovery",
        description="Un parcours riche, mais qui ne les déclare pas.",
    )

    session.close()

    interrogees: list[str] = []

    def _mouchard(texte, *args, **kwargs):
        interrogees.extend(kwargs.get("restrict_to") or ())
        return []

    monkeypatch.setattr(
        inference,
        "find_semantic_skill_matches",
        _mouchard,
    )

    analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=["Savoir-faire", "Outil maison"],
    )

    assert "savoir faire" in interrogees
    assert "outil maison" not in interrogees


def test_une_competence_inconnue_du_referentiel_n_est_pas_deduite(
    session_factory,
):
    """
    Sans entrée pour la décrire, rien ne dit si un terme relève du
    savoir-faire ou de l'outillage. Le doute se résout du côté
    prudent : pas d'inférence.
    """

    from services.matching.inference import _est_deductible

    session = session_factory()
    add_candidate(session)
    session.close()

    assert _est_deductible("un terme que personne ne connait") is False


# ============================================================
# INFERENCE COMPOSITE
# ============================================================
#
# Une compétence d'ensemble se déduit de ses composantes. La règle
# était écrite pour une seule compétence, avec ses neuf composantes
# en dur ; elle lit maintenant le référentiel.


def _profil_avec(session, *competences_prouvees):
    """Un candidat qui prouve les compétences nommées."""

    add_candidate(session)

    for nom in competences_prouvees:

        add_catalog_skill(
            session, canonical_name=nom, aliases=[nom]
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


def test_un_ensemble_se_deduit_de_ses_composantes(session_factory):
    """
    Le métier n'entre pas dans la règle : ici un ensemble du bâtiment,
    composé de trois compétences que le candidat prouve.
    """

    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    _profil_avec(
        session,
        "Lecture de plans",
        "Chiffrage de travaux",
        "Coordination de chantier",
    )

    add_catalog_skill(
        session,
        canonical_name="Conduite de travaux",
        aliases=["Conduite de travaux"],
        related_skills=[
            "Lecture de plans",
            "Chiffrage de travaux",
            "Coordination de chantier",
        ],
        is_composite=True,
    )

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Conduite de travaux",
            "Lecture de plans",
            "Chiffrage de travaux",
            "Coordination de chantier",
        ],
    )

    conduite = _match_for(resultat, "Conduite de travaux")

    assert conduite.status == "inferred"
    assert "Lecture de plans" in " ".join(conduite.evidence)


def test_un_outil_ne_se_deduit_pas_de_ses_competences_associees(
    session_factory,
):
    """
    Régression observée en généralisant : « Jira » était déduit parce
    que le candidat pratiquait Agile, la gestion de backlog et la
    gestion de projet. Jira est *associé* à ces compétences, il n'en
    est pas *fait* — et on ne déduit jamais qu'un candidat connaît un
    outil.
    """

    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    _profil_avec(
        session,
        "Agile / Scrum",
        "Backlog Management",
        "Gestion de projet",
    )

    add_catalog_skill(
        session,
        canonical_name="Jira",
        aliases=["Jira"],
        related_skills=[
            "Agile / Scrum",
            "Backlog Management",
            "Gestion de projet",
        ],
        is_inferable=False,
        # Des compétences associées, mais aucune composition.
        is_composite=False,
    )

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Jira",
            "Agile / Scrum",
            "Backlog Management",
            "Gestion de projet",
        ],
    )

    assert _match_for(resultat, "Jira").status == "missing"


def test_une_composante_manquante_ne_suffit_pas(session_factory):
    """
    Deux composantes sur trois ne font pas un ensemble : le seuil
    protège contre une inférence complaisante.
    """

    from services.matching import analyze_candidate_against_skills

    session = session_factory()

    _profil_avec(session, "Lecture de plans", "Chiffrage de travaux")

    add_catalog_skill(
        session,
        canonical_name="Coordination de chantier",
        aliases=["Coordination de chantier"],
    )

    add_catalog_skill(
        session,
        canonical_name="Conduite de travaux",
        aliases=["Conduite de travaux"],
        related_skills=[
            "Lecture de plans",
            "Chiffrage de travaux",
            "Coordination de chantier",
        ],
        is_composite=True,
    )

    session.close()

    resultat = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=[
            "Conduite de travaux",
            "Lecture de plans",
            "Chiffrage de travaux",
            "Coordination de chantier",
        ],
    )

    assert _match_for(resultat, "Conduite de travaux").status == (
        "missing"
    )

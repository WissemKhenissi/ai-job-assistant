"""
Normalisation des compétences et résolution des alias.

Ces tests verrouillent le principe de cadrage : skill_catalog est
l'unique source de vérité pour la normalisation des compétences.
"""

from __future__ import annotations

import pytest

from conftest import add_catalog_skill
from services.skill_catalog_service import normalize_skill_text


# ============================================================
# NORMALISATION PURE (sans base)
# ============================================================

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Gestion de Projet", "gestion de projet"),
        ("Expérimentation", "experimentation"),
        ("Découverte produit", "decouverte produit"),
        ("Stratégie produit", "strategie produit"),
        ("E-commerce", "e commerce"),
        ("Agile / Scrum", "agile scrum"),
        ("Data / KPI", "data kpi"),
        ("product_management", "product management"),
        ("  Product   Owner  ", "product owner"),
        ("PRODUCT OWNER", "product owner"),
    ],
)
def test_normalise_accents_casse_et_separateurs(raw, expected):
    assert normalize_skill_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("C++", "c++"),
        ("C#", "c#"),
        ("Node.js", "node.js"),
    ],
)
def test_conserve_les_caracteres_techniques(raw, expected):
    """+ , # et . font partie du nom de certaines technologies."""

    assert normalize_skill_text(raw) == expected


def test_normalise_une_valeur_vide():
    assert normalize_skill_text("") == ""


# ============================================================
# RESOLUTION DES ALIAS VIA LE REFERENTIEL
# ============================================================

def test_un_alias_du_catalogue_resout_vers_le_nom_canonique(
    session_factory,
):
    from services.matching_service import _canonical_skill_name

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=[
            "Gestion de projet",
            "Project Management",
            "Pilotage de projet",
        ],
    )

    session.close()

    assert (
        _canonical_skill_name("Project Management")
        == "gestion de projet"
    )

    assert (
        _canonical_skill_name("Pilotage de projet")
        == "gestion de projet"
    )


def test_la_resolution_ignore_les_accents_et_la_casse(
    session_factory,
):
    from services.matching_service import _canonical_skill_name

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Expérimentation",
        aliases=["Expérimentation", "A/B Testing"],
    )

    session.close()

    # L'alias est accentué dans le catalogue, la requête ne l'est pas.
    assert (
        _canonical_skill_name("experimentation")
        == "experimentation"
    )

    assert (
        _canonical_skill_name("a/b testing")
        == "experimentation"
    )

    assert (
        _canonical_skill_name("A/B TESTING")
        == "experimentation"
    )


def test_le_slash_devient_un_espace_dans_les_alias(
    session_factory,
):
    """
    Piège de normalisation à connaître : "A/B Testing" devient
    "a b testing". La graphie collée "AB Testing" est donc une
    chaîne différente, qui doit être listée comme alias distinct
    dans le référentiel (c'est ce que fait seed_skill_catalog).
    """

    from services.matching_service import _canonical_skill_name

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Expérimentation",
        aliases=["Expérimentation", "A/B Testing"],
    )

    session.close()

    # Non couvert tant que "AB Testing" n'est pas un alias explicite.
    assert _canonical_skill_name("AB Testing") == "ab testing"


def test_une_competence_inconnue_retombe_sur_sa_forme_normalisee(
    session_factory,
):
    """
    Aucune invention : si le référentiel ne connaît pas la compétence,
    elle est simplement normalisée, jamais rattachée de force à une
    compétence existante.
    """

    from services.matching_service import _canonical_skill_name

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet"],
    )

    session.close()

    assert (
        _canonical_skill_name("Soudure à l'arc")
        == "soudure a l arc"
    )


def test_le_catalogue_est_bien_la_source_de_verite(
    session_factory,
):
    """
    Garde-fou anti-régression : ajouter un alias au catalogue doit
    suffire à le faire reconnaître, sans toucher au code du matching
    (c'était l'objet de la suppression du dictionnaire SKILL_ALIASES).
    """

    from services.matching_service import _canonical_skill_name

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="AdTech",
        aliases=[
            "AdTech",
            "Advertising Technology",
            "Publicité digitale",
        ],
    )

    session.close()

    assert _canonical_skill_name("Publicite digitale") == "adtech"
    assert _canonical_skill_name("Advertising Technology") == "adtech"

"""
Reconnaissances douteuses du référentiel
(services.catalog_hygiene).

Le référentiel apprend déjà des termes qu'il ne connaît pas. Il
manquait le symétrique : les termes qu'il croit connaître et
reconnaît de travers. Après l'import d'ESCO, « CMS » désignait la
technologie de montage en surface, et « FNAC » une ponction à
l'aiguille fine — deux exigences ajoutées à une analyse marketing, et
comptées manquantes.
"""

from __future__ import annotations

import json

import pytest

from conftest import add_catalog_skill
from services.catalog_hygiene import (
    detections_douteuses,
    remove_alias,
)
from services.skill_catalog_service import (
    find_skill_by_name,
    invalidate_caches,
)


def _annonce(session, texte: str, titre: str = "Une annonce"):

    from models.job import JobOfferDB

    session.add(
        JobOfferDB(
            id=f"job-{titre}",
            title=titre,
            description=texte,
            status="selected",
        )
    )

    session.commit()


# ============================================================
# DETECTION
# ============================================================

def test_un_alias_etranger_a_la_competence_est_signale(
    session_factory,
):
    """
    Le cas relevé : une entrée d'électronique capte le sigle d'un
    outil de gestion de contenu.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Technologie de montage en surface",
        aliases=["Technologie de montage en surface", "CMS"],
        skill_id="esco-montage",
    )

    _annonce(session, "Vous administrez le CMS du site.")
    session.close()
    invalidate_caches()

    douteuses = detections_douteuses()

    assert [d.alias for d in douteuses] == ["CMS"]
    assert douteuses[0].canonical_name == (
        "Technologie de montage en surface"
    )
    assert douteuses[0].vient_d_un_import is True
    assert douteuses[0].offres == ["Une annonce"]


def test_un_alias_qui_ressemble_a_sa_competence_n_est_pas_signale(
    session_factory,
):
    """
    « Gestion de projets » pour « Gestion de projet » partage ses
    mots : rien à vérifier. Sans ce filtre, la liste serait
    illisible.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet", "Gestion de projets"],
    )

    _annonce(session, "Vous assurez la gestion de projets.")
    session.close()
    invalidate_caches()

    assert detections_douteuses() == []


def test_une_reconnaissance_jamais_survenue_n_est_pas_signalee(
    session_factory,
):
    """
    On ne balaie pas les 108 000 alias du référentiel : un alias qui
    n'a jamais rien reconnu ne fausse aucun score, et l'afficher
    noierait les cas réels.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Aspiration à l'aiguille fine",
        aliases=["Aspiration à l'aiguille fine", "FNAC"],
        skill_id="esco-aiguille",
    )

    _annonce(session, "Une annonce qui ne parle pas de ce sigle.")
    session.close()
    invalidate_caches()

    assert detections_douteuses() == []


def test_les_annonces_sont_citees_pour_juger_sur_piece(
    session_factory,
):

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Panneaux de sécurité",
        aliases=["Panneaux de sécurité", "transformer"],
        skill_id="esco-panneaux",
    )

    _annonce(session, "Transformer le parcours client.", "Annonce A")
    _annonce(session, "Transformer les usages.", "Annonce B")
    session.close()
    invalidate_caches()

    douteuse = detections_douteuses()[0]

    assert sorted(douteuse.offres) == ["Annonce A", "Annonce B"]


# ============================================================
# RETRAIT
# ============================================================

def test_retirer_un_alias_le_rend_inoperant(session_factory):

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Technologie de montage en surface",
        aliases=["Technologie de montage en surface", "CMS"],
        skill_id="esco-montage",
    )

    _annonce(session, "Vous administrez le CMS du site.")
    session.close()
    invalidate_caches()

    assert remove_alias("esco-montage", "CMS") is True

    assert find_skill_by_name("CMS") is None

    # La compétence, elle, existe toujours sous son nom.
    assert (
        find_skill_by_name("Technologie de montage en surface")
        is not None
    )

    assert detections_douteuses() == []


def test_le_nom_canonique_n_est_jamais_retirable(session_factory):
    """
    Une compétence que plus rien ne nomme deviendrait indétectable,
    et l'utilisateur ne verrait qu'une exigence disparue sans
    explication. Pour l'écarter, c'est is_active qui existe.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet", "Pilotage"],
    )

    session.close()
    invalidate_caches()

    with pytest.raises(ValueError):
        remove_alias("catalog-gestion de projet", "Gestion de projet")


def test_retirer_un_alias_absent_ne_change_rien(session_factory):

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet", "Pilotage"],
    )

    session.close()
    invalidate_caches()

    assert (
        remove_alias("catalog-gestion de projet", "Kubernetes")
        is False
    )

    assert find_skill_by_name("Pilotage") is not None


def test_les_autres_alias_survivent_au_retrait(session_factory):

    from database.models import SkillCatalogDB

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Artificial Intelligence",
        aliases=["Artificial Intelligence", "IA", "AI"],
        skill_id="catalog-ia",
    )

    session.close()
    invalidate_caches()

    remove_alias("catalog-ia", "AI")

    session = session_factory()
    restants = json.loads(
        session.get(SkillCatalogDB, "catalog-ia").aliases
    )
    session.close()

    assert restants == ["Artificial Intelligence", "IA"]

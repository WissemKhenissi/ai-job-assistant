"""
Intégrité du référentiel de compétences (database.seed_skill_catalog).

Un alias dit « ces deux noms désignent la même compétence ». C'est une
affirmation lourde de conséquences : elle décide si une compétence du
Master CV répond à une exigence d'annonce, donc si elle a le droit de
figurer sur un CV.

Deux entrées qui revendiquent le même alias créent une ambiguïté
silencieuse — l'index de résolution en retient une au hasard, et une
compétence se retrouve rattachée à la mauvaise. Ces tests ferment ce
piège.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from database.seed_skill_catalog import SKILLS, seed_skill_catalog
from services.skill_catalog_service import normalize_skill_text


def _proprietaires_par_alias(entrees) -> dict[str, set[str]]:

    index: dict[str, set[str]] = defaultdict(set)

    for entree in entrees:

        for alias in (
            entree["canonical_name"],
            *entree.get("aliases", []),
        ):
            index[normalize_skill_text(alias)].add(
                entree["canonical_name"]
            )

    return index


# ============================================================
# LE REFERENTIEL LIVRE
# ============================================================

def test_aucun_alias_n_est_revendique_par_deux_competences():
    ambigus = {
        alias: sorted(proprietaires)
        for alias, proprietaires in _proprietaires_par_alias(
            SKILLS
        ).items()
        if len(proprietaires) > 1
    }

    assert not ambigus, f"alias ambigus : {ambigus}"


def test_aucun_nom_canonique_n_est_en_double():
    noms = [entree["canonical_name"] for entree in SKILLS]

    assert len(noms) == len(set(noms))


def test_chaque_entree_a_un_identifiant_unique():
    identifiants = [entree["id"] for entree in SKILLS]

    assert len(identifiants) == len(set(identifiants))


def test_chaque_entree_se_reconnait_elle_meme():
    """
    Le nom canonique doit figurer parmi les alias, sinon une annonce
    qui l'emploie mot pour mot ne le reconnaîtrait pas.
    """

    manquants = [
        entree["canonical_name"]
        for entree in SKILLS
        if normalize_skill_text(entree["canonical_name"])
        not in {
            normalize_skill_text(alias)
            for alias in entree.get("aliases", [])
        }
    ]

    assert not manquants, (
        f"noms canoniques absents de leurs alias : {manquants}"
    )


# ============================================================
# LE GARDE-FOU
# ============================================================

def test_le_seed_refuse_un_alias_ambigu(session_factory, monkeypatch):
    """
    Mieux vaut refuser le référentiel que rattacher silencieusement
    une compétence à la mauvaise.
    """

    import database.seed_skill_catalog as seed

    monkeypatch.setattr(
        seed,
        "SKILLS",
        [
            {
                "id": "catalog-a",
                "canonical_name": "Compétence A",
                "category": "Test",
                "subcategory": "",
                "description": "",
                "aliases": ["Compétence A", "Terme partagé"],
                "parent": None,
                "related_skills": [],
            },
            {
                "id": "catalog-b",
                "canonical_name": "Compétence B",
                "category": "Test",
                "subcategory": "",
                "description": "",
                "aliases": ["Compétence B", "Terme partagé"],
                "parent": None,
                "related_skills": [],
            },
        ],
    )

    with pytest.raises(ValueError, match="Terme partagé"):
        seed.seed_skill_catalog()


def test_le_seed_refuse_un_nom_canonique_en_double(
    session_factory,
    monkeypatch,
):
    import database.seed_skill_catalog as seed

    entree = {
        "id": "catalog-a",
        "canonical_name": "Compétence A",
        "category": "Test",
        "subcategory": "",
        "description": "",
        "aliases": ["Compétence A"],
        "parent": None,
        "related_skills": [],
    }

    monkeypatch.setattr(
        seed, "SKILLS", [entree, dict(entree, id="catalog-b")]
    )

    with pytest.raises(ValueError, match="Doublon"):
        seed.seed_skill_catalog()


def test_le_seed_est_idempotent(session_factory):
    """
    Le rejouer ne doit ni dupliquer, ni perdre d'entrée.
    """

    from database.models import SkillCatalogDB

    seed_skill_catalog()

    session = session_factory()
    premier = session.query(SkillCatalogDB).count()
    session.close()

    seed_skill_catalog()

    session = session_factory()
    second = session.query(SkillCatalogDB).count()
    session.close()

    assert premier == second == len(SKILLS)

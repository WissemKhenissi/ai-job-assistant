"""
Import du référentiel ESCO (services.esco_import).

Les tests travaillent sur un mini-ESCO écrit à la main : le vrai
fichier fait 13 960 lignes et n'a pas sa place dans une suite de
tests, mais sa **structure** est reproduite fidèlement — mêmes
colonnes, mêmes valeurs de `skillType` et `reuseLevel`, alias séparés
par des retours à la ligne.

Ce qui est verrouillé ici est ce qui protège le référentiel d'un
import massif venu de l'extérieur : le catalogue maison l'emporte, un
alias n'appartient qu'à une entrée, et un mot isolé trop courant n'en
devient jamais un.
"""

from __future__ import annotations

import csv

import pytest

from conftest import add_catalog_skill
from services.esco_import import (
    alias_exploitable,
    import_esco,
)
from services.skill_catalog_service import find_skill_by_name


COLONNES_SKILLS = [
    "conceptType",
    "conceptUri",
    "skillType",
    "reuseLevel",
    "preferredLabel",
    "altLabels",
    "hiddenLabels",
    "status",
    "modifiedDate",
    "scopeNote",
    "definition",
    "inScheme",
    "description",
]


def _ligne(
    uri: str,
    label: str,
    alias: str = "",
    skill_type: str = "knowledge",
    reuse: str = "sector-specific",
) -> dict:
    return {
        **{colonne: "" for colonne in COLONNES_SKILLS},
        "conceptType": "KnowledgeSkillCompetence",
        "conceptUri": f"http://data.europa.eu/esco/skill/{uri}",
        "skillType": skill_type,
        "reuseLevel": reuse,
        "preferredLabel": label,
        "altLabels": alias,
        "status": "released",
        "description": f"Description de {label}.",
    }


@pytest.fixture
def mini_esco(tmp_path):
    """Un dossier ESCO minimal, structuré comme le vrai."""

    dossier = tmp_path / "esco_fr"
    dossier.mkdir()

    lignes = [
        _ligne("aaa", "réanimation", "soins intensifs\nsoins critiques"),
        _ligne("bbb", "comptabilité générale", "tenue de comptes"),
        _ligne(
            "ccc",
            "gestion des appareils mobiles",
            "AVEC\nMDM",
        ),
        _ligne(
            "ddd",
            "travailler en équipe",
            reuse="transversal",
        ),
        _ligne(
            "eee",
            "appliquer la méthode HACCP",
            "hygiène alimentaire",
            skill_type="skill/competence",
        ),
    ]

    with open(
        dossier / "skills_fr.csv", "w", encoding="utf-8", newline=""
    ) as fichier:
        writer = csv.DictWriter(fichier, fieldnames=COLONNES_SKILLS)
        writer.writeheader()
        writer.writerows(lignes)

    # Hiérarchie : une seule catégorie, atteinte directement.
    with open(
        dossier / "broaderRelationsSkillPillar_fr.csv",
        "w",
        encoding="utf-8",
        newline="",
    ) as fichier:
        writer = csv.DictWriter(
            fichier,
            fieldnames=[
                "conceptType",
                "conceptUri",
                "conceptLabel",
                "broaderType",
                "broaderUri",
                "broaderLabel",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "conceptType": "KnowledgeSkillCompetence",
                "conceptUri": (
                    "http://data.europa.eu/esco/skill/aaa"
                ),
                "conceptLabel": "réanimation",
                "broaderType": "SkillGroup",
                "broaderUri": "groupe-sante",
                "broaderLabel": "santé",
            }
        )

    with open(
        dossier / "skillsHierarchy_fr.csv",
        "w",
        encoding="utf-8",
        newline="",
    ) as fichier:
        writer = csv.DictWriter(
            fichier,
            fieldnames=["Level 0 URI", "Level 1 URI", "Level 1 preferred term"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Level 0 URI": "racine",
                "Level 1 URI": "groupe-sante",
                "Level 1 preferred term": "santé et protection sociales",
            }
        )

    return dossier


# ============================================================
# QUALITE DES ALIAS
# ============================================================

def test_un_mot_outil_ne_peut_pas_etre_un_alias():
    """
    Cas réel : « AVEC » est un alias ESCO de « gestion des appareils
    mobiles ». Il reconnaissait une exigence dans toute phrase
    contenant la préposition — observé sur deux annonces sans le
    moindre rapport entre elles.
    """

    assert not alias_exploitable("AVEC")


def test_un_terme_compose_passe_toujours():
    assert alias_exploitable("gestion des appareils mobiles")
    assert alias_exploitable("gestion de projet")


def test_un_mot_trop_general_ne_peut_pas_etre_un_alias():
    assert not alias_exploitable("acquisition")
    assert not alias_exploitable("mobile")


def test_un_alias_trop_court_est_refuse():
    assert not alias_exploitable("go")
    assert not alias_exploitable("x")


def test_un_sigle_specifique_reste_admis():
    assert alias_exploitable("HACCP")
    assert alias_exploitable("MDM")


# ============================================================
# IMPORT
# ============================================================

def test_les_competences_sont_importees(session_factory, mini_esco):
    resume = import_esco(mini_esco)

    assert resume.created == 4  # la transversale est exclue

    competence = find_skill_by_name("réanimation")

    assert competence is not None
    assert "soins intensifs" in competence.aliases


def test_une_competence_transversale_est_exclue(
    session_factory, mini_esco
):
    """
    « travailler en équipe » figurerait dans presque toutes les
    annonces et gonflerait les exigences sans rien distinguer.
    """

    resume = import_esco(mini_esco)

    assert find_skill_by_name("travailler en équipe") is None
    assert resume.skipped_transversal == 1


def test_les_transversales_peuvent_etre_demandees(
    session_factory, mini_esco
):
    import_esco(mini_esco, include_transversal=True)

    assert find_skill_by_name("travailler en équipe") is not None


def test_le_referentiel_maison_gagne(session_factory, mini_esco):
    """
    Une entrée écrite à la main est plus précise pour ce candidat que
    son équivalent générique : l'import ne doit pas la remplacer.
    """

    session = session_factory()
    add_catalog_skill(
        session,
        canonical_name="Réanimation",
        aliases=["Réanimation", "Soins critiques"],
        skill_id="catalog-maison",
        category="Santé",
    )
    session.close()

    resume = import_esco(mini_esco)

    assert resume.skipped_existing_name >= 1

    competence = find_skill_by_name("réanimation")

    assert competence.id == "catalog-maison"
    assert competence.category == "Santé"


def test_un_alias_deja_pris_est_abandonne(session_factory, mini_esco):
    """
    Un alias n'appartient qu'à une entrée : le déplacer rattacherait
    une compétence du Master CV à la mauvaise.
    """

    session = session_factory()
    add_catalog_skill(
        session,
        canonical_name="Soins critiques",
        aliases=["Soins critiques"],
        skill_id="catalog-maison",
    )
    session.close()

    resume = import_esco(mini_esco)

    assert resume.aliases_dropped >= 1
    assert find_skill_by_name("Soins critiques").id == "catalog-maison"


def test_le_mot_outil_n_entre_pas_au_referentiel(
    session_factory, mini_esco
):
    import_esco(mini_esco)

    assert find_skill_by_name("AVEC") is None
    assert find_skill_by_name("MDM") is not None


def test_la_categorie_vient_de_la_hierarchie(
    session_factory, mini_esco
):
    import_esco(mini_esco)

    assert (
        find_skill_by_name("réanimation").category
        == "santé et protection sociales"
    )


# ============================================================
# PRUDENCE
# ============================================================

def test_un_essai_a_blanc_n_ecrit_rien(session_factory, mini_esco):
    resume = import_esco(mini_esco, dry_run=True)

    assert resume.created == 4
    assert resume.dry_run
    assert find_skill_by_name("réanimation") is None


def test_reimporter_ne_cree_pas_de_doublon(
    session_factory, mini_esco
):
    import_esco(mini_esco)

    second = import_esco(mini_esco)

    assert second.created == 0
    assert second.already_imported == 4


def test_un_fichier_absent_est_signale(session_factory, tmp_path):
    vide = tmp_path / "vide"
    vide.mkdir()

    with pytest.raises(FileNotFoundError):
        import_esco(vide)

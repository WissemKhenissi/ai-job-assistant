"""
Écart entre le référentiel en base et celui du dépôt
(services.catalog_drift).

Le tri des termes se fait depuis l'écran Référentiel, qui écrit en
base. Le référentiel est aussi décrit dans
database/seed_skill_catalog.py, et le seed REMPLACE ce qu'il gère au
lieu de le compléter. Quatorze alias issus du tri ont disparu à un
passage du seed, et la mesure publiée sur onze annonces portait donc
sur un moteur que le dépôt ne décrivait pas.

Ces tests tiennent les deux bouts : que la dérive soit vue quand elle
existe, et qu'on ne crie pas quand elle n'existe pas — une alerte qui
s'affiche pour rien finit par être ignorée le jour où elle compte.
"""

from __future__ import annotations

import json

import pytest

from conftest import add_catalog_skill

from database.models import SkillCatalogDB
from database.seed_skill_catalog import champs_ecrases_par_le_seed
from services.catalog_drift import (
    divergences_avec_le_seed,
    extrait_de_seed,
)


def _entree_seed(
    skill_id: str = "catalog-jira",
    canonical_name: str = "Jira",
    aliases: list[str] | None = None,
    **extra,
) -> dict:
    """Une entrée du seed, réduite à ce que les tests font varier."""

    donnees = {
        "id": skill_id,
        "canonical_name": canonical_name,
        "category": "Test",
        "subcategory": "",
        "description": "",
        "aliases": aliases if aliases is not None else [canonical_name],
        "parent": None,
        "related_skills": [],
    }

    donnees.update(extra)

    return donnees


@pytest.fixture
def seed(monkeypatch):
    """Remplace le seed du dépôt par celui que le test décrit."""

    def poser(entrees: list[dict]) -> None:
        import services.catalog_drift as module

        monkeypatch.setattr(module, "SKILLS", entrees)

    return poser


# ============================================================
# AUCUNE DERIVE
# ============================================================

def test_base_conforme_au_depot_aucune_derive(
    session_factory, seed
):

    session = session_factory()

    add_catalog_skill(
        session,
        "Jira",
        aliases=["Jira", "Atlassian Jira"],
        skill_id="catalog-jira",
    )

    session.close()

    seed([_entree_seed(aliases=["Jira", "Atlassian Jira"])])

    assert not divergences_avec_le_seed()


def test_alias_seulement_reordonnes_ne_derivent_pas(
    session_factory, seed
):
    """
    Le seed réécrit la colonne, mais rien n'est perdu.

    Prévenir pour un changement d'ordre apprendrait à cliquer sans
    lire, et le jour où un alias disparaît vraiment, l'alerte aurait
    déjà perdu son crédit.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        "Jira",
        aliases=["Atlassian Jira", "Jira"],
        skill_id="catalog-jira",
    )

    session.close()

    seed([_entree_seed(aliases=["Jira", "Atlassian Jira"])])

    assert not divergences_avec_le_seed()


def test_les_entrees_importees_ne_sont_jamais_une_derive(
    session_factory, seed
):
    """
    ESCO n'a pas à figurer dans le seed.

    Les treize mille entrées importées viennent d'un fichier de
    référence, pas d'une décision : les compter ferait hurler le
    garde-fou en permanence, donc jamais.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        "médecine physique",
        aliases=["médecine physique", "PRM"],
        skill_id="esco-12345",
    )

    session.close()

    seed([])

    assert not divergences_avec_le_seed()


# ============================================================
# CE QU'UN SEED DETRUIRAIT
# ============================================================

def test_alias_ajoute_en_base_est_signale_comme_perdu(
    session_factory, seed
):
    """Le cas réel : « gestion de projets » ajouté depuis l'écran."""

    session = session_factory()

    add_catalog_skill(
        session,
        "Gestion de projet",
        aliases=["Gestion de projet", "gestion de projets"],
        skill_id="catalog-project-management",
    )

    session.close()

    seed(
        [
            _entree_seed(
                skill_id="catalog-project-management",
                canonical_name="Gestion de projet",
                aliases=["Gestion de projet"],
            )
        ]
    )

    derive = divergences_avec_le_seed()

    assert derive
    assert derive.alias_en_peril == 1

    (entree,) = derive.modifiees

    assert entree.alias_perdus == ["gestion de projets"]
    assert entree.alias_a_recuperer == []
    assert entree.perd_quelque_chose


def test_alias_present_au_depot_et_pas_en_base_ne_perd_rien(
    session_factory, seed
):
    """La base est en retard d'un seed : rien n'est en péril."""

    session = session_factory()

    add_catalog_skill(
        session,
        "Jira",
        aliases=["Jira"],
        skill_id="catalog-jira",
    )

    session.close()

    seed([_entree_seed(aliases=["Jira", "Atlassian Jira"])])

    derive = divergences_avec_le_seed()

    assert derive
    assert derive.alias_en_peril == 0

    (entree,) = derive.modifiees

    assert entree.alias_a_recuperer == ["Atlassian Jira"]
    assert not entree.perd_quelque_chose


@pytest.mark.parametrize(
    "champ, valeur_en_base",
    [
        ("description", "Écrite depuis l'écran"),
        ("is_inferable", False),
        ("is_active", False),
        ("category", "Autre"),
    ],
)
def test_un_champ_modifie_en_base_est_signale(
    session_factory, seed, champ, valeur_en_base
):
    """
    Les alias ne sont pas seuls en jeu.

    Désactiver une compétence depuis l'écran, par exemple, ne
    survit pas non plus : le seed réimpose is_active.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        "Jira",
        aliases=["Jira"],
        skill_id="catalog-jira",
    )

    ligne = session.get(SkillCatalogDB, "catalog-jira")
    setattr(ligne, champ, valeur_en_base)
    session.commit()
    session.close()

    seed([_entree_seed()])

    derive = divergences_avec_le_seed()

    assert derive
    assert derive.modifiees[0].autres_champs == [champ]


# ============================================================
# CE QUE LE DEPOT NE CONNAIT PAS
# ============================================================

def test_competence_creee_depuis_l_ecran_est_hors_depot(
    session_factory, seed
):
    """
    Elle survit au seed, mais pas au clone.

    promote_to_catalog fabrique un identifiant catalog-<uuid> : rien
    ne la distingue d'une entrée du dépôt, sauf son absence du seed.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        "Marketplace B2B",
        aliases=["Marketplace B2B", "place de marché B2B"],
        skill_id="catalog-1f2e3d4c",
    )

    session.close()

    seed([])

    derive = divergences_avec_le_seed()

    assert derive
    assert [e.canonical_name for e in derive.hors_depot] == [
        "Marketplace B2B"
    ]


def test_entree_du_depot_absente_de_la_base(session_factory, seed):

    session_factory().close()

    seed([_entree_seed()])

    derive = divergences_avec_le_seed()

    assert derive
    assert derive.absentes_de_la_base == ["Jira"]


def test_appariement_par_nom_quand_l_identifiant_differe(
    session_factory, seed
):
    """
    Le seed apparie par id, puis à défaut par nom canonique.

    Les entrées versées au seed après coup gardent en base
    l'identifiant uuid de leur création : les apparier par id seul
    les déclarerait toutes hors dépôt, et l'alerte serait fausse dès
    le premier lancement.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        "Jira",
        aliases=["Jira"],
        skill_id="catalog-9a8b7c6d",
    )

    session.close()

    seed([_entree_seed(skill_id="catalog-jira", aliases=["Jira"])])

    assert not divergences_avec_le_seed()


# ============================================================
# CE QU'ON PROPOSE DE REPORTER
# ============================================================

def test_extrait_de_seed_nomme_les_alias_perdus(
    session_factory, seed
):

    session = session_factory()

    add_catalog_skill(
        session,
        "Data / KPI",
        aliases=["Data / KPI", "KPIs"],
        skill_id="catalog-data-kpi",
    )

    session.close()

    seed(
        [
            _entree_seed(
                skill_id="catalog-data-kpi",
                canonical_name="Data / KPI",
                aliases=["Data / KPI"],
            )
        ]
    )

    texte = extrait_de_seed(divergences_avec_le_seed())

    assert '"KPIs",' in texte
    assert "Data / KPI" in texte


# ============================================================
# LE GARDE-FOU SURVEILLE-T-IL TOUT CE QUE LE SEED ECRASE ?
# ============================================================

def test_aucune_colonne_du_modele_n_echappe_au_garde_fou():
    """
    Le jour où une colonne s'ajoute au référentiel.

    Le garde-fou et le seed partagent champs_ecrases_par_le_seed :
    ce test vérifie que cette liste couvre bien toutes les colonnes
    de la table, hors celles qui ne peuvent pas dériver. Sans lui,
    une colonne ajoutée au modèle et au seed serait écrasée en
    silence, et l'alerte jurerait que tout va bien.
    """

    surveillees = set(
        champs_ecrases_par_le_seed(_entree_seed()).keys()
    )

    # L'identifiant n'est pas une valeur : c'est la clé d'appariement.
    hors_sujet = {"id"}

    colonnes = {
        colonne.name
        for colonne in SkillCatalogDB.__table__.columns
    }

    assert colonnes - hors_sujet - surveillees == set()


def test_le_seed_ecrase_bien_les_colonnes_annoncees(
    session_factory,
):
    """
    Le garde-fou dit « ceci sera remplacé » — vérifions-le.

    Il ne suffit pas que la liste existe : elle doit décrire ce que
    le seed fait vraiment. On rejoue ici le geste du seed sur une
    entrée modifiée à la main, et on vérifie qu'elle est bien
    ramenée à sa version dépôt.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        "Jira",
        aliases=["Jira", "ajouté à la main"],
        skill_id="catalog-jira",
    )

    ligne = session.get(SkillCatalogDB, "catalog-jira")

    for champ, valeur in champs_ecrases_par_le_seed(
        _entree_seed()
    ).items():
        setattr(ligne, champ, valeur)

    session.commit()

    relue = json.loads(
        session.get(SkillCatalogDB, "catalog-jira").aliases
    )

    session.close()

    assert relue == ["Jira"]

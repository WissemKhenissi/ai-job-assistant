"""
Détection des compétences dans une annonce
(services.job_requirements_service).

Cette étape n'avait aucun test, alors qu'elle décide de tout ce qui
suit : ce qu'elle ne reconnaît pas ne sera jamais comparé au Master
CV, et n'a donc aucune chance de figurer sur un CV.

Elle a été réécrite pour cesser de balayer le référentiel entier à
chaque annonce. Ces tests fixent les deux choses qui comptent : le
**résultat** ne change pas, et le **coût** ne suit plus la taille du
référentiel — sans quoi importer une taxonomie publique de plusieurs
milliers d'entrées resterait impossible.
"""

from __future__ import annotations

import json
import time

from conftest import add_catalog_skill
from services.job_requirements_service import (
    extract_required_skills,
    extract_required_skills_detailed,
)
from services.skill_catalog_service import invalidate_caches


def _referentiel(session_factory):
    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="SQL",
        aliases=["SQL", "Requêtes SQL"],
        skill_id="catalog-sql",
    )
    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery", "Découverte produit"],
        skill_id="catalog-discovery",
    )
    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet", "Pilotage de projet"],
        skill_id="catalog-projet",
    )

    session.close()


# ============================================================
# RESULTAT
# ============================================================

def test_une_competence_est_reconnue_par_son_nom(session_factory):
    _referentiel(session_factory)

    assert "SQL" in extract_required_skills("Maîtrise de SQL exigée.")


def test_une_competence_est_reconnue_par_un_alias(session_factory):
    _referentiel(session_factory)

    trouvees = extract_required_skills(
        "Vous écrirez des requêtes SQL quotidiennement."
    )

    assert trouvees == ["SQL"]


def test_un_alias_de_plusieurs_mots_est_reconnu(session_factory):
    _referentiel(session_factory)

    assert "Product Discovery" in extract_required_skills(
        "Vous menez la découverte produit avec les utilisateurs."
    )


def test_un_terme_n_est_pas_reconnu_dans_un_mot_plus_long(
    session_factory,
):
    """
    « SQL » ne doit pas se reconnaître dans « SQLite » : c'est la
    frontière de mot qui distingue une exigence d'une coïncidence.
    """

    _referentiel(session_factory)

    assert extract_required_skills("Base embarquée SQLite.") == []


def test_les_accents_et_la_casse_sont_ignores(session_factory):
    _referentiel(session_factory)

    assert extract_required_skills(
        "DECOUVERTE PRODUIT et gestion de projet"
    ) == ["Product Discovery", "Gestion de projet"]


def test_l_ordre_suit_l_apparition_dans_l_annonce(session_factory):
    """
    L'ordre porte une information : ce que l'annonce cite en premier
    compte davantage, et le CV le présente dans cet ordre.
    """

    _referentiel(session_factory)

    assert extract_required_skills(
        "Gestion de projet, puis SQL, puis Product Discovery."
    ) == ["Gestion de projet", "SQL", "Product Discovery"]


def test_une_competence_repetee_n_est_comptee_qu_une_fois(
    session_factory,
):
    _referentiel(session_factory)

    assert extract_required_skills(
        "SQL, encore SQL, toujours des requêtes SQL."
    ) == ["SQL"]


def test_une_annonce_sans_competence_connue_ne_retourne_rien(
    session_factory,
):
    _referentiel(session_factory)

    assert extract_required_skills(
        "Vous aimez le contact humain et le travail soigné."
    ) == []


def test_un_texte_vide_ne_retourne_rien(session_factory):
    _referentiel(session_factory)

    assert extract_required_skills("") == []


# ============================================================
# VERSION DETAILLEE
# ============================================================

def test_le_detail_dit_quel_alias_a_declenche_la_detection(
    session_factory,
):
    """
    Sans cette information, impossible d'expliquer pourquoi une
    compétence a été retenue — ni de corriger un alias trop large.
    """

    _referentiel(session_factory)

    detail = extract_required_skills_detailed(
        "Vous écrirez des requêtes SQL."
    )

    assert detail[0]["canonical_name"] == "SQL"
    assert detail[0]["matched_alias"] == "Requêtes SQL"
    assert detail[0]["skill_id"] == "catalog-sql"


# ============================================================
# COUT
# ============================================================

def _referentiel_volumineux(session_factory, nombre: int):
    """Un référentiel de la taille d'une taxonomie publique."""

    from database.models import SkillCatalogDB

    session = session_factory()

    for index in range(nombre):

        nom = f"compétence numéro {index}"

        session.add(
            SkillCatalogDB(
                id=f"catalog-{index}",
                canonical_name=nom,
                category="Test",
                subcategory="",
                description="",
                aliases=json.dumps(
                    [nom, f"alias {index}"], ensure_ascii=False
                ),
                parent_skill_id=None,
                related_skills="[]",
                is_active=True,
            )
        )

    session.commit()
    session.close()

    invalidate_caches()


def test_le_cout_ne_suit_pas_la_taille_du_referentiel(
    session_factory,
):
    """
    Le verrou qui rend une taxonomie publique importable.

    L'ancienne implémentation lançait une recherche par expression
    régulière **par alias** : mesurée à 23 ms sur 46 entrées, elle
    demandait près de sept secondes extrapolée à 14 000. La borne
    ci-dessous est très large — elle ne cherche pas à mesurer une
    vitesse, seulement à faire échouer bruyamment un retour au
    balayage linéaire.
    """

    _referentiel_volumineux(session_factory, 5_000)

    annonce = (
        "Nous recherchons un profil confirmé pour la compétence "
        "numéro 42 et la compétence numéro 4000. " * 20
    )

    extract_required_skills(annonce)  # amorce l'index

    debut = time.perf_counter()

    for _ in range(10):
        extract_required_skills(annonce)

    duree_moyenne = (time.perf_counter() - debut) / 10

    assert duree_moyenne < 0.2, (
        f"{duree_moyenne * 1000:.0f} ms par annonce sur 5 000 "
        "compétences : le coût suit de nouveau la taille du "
        "référentiel."
    )


def test_un_gros_referentiel_reconnait_toujours(session_factory):
    """Rapide ne doit pas vouloir dire aveugle."""

    _referentiel_volumineux(session_factory, 2_000)

    assert extract_required_skills(
        "Vous maîtrisez la compétence numéro 7 et l'alias 1234."
    ) == ["compétence numéro 7", "compétence numéro 1234"]


# ============================================================
# FRONTIERES DE PONCTUATION
# ============================================================
#
# La normalisation efface la ponctuation. Un groupe de mots pouvait
# donc enjamber une virgule et reconnaître une compétence que
# l'annonce ne nomme nulle part.


def test_un_groupe_de_mots_ne_franchit_pas_une_virgule(
    session_factory,
):
    """
    Cas relevé sur une annonce réelle : « Compétences attendues :
    gestion de projet, agile/scrum » faisait apparaître l'entrée
    « gestion de projet agile », reconnue à cheval sur la virgule.
    Deux exigences pour une, dont une fantôme — et comptée manquante,
    puisque le candidat ne peut pas prouver une compétence que
    l'annonce ne demande pas.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["Gestion de projet"],
    )
    add_catalog_skill(
        session,
        canonical_name="Agile / Scrum",
        aliases=["Agile", "Scrum"],
    )
    add_catalog_skill(
        session,
        canonical_name="Gestion de projet agile",
        aliases=["gestion de projet agile"],
    )

    session.close()
    invalidate_caches()

    detectees = extract_required_skills(
        "Compétences attendues : gestion de projet, agile/scrum."
    )

    assert "Gestion de projet" in detectees
    assert "Agile / Scrum" in detectees
    assert "Gestion de projet agile" not in detectees


def test_une_barre_oblique_reste_franchissable(session_factory):
    """
    « agile/scrum » désigne une compétence unique, et le référentiel
    la nomme avec un espace. Traiter la barre oblique comme une
    frontière la rendrait indétectable.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Agile / Scrum",
        aliases=["Agile / Scrum"],
    )

    session.close()
    invalidate_caches()

    assert extract_required_skills(
        "Méthodologie agile/scrum au quotidien."
    ) == ["Agile / Scrum"]


def test_un_point_de_version_ne_coupe_pas_le_terme(session_factory):
    """
    Le point ne sépare que suivi d'une espace ou d'une fin de texte :
    sans cette précaution, « node.js » deviendrait deux termes que
    rien ne pourrait plus rapprocher de l'entrée du référentiel.
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Node.js",
        aliases=["Node.js", "NodeJS"],
    )

    session.close()
    invalidate_caches()

    assert extract_required_skills(
        "Environnement node.js, en production."
    ) == ["Node.js"]


def test_une_fin_de_phrase_coupe_bien(session_factory):
    """
    Le pendant : « ... la gestion. Projet agile ... » ne doit pas
    faire apparaître « gestion de projet ».
    """

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Gestion de projet",
        aliases=["gestion projet"],
    )

    session.close()
    invalidate_caches()

    assert (
        extract_required_skills(
            "Vous assurez la gestion. Projet livré en juin."
        )
        == []
    )


def test_l_ordre_d_apparition_survit_au_decoupage(session_factory):
    """
    L'ordre porte une information — ce que l'annonce cite en premier
    pèse davantage dans le score. Découper l'annonce en fragments ne
    doit pas le brouiller.
    """

    session = session_factory()

    add_catalog_skill(session, canonical_name="Python", aliases=["Python"])
    add_catalog_skill(session, canonical_name="SQL", aliases=["SQL"])
    add_catalog_skill(session, canonical_name="Docker", aliases=["Docker"])

    session.close()
    invalidate_caches()

    assert extract_required_skills(
        "D'abord Docker. Ensuite Python ; enfin SQL."
    ) == ["Docker", "Python", "SQL"]

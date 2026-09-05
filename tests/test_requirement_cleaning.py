"""
Tri des exigences extraites d'une annonce (services.requirement_cleaning).

Le catalogue ne détecte que ce qu'il connaît : sa sortie est propre.
L'extraction par l'IA est libre, et sur une annonce marketing elle
rapporte « Data », « mobile », « acquisition », « influence » — des
mots de l'annonce, pas des compétences.

Comptés comme exigences, ces fragments abaissent le score d'adéquation
et se retrouvent dans la liste des termes interdits à la rédaction. Le
cas le plus parlant, observé en réel : « Data » interdit alors que
« Data / KPI » est une compétence prouvée du candidat.
"""

from __future__ import annotations

import pytest

from conftest import add_catalog_skill
from services.requirement_cleaning import (
    clean_required_skills,
    is_plausible_requirement,
)


@pytest.fixture
def catalogue(session_factory):
    """Un référentiel minimal, comme en production."""

    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Data / KPI",
        aliases=["Data / KPI", "KPI", "Reporting"],
    )
    add_catalog_skill(
        session,
        canonical_name="Backlog Management",
        aliases=[
            "Backlog Management",
            "Product backlog",
            "Gestion du backlog",
        ],
    )
    add_catalog_skill(
        session, canonical_name="Jira", aliases=["Jira"]
    )

    session.close()


# ============================================================
# CE QUI EST ECARTE
# ============================================================

@pytest.mark.parametrize(
    "fragment",
    ["Data", "mobile", "acquisition", "fidélisation", "influence"],
)
def test_un_mot_generique_isole_n_est_pas_une_competence(
    catalogue, fragment
):
    assert not is_plausible_requirement(fragment)


def test_les_fragments_sont_retires_du_decompte(catalogue):
    retenues, ecartees = clean_required_skills(
        ["Jira", "Data", "mobile", "marketing automation"]
    )

    assert retenues == ["Jira", "marketing automation"]
    assert ecartees == ["Data", "mobile"]


# ============================================================
# CE QUI EST GARDE
# ============================================================

@pytest.mark.parametrize(
    "exigence",
    [
        "CRM",
        "CDP",
        "marketing automation",
        "social media",
        "web-to-store",
        "e-réputation",
        "Cycle en V",
        "coordination des équipes techniques",
    ],
)
def test_un_terme_compose_ou_un_acronyme_est_conserve(
    catalogue, exigence
):
    """
    En cas de doute, on garde : écarter une vraie exigence fausserait
    l'analyse dans l'autre sens.
    """

    assert is_plausible_requirement(exigence)


def test_le_referentiel_l_emporte_sur_la_liste_generique(catalogue):
    """
    « Reporting » figure parmi les termes génériques, mais le
    référentiel le connaît comme compétence : il est conservé.
    """

    assert is_plausible_requirement("Reporting")


def test_un_terme_du_referentiel_est_toujours_conserve(catalogue):
    retenues, ecartees = clean_required_skills(["Data / KPI"])

    assert retenues == ["Data / KPI"]
    assert ecartees == []


# ============================================================
# DEDUPLICATION
# ============================================================

def test_deux_libelles_de_la_meme_competence_ne_comptent_qu_une_fois(
    catalogue,
):
    retenues, _ecartees = clean_required_skills(
        ["Product backlog", "Gestion du backlog"]
    )

    assert retenues == ["Product backlog"]


def test_le_libelle_de_l_annonce_est_conserve(catalogue):
    """
    Le CV affiche le mot de l'annonce, qui est aussi celui que l'ATS
    cherche : la déduplication ne doit pas le remplacer par le nom
    canonique.
    """

    retenues, _ecartees = clean_required_skills(["Gestion du backlog"])

    assert retenues == ["Gestion du backlog"]


def test_un_doublon_exact_ne_compte_qu_une_fois(catalogue):
    retenues, _ecartees = clean_required_skills(["Jira", "jira"])

    assert retenues == ["Jira"]


# ============================================================
# CAS LIMITES
# ============================================================

def test_une_liste_vide_ne_casse_rien(catalogue):
    assert clean_required_skills([]) == ([], [])


def test_les_chaines_vides_sont_ignorees(catalogue):
    retenues, ecartees = clean_required_skills(["", "   ", "Jira"])

    assert retenues == ["Jira"]
    assert ecartees == []


def test_un_terme_ecarte_deux_fois_n_est_signale_qu_une_fois(
    catalogue,
):
    _retenues, ecartees = clean_required_skills(["Data", "data"])

    assert ecartees == ["Data"]


# ============================================================
# LE NOM DU POSTE N'EST PAS UNE COMPETENCE
# ============================================================
#
# Une annonce de Product Owner comptait « Product Owner » parmi ses
# exigences, et le candidat qui ne porte pas ce titre dans son Master
# CV la voyait manquante. Le prompt d'extraction l'interdit désormais
# à l'IA ; ce garde-fou-ci est déterministe, et tient quel que soit
# l'humeur du modèle.


def test_l_intitule_du_poste_est_ecarte(session_factory):

    session = session_factory()
    session.close()

    retenues, ecartees = clean_required_skills(
        ["Product Owner", "Roadmap produit"],
        job_title="Product Owner Digital",
        job_description="Vous piloterez la roadmap produit.",
    )

    assert retenues == ["Roadmap produit"]
    assert ecartees == ["Product Owner"]


def test_une_competence_citee_dans_l_intitule_survit(
    session_factory,
):
    """
    Le garde-fou est étroit à dessein. Écarter tout ce qui figure
    dans l'intitulé retirait « E-commerce » d'une annonce intitulée
    « CHEF DE PROJETS PLATEFORME E-COMMERCE » — une compétence que le
    candidat prouve.

    Ce qui distingue le nom du poste d'une compétence citée dans le
    titre, c'est que le corps de l'annonce reparle de la seconde.
    """

    session = session_factory()
    session.close()

    retenues, ecartees = clean_required_skills(
        ["E-commerce"],
        job_title="CHEF DE PROJETS PLATEFORME E-COMMERCE H/F",
        job_description=(
            "Vous pilotez la plateforme e-commerce du groupe."
        ),
    )

    assert retenues == ["E-commerce"]
    assert ecartees == []


def test_une_technologie_du_titre_survit(session_factory):
    """
    Le cas qui condamnerait une règle plus large : « Développeur
    Python » nomme le poste par sa technologie, et Python reste une
    exigence.
    """

    session = session_factory()
    session.close()

    retenues, _ = clean_required_skills(
        ["Python"],
        job_title="Développeur Python H/F",
        job_description="Vous développerez en Python.",
    )

    assert retenues == ["Python"]


def test_sans_intitule_le_tri_ne_change_pas(session_factory):
    """
    Les appels qui ne fournissent pas l'annonce gardent exactement le
    comportement d'avant.
    """

    session = session_factory()
    session.close()

    retenues, ecartees = clean_required_skills(
        ["Product Owner", "Roadmap produit"]
    )

    assert retenues == ["Product Owner", "Roadmap produit"]
    assert ecartees == []


def test_le_bruit_de_page_web_ne_fait_pas_ecarter(session_factory):
    """
    Les titres enregistrés depuis un lien portent le nom du site et
    du recruteur. clean_job_title les coupe avant comparaison, sinon
    « LinkedIn » ou le nom de l'entreprise écarteraient des exigences
    au hasard.
    """

    session = session_factory()
    session.close()

    retenues, ecartees = clean_required_skills(
        ["Marketing digital"],
        job_title=(
            "Anonyme hiring Chef de Projet Marketing digital in "
            "Paris | LinkedIn"
        ),
        job_description="Une annonce qui n'en reparle pas.",
    )

    # « Marketing digital » figure dans le titre de page, mais
    # l'intitulé nettoyé s'arrête avant « in Paris ».
    assert ecartees == ["Marketing digital"]
    assert retenues == []

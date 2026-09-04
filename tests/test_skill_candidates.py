"""
Apprentissage du référentiel (services.skill_candidate_service).

Le référentiel livré ne couvre que les métiers que son auteur a
prévus. Ces tests verrouillent la boucle qui lui permet de grandir :
un terme d'annonce inconnu est enregistré, compté, puis **l'utilisateur
décide** — intégrer, rattacher, ou ignorer.

Rien n'est décidé automatiquement : créer une compétence, c'est
affirmer qu'un terme en désigne une.
"""

from __future__ import annotations

import pytest

from conftest import add_catalog_skill
from services.skill_candidate_service import (
    IGNORE,
    INTEGRE,
    RATTACHE,
    attach_as_alias,
    get_candidates,
    ignore_candidate,
    promote_to_catalog,
    record_unknown_terms,
)
from services.skill_catalog_service import find_skill_by_name


@pytest.fixture
def catalogue(session_factory):
    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery", "Découverte produit"],
        skill_id="catalog-discovery",
    )

    session.close()


# ============================================================
# ENREGISTREMENT
# ============================================================

def test_un_terme_inconnu_est_enregistre(catalogue):
    record_unknown_terms(["Kubernetes"], job_offer_id="job-1")

    candidats = get_candidates()

    assert len(candidats) == 1
    assert candidats[0]["term"] == "Kubernetes"
    assert candidats[0]["occurrences"] == 1
    assert candidats[0]["job_offer_ids"] == ["job-1"]


def test_un_terme_deja_connu_du_referentiel_est_ignore(catalogue):
    """
    Inutile de proposer d'apprendre ce que le référentiel sait déjà.
    """

    record_unknown_terms(["Découverte produit"])

    assert get_candidates() == []


def test_un_terme_revu_incremente_son_compteur(catalogue):
    record_unknown_terms(["Kubernetes"], job_offer_id="job-1")
    record_unknown_terms(["kubernetes"], job_offer_id="job-2")

    candidat = get_candidates()[0]

    assert candidat["occurrences"] == 2
    assert candidat["job_offer_ids"] == ["job-1", "job-2"]


def test_les_termes_sont_tries_par_frequence(catalogue):
    record_unknown_terms(["Rare"])
    record_unknown_terms(["Fréquent"])
    record_unknown_terms(["Fréquent"])
    record_unknown_terms(["Fréquent"])

    assert [item["term"] for item in get_candidates()] == [
        "Fréquent",
        "Rare",
    ]


def test_un_terme_ecarte_est_enregistre_comme_tel(catalogue):
    """
    Le tri des exigences se trompe parfois : l'utilisateur doit
    pouvoir rattraper un mot écarté à tort.
    """

    record_unknown_terms(["mobile"], was_counted=False)

    assert get_candidates()[0]["was_counted"] is False


# ============================================================
# DECISIONS DE L'UTILISATEUR
# ============================================================

def test_un_terme_peut_devenir_une_competence(catalogue):
    record_unknown_terms(["Kubernetes"])

    identifiant = promote_to_catalog(
        get_candidates()[0]["id"], category="Technology"
    )

    competence = find_skill_by_name("Kubernetes")

    assert competence is not None
    assert competence.id == identifiant
    assert competence.category == "Technology"


def test_un_terme_promu_peut_etre_renomme(catalogue):
    """
    L'annonce écrit « K8s » ; la compétence mérite un nom lisible.
    Les deux doivent rester reconnus.
    """

    record_unknown_terms(["K8s"])

    promote_to_catalog(
        get_candidates()[0]["id"], canonical_name="Kubernetes"
    )

    assert find_skill_by_name("Kubernetes") is not None
    assert find_skill_by_name("K8s") is not None


def test_un_terme_peut_etre_rattache_a_une_competence_existante(
    catalogue,
):
    """
    Le cas le plus fréquent : l'annonce nomme autrement quelque chose
    que le référentiel connaît déjà.
    """

    record_unknown_terms(["Discovery phase"])

    attach_as_alias(
        get_candidates()[0]["id"], "catalog-discovery"
    )

    competence = find_skill_by_name("Discovery phase")

    assert competence is not None
    assert competence.canonical_name == "Product Discovery"


def test_un_terme_peut_etre_ignore(catalogue):
    record_unknown_terms(["mobile"])

    ignore_candidate(get_candidates()[0]["id"])

    assert get_candidates() == []
    assert get_candidates(only_pending=False)[0]["status"] == IGNORE


@pytest.mark.parametrize(
    ("action", "statut"),
    [("promote", INTEGRE), ("attach", RATTACHE)],
)
def test_un_terme_traite_ne_revient_plus_dans_la_liste(
    catalogue, action, statut
):
    record_unknown_terms(["Discovery phase"])

    identifiant = get_candidates()[0]["id"]

    if action == "promote":
        promote_to_catalog(identifiant)
    else:
        attach_as_alias(identifiant, "catalog-discovery")

    assert get_candidates() == []
    assert (
        get_candidates(only_pending=False)[0]["status"] == statut
    )


def test_la_decision_de_l_utilisateur_tient_si_le_terme_revient(
    catalogue,
):
    """
    Réanalyser une annonce ne doit pas ressusciter un terme déjà
    écarté par l'utilisateur.
    """

    record_unknown_terms(["mobile"])
    ignore_candidate(get_candidates()[0]["id"])

    record_unknown_terms(["mobile"])

    assert get_candidates() == []
    assert get_candidates(only_pending=False)[0]["occurrences"] == 2


# ============================================================
# GARDE-FOU
# ============================================================

def test_promouvoir_un_nom_deja_pris_est_refuse(catalogue):
    """
    Un alias appartient à une seule compétence : créer un doublon
    rattacherait silencieusement une compétence du Master CV à la
    mauvaise entrée.
    """

    record_unknown_terms(["Kubernetes"])

    with pytest.raises(ValueError, match="Product Discovery"):
        promote_to_catalog(
            get_candidates()[0]["id"],
            canonical_name="Découverte produit",
        )


def test_promouvoir_sans_nom_est_refuse(catalogue):
    record_unknown_terms(["Kubernetes"])

    with pytest.raises(ValueError):
        promote_to_catalog(
            get_candidates()[0]["id"], canonical_name="   "
        )


def test_rattacher_a_une_competence_inexistante_est_refuse(catalogue):
    record_unknown_terms(["Kubernetes"])

    with pytest.raises(ValueError, match="introuvable"):
        attach_as_alias(get_candidates()[0]["id"], "catalog-fantome")

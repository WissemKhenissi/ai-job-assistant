"""
Proposition d'entrée de référentiel (services.ai.skill_proposal).

Aucun test n'appelle la vraie API : generate_text est remplacé dans le
module, comme partout ailleurs dans le projet.

Ce qui est vérifié n'est pas la qualité de la proposition — elle
dépend du modèle — mais ce que le code en fait : une proposition n'est
qu'un formulaire pré-rempli, et tout ce qui la rendrait dangereuse est
écarté avant même d'être affiché.
"""

from __future__ import annotations

import json

import pytest

import services.ai.skill_proposal as proposal
from conftest import add_catalog_skill


@pytest.fixture
def catalogue(session_factory):
    session = session_factory()

    add_catalog_skill(
        session,
        canonical_name="Product Discovery",
        aliases=["Product Discovery", "Découverte produit"],
        skill_id="catalog-discovery",
        category="Product",
    )
    add_catalog_skill(
        session,
        canonical_name="SQL",
        aliases=["SQL", "Requêtes SQL"],
        skill_id="catalog-sql",
        category="Data",
    )

    session.close()


def _repondre(monkeypatch, charge: dict | str):
    """Fait répondre l'IA avec cette charge utile."""

    texte = (
        charge if isinstance(charge, str)
        else json.dumps(charge, ensure_ascii=False)
    )

    monkeypatch.setattr(proposal, "is_configured", lambda: True)
    monkeypatch.setattr(
        proposal, "generate_text", lambda *a, **k: texte
    )


# ============================================================
# NOUVELLE COMPETENCE
# ============================================================

def test_une_competence_nouvelle_est_proposee(catalogue, monkeypatch):
    _repondre(
        monkeypatch,
        {
            "canonical_name": "Kubernetes",
            "category": "Technology",
            "description": "Orchestration de conteneurs.",
            "aliases": ["Kubernetes", "K8s"],
            "reasoning": "Terme technique absent du référentiel.",
        },
    )

    resultat = proposal.propose_catalog_entry("K8s")

    assert resultat.canonical_name == "Kubernetes"
    assert resultat.category == "Technology"
    assert "K8s" in resultat.aliases
    assert resultat.reasoning


def test_le_terme_d_origine_est_toujours_parmi_les_alias(
    catalogue, monkeypatch
):
    """
    Sans lui, l'annonce qui emploie ce mot resterait incomprise —
    la création n'aurait servi à rien.
    """

    _repondre(
        monkeypatch,
        {
            "canonical_name": "Kubernetes",
            "category": "Technology",
            "aliases": ["Kubernetes", "Container orchestration"],
        },
    )

    resultat = proposal.propose_catalog_entry("K8s")

    assert "K8s" in resultat.aliases


# ============================================================
# RATTACHEMENT
# ============================================================

def test_un_synonyme_est_proposé_en_rattachement(
    catalogue, monkeypatch
):
    _repondre(
        monkeypatch,
        {
            "attach_to": "Product Discovery",
            "reasoning": "Autre nom de la même pratique.",
        },
    )

    resultat = proposal.propose_catalog_entry("Discovery phase")

    assert resultat.attach_to_id == "catalog-discovery"
    assert resultat.attach_to_name == "Product Discovery"
    assert not resultat.canonical_name


def test_un_rattachement_vers_une_competence_inexistante_est_ecarte(
    catalogue, monkeypatch
):
    """
    Le modèle invente parfois une cible : sans ce contrôle,
    l'interface proposerait un bouton qui échouerait.
    """

    _repondre(monkeypatch, {"attach_to": "Compétence imaginaire"})

    resultat = proposal.propose_catalog_entry("Discovery phase")

    assert resultat.attach_to_id == ""
    assert "ne figure pas au référentiel" in resultat.warning


# ============================================================
# GARDE-FOUS SUR LES ALIAS
# ============================================================

def test_un_alias_appartenant_a_une_autre_competence_est_retire(
    catalogue, monkeypatch
):
    """
    Un alias n'appartient qu'à une compétence : le laisser passer
    rattacherait une compétence du Master CV à la mauvaise entrée.
    """

    _repondre(
        monkeypatch,
        {
            "canonical_name": "PostgreSQL",
            "category": "Data",
            "aliases": ["PostgreSQL", "Requêtes SQL", "Postgres"],
        },
    )

    resultat = proposal.propose_catalog_entry("Postgres")

    assert "Requêtes SQL" not in resultat.aliases
    assert "Postgres" in resultat.aliases
    assert "Requêtes SQL" in resultat.warning


def test_un_nom_deja_pris_fait_echouer_la_proposition(
    catalogue, monkeypatch
):
    _repondre(
        monkeypatch,
        {
            "canonical_name": "Découverte produit",
            "category": "Product",
            "aliases": ["Découverte produit"],
        },
    )

    resultat = proposal.propose_catalog_entry("Discovery phase")

    assert not resultat.canonical_name
    assert "Product Discovery" in resultat.warning


# ============================================================
# TERME QUI N'EST PAS UNE COMPETENCE
# ============================================================

def test_un_mot_generique_est_signale_comme_tel(
    catalogue, monkeypatch
):
    _repondre(
        monkeypatch,
        {
            "not_a_skill": True,
            "reasoning": "« mobile » est un support, pas une compétence.",
        },
    )

    resultat = proposal.propose_catalog_entry("mobile")

    assert resultat.is_empty
    assert "ne désigne pas une compétence" in resultat.warning
    assert resultat.reasoning


# ============================================================
# ECHECS
# ============================================================

def test_sans_cle_la_proposition_est_indisponible(
    catalogue, monkeypatch
):
    monkeypatch.setattr(proposal, "is_configured", lambda: False)

    resultat = proposal.propose_catalog_entry("K8s")

    assert resultat.is_empty
    assert "GEMINI_API_KEY" in resultat.warning


def test_une_reponse_illisible_ne_casse_rien(catalogue, monkeypatch):
    _repondre(monkeypatch, "ceci n'est pas du JSON")

    resultat = proposal.propose_catalog_entry("K8s")

    assert resultat.is_empty
    assert resultat.warning


@pytest.mark.parametrize(
    "enrobage",
    [
        'Voici ma réponse :\n{"canonical_name": "Kubernetes"}',
        '```json\n{"canonical_name": "Kubernetes"}\n```',
        '{"canonical_name": "Kubernetes"}\nJ\'espère que cela aide.',
    ],
)
def test_un_json_entoure_de_texte_reste_lisible(
    catalogue, monkeypatch, enrobage
):
    """
    Le modèle respecte la consigne « uniquement du JSON » la plupart
    du temps, mais pas toujours — observé une fois sur quinze en
    usage réel.
    """

    _repondre(monkeypatch, enrobage)

    resultat = proposal.propose_catalog_entry("K8s")

    assert resultat.canonical_name == "Kubernetes"


def test_une_erreur_api_ne_casse_rien(catalogue, monkeypatch):
    from services.ai.gemini_client import GeminiRequestError

    monkeypatch.setattr(proposal, "is_configured", lambda: True)

    def _echoue(*args, **kwargs):
        raise GeminiRequestError("quota dépassé")

    monkeypatch.setattr(proposal, "generate_text", _echoue)

    resultat = proposal.propose_catalog_entry("K8s")

    assert resultat.is_empty
    assert "quota" in resultat.warning


def test_un_terme_vide_n_appelle_pas_l_api(catalogue, monkeypatch):
    appele = False

    def _generate_text(*args, **kwargs):
        nonlocal appele
        appele = True
        return "{}"

    monkeypatch.setattr(proposal, "is_configured", lambda: True)
    monkeypatch.setattr(proposal, "generate_text", _generate_text)

    resultat = proposal.propose_catalog_entry("   ")

    assert resultat.is_empty
    assert not appele


# ============================================================
# CONTEXTE
# ============================================================

def test_l_extrait_de_l_annonce_est_transmis(catalogue, monkeypatch):
    """
    Un sigle n'a pas le même sens partout : sans contexte, la
    proposition serait un pari.
    """

    prompts: list[str] = []

    def _generate_text(prompt, *args, **kwargs):
        prompts.append(prompt)
        return json.dumps({"canonical_name": "Customer Data Platform"})

    monkeypatch.setattr(proposal, "is_configured", lambda: True)
    monkeypatch.setattr(proposal, "generate_text", _generate_text)

    proposal.propose_catalog_entry(
        "CDP", context="Vous piloterez notre CDP marketing."
    )

    assert "CDP marketing" in prompts[0]
    assert "Product Discovery" in prompts[0]

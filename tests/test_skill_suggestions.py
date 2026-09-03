"""
Suggestions de compétences attendues pour un poste
(services.ai.skill_suggestions).

Aucun appel réseau : is_configured/generate_text sont remplacés dans
le module, comme pour les autres tests services.ai.*.
"""

from __future__ import annotations

import json

import services.ai.skill_suggestions as suggestions


def test_sans_poste_aucune_suggestion(monkeypatch):
    monkeypatch.setattr(suggestions, "is_configured", lambda: True)

    resultat, avertissement = suggestions.suggest_skills_for_role("   ")

    assert resultat == []
    assert "poste" in avertissement.lower()


def test_sans_cle_configuree(monkeypatch):
    monkeypatch.setattr(suggestions, "is_configured", lambda: False)

    resultat, avertissement = suggestions.suggest_skills_for_role(
        "Product Owner"
    )

    assert resultat == []
    assert "GEMINI_API_KEY" in avertissement


def test_des_suggestions_valides_sont_retournees(monkeypatch):
    monkeypatch.setattr(suggestions, "is_configured", lambda: True)
    monkeypatch.setattr(
        suggestions,
        "generate_text",
        lambda *a, **k: json.dumps(
            ["Product Discovery", "Roadmap produit", "Agile / Scrum"]
        ),
    )

    resultat, avertissement = suggestions.suggest_skills_for_role(
        "Product Owner"
    )

    assert resultat == [
        "Product Discovery",
        "Roadmap produit",
        "Agile / Scrum",
    ]
    assert avertissement == ""


def test_les_competences_deja_declarees_sont_filtrees(monkeypatch):
    """
    Le prompt demande d'exclure l'existant, mais rien ne garantit
    qu'il soit suivi : le filtre côté code évite de proposer au
    candidat ce qu'il possède déjà.
    """

    monkeypatch.setattr(suggestions, "is_configured", lambda: True)
    monkeypatch.setattr(
        suggestions,
        "generate_text",
        lambda *a, **k: json.dumps(
            ["Product Discovery", "Roadmap produit"]
        ),
    )

    resultat, _avertissement = suggestions.suggest_skills_for_role(
        "Product Owner",
        existing=["product discovery"],
    )

    assert resultat == ["Roadmap produit"]


def test_les_doublons_internes_sont_ecartes(monkeypatch):
    monkeypatch.setattr(suggestions, "is_configured", lambda: True)
    monkeypatch.setattr(
        suggestions,
        "generate_text",
        lambda *a, **k: json.dumps(
            ["Roadmap produit", "roadmap produit", "Priorisation"]
        ),
    )

    resultat, _avertissement = suggestions.suggest_skills_for_role(
        "Product Owner"
    )

    assert resultat == ["Roadmap produit", "Priorisation"]


def test_une_reponse_avec_balisage_markdown_est_nettoyee(monkeypatch):
    monkeypatch.setattr(suggestions, "is_configured", lambda: True)
    monkeypatch.setattr(
        suggestions,
        "generate_text",
        lambda *a, **k: '```json\n["Priorisation"]\n```',
    )

    resultat, _avertissement = suggestions.suggest_skills_for_role(
        "Product Owner"
    )

    assert resultat == ["Priorisation"]


def test_une_reponse_illisible_est_signalee(monkeypatch):
    monkeypatch.setattr(suggestions, "is_configured", lambda: True)
    monkeypatch.setattr(
        suggestions, "generate_text", lambda *a, **k: "pas du JSON"
    )

    resultat, avertissement = suggestions.suggest_skills_for_role(
        "Product Owner"
    )

    assert resultat == []
    assert avertissement


def test_une_erreur_api_est_signalee(monkeypatch):
    from services.ai.gemini_client import GeminiRequestError

    monkeypatch.setattr(suggestions, "is_configured", lambda: True)

    def _generate_text(*args, **kwargs):
        raise GeminiRequestError("quota dépassé")

    monkeypatch.setattr(suggestions, "generate_text", _generate_text)

    resultat, avertissement = suggestions.suggest_skills_for_role(
        "Product Owner"
    )

    assert resultat == []
    assert "quota dépassé" in avertissement

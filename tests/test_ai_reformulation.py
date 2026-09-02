"""
Reformulation IA (Gemini) du CV et de la lettre.

Aucun test ici n'appelle la vraie API : services.ai.reformulation
importe generate_text/is_configured par leur nom, donc on les
remplace directement dans le module (comme pour
find_semantic_skill_matches dans test_matching_status.py).

Ce qui est vérifié n'est pas la qualité de la reformulation — on ne
peut pas la tester sans clé réelle — mais les garde-fous : ce que le
code fait quand l'IA n'est pas configurée, échoue, ou invente un
chiffre. C'est là que se joue le principe "rien n'est inventé"
appliqué à l'IA.
"""

from __future__ import annotations

from datetime import date

import pytest

import services.ai.reformulation as reformulation
from services.ai.gemini_client import GeminiNotConfiguredError, GeminiRequestError
from services.cv.results import CVEvidenceLine, CVExperience, TargetedCV
from services.letter.results import CoverLetter, LetterParagraph


JOB_TEXT = "Nous cherchons un profil produit avec de l'expérience e-commerce."


# ============================================================
# GARDE-FOUS DE _safe_reformulate
# ============================================================

def test_un_texte_vide_n_appelle_pas_l_api(monkeypatch):
    """Rien à reformuler : pas d'appel réseau pour rien."""

    appele = False

    def _generate_text(*args, **kwargs):
        nonlocal appele
        appele = True
        return "peu importe"

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)
    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    resultat = reformulation._safe_reformulate("   ", "instructions")

    assert resultat.text == "   "
    assert resultat.was_reformulated is False
    assert not appele


def test_sans_cle_configuree_le_texte_source_est_conserve(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: False)

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets.",
        "instructions",
    )

    assert resultat.text == "Pilotage de projets."
    assert resultat.was_reformulated is False
    assert "GEMINI_API_KEY" in resultat.warning


@pytest.mark.parametrize(
    "erreur",
    [
        GeminiNotConfiguredError("pas de clé"),
        GeminiRequestError("quota dépassé"),
    ],
)
def test_une_erreur_api_fait_replier_sur_le_texte_source(
    monkeypatch,
    erreur,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    def _generate_text(*args, **kwargs):
        raise erreur

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets.",
        "instructions",
    )

    assert resultat.text == "Pilotage de projets."
    assert resultat.was_reformulated is False
    assert resultat.warning


def test_une_reformulation_sans_nouveau_chiffre_est_acceptee(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Pilotage de projets digitaux à fort enjeu.",
    )

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets.",
        "instructions",
    )

    assert resultat.text == "Pilotage de projets digitaux à fort enjeu."
    assert resultat.was_reformulated is True
    assert resultat.warning == ""


def test_un_chiffre_invente_fait_rejeter_la_reformulation(
    monkeypatch,
):
    """
    Le garde-fou central : si l'IA introduit un chiffre absent du
    texte source (un pourcentage, une durée, un montant inventé),
    la reformulation est rejetée et le texte déterministe est gardé.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Marge publicitaire portée à 40 % de croissance.",
    )

    resultat = reformulation._safe_reformulate(
        "Marge publicitaire passée de 1,4 M€ à 2,5 M€.",
        "instructions",
    )

    assert resultat.text == "Marge publicitaire passée de 1,4 M€ à 2,5 M€."
    assert resultat.was_reformulated is False
    assert "40" in resultat.warning


def test_un_chiffre_deja_present_ne_declenche_pas_le_garde_fou(
    monkeypatch,
):
    """
    Réutiliser un chiffre déjà présent dans le texte source (même
    reformulé autour) ne doit pas être pris pour une invention.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: (
            "Une marge portée de 1,4 M€ à 2,5 M€, soit une forte "
            "progression."
        ),
    )

    resultat = reformulation._safe_reformulate(
        "Marge publicitaire passée de 1,4 M€ à 2,5 M€.",
        "instructions",
    )

    assert resultat.was_reformulated is True


# ============================================================
# LETTRE DE MOTIVATION
# ============================================================

def _lettre_de_test() -> CoverLetter:
    return CoverLetter(
        candidate_id="candidate-test",
        full_name="Wissem Khenissi",
        email="test@example.com",
        phone="",
        location="",
        job_offer_id="job-test",
        job_offer_title="Product Owner",
        company="",
        redaction_date=date(2026, 9, 2),
        objet="Objet : candidature au poste de Product Owner",
        salutation="Madame, Monsieur,",
        paragraphs=[
            LetterParagraph(
                text="Votre annonce a retenu mon attention.",
                sources=(),
            ),
            LetterParagraph(
                text="Je documente concrètement Product Discovery.",
                sources=("evidence-1",),
            ),
        ],
        closing="Je vous remercie de votre attention.",
        signature="Wissem Khenissi",
    )


def test_reformulate_cover_letter_ne_touche_pas_aux_formules_fixes(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: False)

    lettre = _lettre_de_test()

    lettre_reformulee, _avertissements = (
        reformulation.reformulate_cover_letter(lettre, JOB_TEXT)
    )

    assert lettre_reformulee.objet == lettre.objet
    assert lettre_reformulee.salutation == lettre.salutation
    assert lettre_reformulee.closing == lettre.closing
    assert lettre_reformulee.signature == lettre.signature


def test_reformulate_cover_letter_preserve_les_sources(monkeypatch):
    """
    Le texte peut changer, les identifiants de preuve qui justifient
    chaque paragraphe ne doivent jamais bouger : c'est la traçabilité
    du document.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Un texte reformulé, sans nouveau chiffre.",
    )

    lettre = _lettre_de_test()

    lettre_reformulee, _avertissements = (
        reformulation.reformulate_cover_letter(lettre, JOB_TEXT)
    )

    sources_avant = [p.sources for p in lettre.paragraphs]
    sources_apres = [p.sources for p in lettre_reformulee.paragraphs]

    assert sources_avant == sources_apres


def test_reformulate_cover_letter_sans_cle_remonte_les_avertissements(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: False)

    lettre = _lettre_de_test()

    _lettre_reformulee, avertissements = (
        reformulation.reformulate_cover_letter(lettre, JOB_TEXT)
    )

    # Un avertissement par paragraphe non vide.
    assert len(avertissements) == len(lettre.paragraphs)


def test_reformulate_cover_letter_redemande_toujours_validation(
    monkeypatch,
):
    """
    Une lettre reformulée n'est jamais validée d'office : c'est le
    même principe que pour la lettre déterministe.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Texte reformulé sans chiffre.",
    )

    lettre = _lettre_de_test()
    lettre.validated_by_user = True  # même si déjà validée avant...

    lettre_reformulee, _ = reformulation.reformulate_cover_letter(
        lettre, JOB_TEXT
    )

    assert lettre_reformulee.validated_by_user is False


# ============================================================
# CV CIBLE
# ============================================================

def _cv_de_test() -> TargetedCV:
    return TargetedCV(
        candidate_id="candidate-test",
        full_name="Wissem Khenissi",
        email="test@example.com",
        phone="",
        location="",
        linkedin_url="",
        summary="",
        job_offer_id="job-test",
        job_offer_title="Product Owner",
        skills=["Product Discovery"],
        experiences=[
            CVExperience(
                experience_id="experience-test",
                job_title="Chef de projet",
                company="Groupe Meridiem",
                location="Ivry-sur-Seine",
                start_date=date(2018, 1, 1),
                end_date=date(2024, 12, 31),
                business_context="",
                lines=[
                    CVEvidenceLine(
                        text="Conception de produits digitaux.",
                        skill="Product Discovery",
                        evidence_id="evidence-1",
                    )
                ],
            )
        ],
    )


def test_reformulate_targeted_cv_preserve_skill_et_evidence_id(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception de produits digitaux à fort trafic.",
    )

    cv = _cv_de_test()

    cv_reformule, _avertissements = (
        reformulation.reformulate_targeted_cv(cv, JOB_TEXT)
    )

    ligne = cv_reformule.experiences[0].lines[0]

    assert ligne.text == "Conception de produits digitaux à fort trafic."
    assert ligne.skill == "Product Discovery"
    assert ligne.evidence_id == "evidence-1"


def test_reformulate_targeted_cv_rejette_un_chiffre_invente(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception ayant généré 25 % de trafic en plus.",
    )

    cv = _cv_de_test()

    cv_reformule, avertissements = (
        reformulation.reformulate_targeted_cv(cv, JOB_TEXT)
    )

    ligne = cv_reformule.experiences[0].lines[0]

    assert ligne.text == "Conception de produits digitaux."
    assert avertissements

"""
Lettre de motivation rédigée par l'IA (services.ai.letter_authoring).

Aucun test ici n'appelle la vraie API : is_configured/generate_text
sont remplacés directement dans le module, comme pour
test_ai_reformulation.py. Ce qui est vérifié : le repli déterministe
dans tous les cas d'échec, le garde-fou anti-invention appliqué à
l'ensemble de la fiche de faits (pas seulement à un paragraphe), et
que la fiche de faits transmise au prompt contient bien les
motivations du candidat quand elles existent.
"""

from __future__ import annotations

import services.ai.letter_authoring as letter_authoring
from services.ai.gemini_client import GeminiRequestError
from services.profile_service import update_candidate

from test_letter_generation import CANDIDATE_ID, JOB_OFFER_ID, _analyser, _prepare


LETTRE_IA_VALIDE = (
    "Votre annonce pour le poste de Product Owner a retenu mon "
    "attention.\n\n"
    "Mon expérience en conception de produits digitaux répond "
    "directement à ce que vous recherchez.\n\n"
    "Je serais heureux d'échanger avec vous sur cette candidature."
)


def _preparer_offre_analysee(session_factory, **kwargs):
    session = session_factory()
    _prepare(session, **kwargs)
    session.close()

    _analyser(["Product Discovery"])


# ============================================================
# REPLI DETERMINISTE
# ============================================================

def test_sans_cle_configuree_la_lettre_deterministe_est_utilisee(
    session_factory, monkeypatch
):
    _preparer_offre_analysee(session_factory)

    from services.letter import build_cover_letter

    lettre_attendue = build_cover_letter(CANDIDATE_ID, JOB_OFFER_ID)

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: False)

    lettre, avertissements = letter_authoring.build_ai_letter(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert lettre.full_text == lettre_attendue.full_text
    assert "GEMINI_API_KEY" in avertissements[0]


def test_une_erreur_api_fait_replier_sur_la_lettre_deterministe(
    session_factory, monkeypatch
):
    _preparer_offre_analysee(session_factory)

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)

    def _generate_text(*args, **kwargs):
        raise GeminiRequestError("quota dépassé")

    monkeypatch.setattr(letter_authoring, "generate_text", _generate_text)

    lettre, avertissements = letter_authoring.build_ai_letter(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert lettre.validated_by_user is False
    assert avertissements
    assert "quota dépassé" in avertissements[0]


def test_une_reponse_vide_fait_replier_sur_la_lettre_deterministe(
    session_factory, monkeypatch
):
    _preparer_offre_analysee(session_factory)

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)
    monkeypatch.setattr(
        letter_authoring, "generate_text", lambda *a, **k: "   "
    )

    lettre, avertissements = letter_authoring.build_ai_letter(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert avertissements
    assert "vide" in avertissements[0]


def test_un_chiffre_invente_fait_rejeter_la_lettre_ia(
    session_factory, monkeypatch
):
    """
    Garde-fou central : un chiffre absent de la fiche de faits entière
    (Master CV + motivations + offre) fait rejeter la lettre IA.
    """

    _preparer_offre_analysee(session_factory)

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)
    monkeypatch.setattr(
        letter_authoring,
        "generate_text",
        lambda *a, **k: (
            "J'ai fait progresser le trafic de 42 % grâce à cette "
            "expérience."
        ),
    )

    lettre, avertissements = letter_authoring.build_ai_letter(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert avertissements
    assert "42" in avertissements[0]
    assert "42" not in lettre.full_text


# ============================================================
# LETTRE IA ACCEPTEE
# ============================================================

def test_une_lettre_ia_valide_est_utilisee(session_factory, monkeypatch):
    _preparer_offre_analysee(session_factory)

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)
    monkeypatch.setattr(
        letter_authoring, "generate_text", lambda *a, **k: LETTRE_IA_VALIDE
    )

    lettre, avertissements = letter_authoring.build_ai_letter(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert avertissements == []
    assert lettre.validated_by_user is False
    assert len(lettre.paragraphs) == 3
    assert "conception de produits digitaux" in lettre.full_text.lower()

    # Les formules fixes restent celles de la lettre déterministe.
    assert lettre.salutation == "Madame, Monsieur,"
    assert lettre.signature == "Test Candidat"


def test_un_chiffre_present_dans_l_offre_ne_declenche_pas_le_garde_fou(
    session_factory, monkeypatch
):
    """
    La fiche de faits inclut le texte complet de l'offre : un chiffre
    qui y figure déjà (ex. "5 ans d'expérience requis") n'est pas une
    invention s'il est repris.
    """

    session = session_factory()
    _prepare(session)
    session.close()

    from services.job_service import save_job_offer

    save_job_offer(
        job_offer_id=JOB_OFFER_ID,
        title="Product Owner",
        description="Poste nécessitant 5 ans d'expérience en produit.",
        company="Groupe Meridiem",
        status="selected",
    )

    _analyser(["Product Discovery"])

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)
    monkeypatch.setattr(
        letter_authoring,
        "generate_text",
        lambda *a, **k: (
            "Votre exigence de 5 ans d'expérience correspond à mon "
            "parcours.\n\nJe documente concrètement mes compétences "
            "produit.\n\nÉchangeons à ce sujet."
        ),
    )

    lettre, avertissements = letter_authoring.build_ai_letter(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert avertissements == []
    assert "5 ans" in lettre.full_text


# ============================================================
# FICHE DE FAITS
# ============================================================

def test_les_motivations_du_candidat_atteignent_le_prompt(
    session_factory, monkeypatch
):
    _preparer_offre_analysee(session_factory)

    update_candidate(
        CANDIDATE_ID,
        motivations=(
            "En reconversion vers le produit digital après plusieurs "
            "années en gestion de projet."
        ),
    )

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)

    prompts_recus = []

    def _generate_text(prompt, *args, **kwargs):
        prompts_recus.append(prompt)
        return LETTRE_IA_VALIDE

    monkeypatch.setattr(letter_authoring, "generate_text", _generate_text)

    letter_authoring.build_ai_letter(CANDIDATE_ID, JOB_OFFER_ID)

    assert prompts_recus
    assert "En reconversion vers le produit digital" in prompts_recus[0]


def test_sans_motivation_le_prompt_l_indique_explicitement(
    session_factory, monkeypatch
):
    """
    L'absence de motivation doit être un signal explicite pour l'IA
    ("n'invente rien"), pas une simple absence de section.
    """

    _preparer_offre_analysee(session_factory)

    monkeypatch.setattr(letter_authoring, "is_configured", lambda: True)

    prompts_recus = []

    def _generate_text(prompt, *args, **kwargs):
        prompts_recus.append(prompt)
        return LETTRE_IA_VALIDE

    monkeypatch.setattr(letter_authoring, "generate_text", _generate_text)

    letter_authoring.build_ai_letter(CANDIDATE_ID, JOB_OFFER_ID)

    assert "aucune information fournie par le candidat" in prompts_recus[0]

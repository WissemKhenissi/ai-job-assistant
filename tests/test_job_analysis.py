"""
Analyse d'offre par l'IA (services.ai.job_analysis) : catégorisation
(type de contrat, télétravail) et synthèse qualitative de
l'adéquation.

Aucun test n'appelle la vraie API : is_configured/generate_text sont
remplacés directement dans le module, comme pour
test_ai_reformulation.py et test_letter_authoring.py.
"""

from __future__ import annotations

import services.ai.job_analysis as job_analysis


JOB_TEXT = (
    "Product Owner Digital\n"
    "Nous recherchons un Product Owner avec au moins 5 ans "
    "d'expérience en e-commerce. Poste en CDI, 2 jours de "
    "télétravail par semaine. Compétences attendues : Product "
    "Discovery, Roadmap produit."
)


# ============================================================
# CATEGORISATION DE L'OFFRE
# ============================================================

def test_un_texte_vide_ne_retourne_rien(monkeypatch):
    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    resultat = job_analysis.analyze_job_offer_with_ai("   ")

    assert resultat.contract_type == ""
    assert resultat.required_skills == []


def test_sans_cle_configuree_retourne_un_avertissement(monkeypatch):
    monkeypatch.setattr(job_analysis, "is_configured", lambda: False)

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.contract_type == ""
    assert "GEMINI_API_KEY" in resultat.warning


def test_une_reponse_json_valide_est_acceptee(monkeypatch):
    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "CDI", "remote_policy": "Hybride", '
            '"remote_details": "2 jours de télétravail par semaine", '
            '"required_skills": ["Product Discovery", "Roadmap produit"]}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.contract_type == "CDI"
    assert resultat.remote_policy == "Hybride"
    assert resultat.remote_details == "2 jours de télétravail par semaine"
    assert "Product Discovery" in resultat.required_skills
    assert resultat.warning == ""


def test_une_reponse_avec_balisage_markdown_est_nettoyee(
    monkeypatch,
):
    """Gemini enveloppe parfois sa réponse dans ```json ... ``` malgré la consigne."""

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '```json\n{"contract_type": "CDI", "remote_policy": "", '
            '"remote_details": "", "required_skills": []}\n```'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.contract_type == "CDI"


def test_une_valeur_hors_liste_est_ignoree(monkeypatch):
    """contract_type/remote_policy doivent être une valeur autorisée, ou vide."""

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "Intérim", "remote_policy": "Nomade", '
            '"remote_details": "", "required_skills": []}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.contract_type == ""
    assert resultat.remote_policy == ""


def test_une_reponse_illisible_est_rejetee(monkeypatch):
    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)
    monkeypatch.setattr(
        job_analysis, "generate_text", lambda *a, **k: "pas du JSON"
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.contract_type == ""
    assert resultat.warning


def test_une_competence_absente_du_texte_est_filtree(monkeypatch):
    """
    Garde-fou central : une compétence extraite par l'IA mais absente
    du texte source ne doit jamais être conservée — c'est le
    principe anti-invention appliqué à l'extraction.
    """

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "", "remote_policy": "", '
            '"remote_details": "", "required_skills": '
            '["Product Discovery", "Kubernetes"]}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert "Product Discovery" in resultat.required_skills
    assert "Kubernetes" not in resultat.required_skills


def test_un_nombre_de_jours_invente_est_ecarte(monkeypatch):
    """
    Une précision de télétravail contenant un chiffre absent du
    texte source (un nombre de jours inventé) est écartée plutôt que
    conservée telle quelle.
    """

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "", "remote_policy": "", '
            '"remote_details": "4 jours de télétravail par semaine", '
            '"required_skills": []}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.remote_details == ""


def test_une_erreur_api_retourne_un_avertissement(monkeypatch):
    from services.ai.gemini_client import GeminiRequestError

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    def _generate_text(*args, **kwargs):
        raise GeminiRequestError("quota dépassé")

    monkeypatch.setattr(job_analysis, "generate_text", _generate_text)

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.contract_type == ""
    assert "quota dépassé" in resultat.warning


# ============================================================
# SYNTHESE QUALITATIVE
# ============================================================

def test_synthese_sans_cle_configuree(monkeypatch):
    monkeypatch.setattr(job_analysis, "is_configured", lambda: False)

    resultat = job_analysis.generate_fit_synthesis(
        "candidate-test", "job-test"
    )

    assert resultat.text == ""
    assert "GEMINI_API_KEY" in resultat.warning


def test_synthese_sans_analyse_prealable(session_factory, monkeypatch):
    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    resultat = job_analysis.generate_fit_synthesis(
        "candidate-inconnu", "job-inconnu"
    )

    assert resultat.text == ""
    assert "Analysez d'abord" in resultat.warning


def test_synthese_valide_est_acceptee(session_factory, monkeypatch):
    from test_letter_generation import CANDIDATE_ID, JOB_OFFER_ID, _analyser, _prepare

    session = session_factory()
    _prepare(session)
    session.close()

    _analyser(["Product Discovery"])

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)
    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            "Ce profil démontre une expérience directe en Product "
            "Discovery, un atout pour ce poste. Le reste du parcours "
            "reste à documenter plus précisément pour ce type "
            "d'offre."
        ),
    )

    resultat = job_analysis.generate_fit_synthesis(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert resultat.text
    assert resultat.warning == ""


def test_synthese_rejette_un_chiffre_invente(session_factory, monkeypatch):
    from test_letter_generation import CANDIDATE_ID, JOB_OFFER_ID, _analyser, _prepare

    session = session_factory()
    _prepare(session)
    session.close()

    _analyser(["Product Discovery"])

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)
    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            "Ce candidat possède 12 ans d'expérience directement "
            "pertinente pour ce poste."
        ),
    )

    resultat = job_analysis.generate_fit_synthesis(
        CANDIDATE_ID, JOB_OFFER_ID
    )

    assert resultat.text == ""
    assert "12" in resultat.warning


# ============================================================
# NIVEAU D'EXIGENCE PROPOSE PAR L'IA
# ============================================================
#
# L'IA lit le découpage en sections mieux qu'une recherche de
# marqueurs : elle sait distinguer « maîtrise indispensable » d'un
# « environnement : Jira, Miro ». Sa proposition reste une
# proposition — même garde-fou que pour le type de contrat.


def test_le_niveau_d_exigence_est_conserve(monkeypatch):

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "", "remote_policy": "", '
            '"remote_details": "", "required_skills": ['
            '{"skill": "Product Discovery", '
            '"importance": "essentielle"}, '
            '{"skill": "Roadmap produit", "importance": "mention"}]}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.required_skills == [
        "Product Discovery",
        "Roadmap produit",
    ]

    assert resultat.skill_importance == {
        "Product Discovery": "essentielle",
        "Roadmap produit": "mention",
    }


def test_un_niveau_hors_liste_est_ignore(monkeypatch):
    """
    Une valeur inventée n'est jamais réinterprétée : la compétence
    est gardée, son niveau non — le classement déterministe le
    recalculera depuis le texte de l'annonce.
    """

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "", "remote_policy": "", '
            '"remote_details": "", "required_skills": ['
            '{"skill": "Product Discovery", '
            '"importance": "critique"}]}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.required_skills == ["Product Discovery"]
    assert resultat.skill_importance == {}


def test_une_liste_de_chaines_reste_acceptee(monkeypatch):
    """
    Rétrocompatibilité : le modèle retourne encore parfois l'ancien
    format. Perdre le niveau est acceptable, perdre la compétence ne
    l'est pas.
    """

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "", "remote_policy": "", '
            '"remote_details": "", '
            '"required_skills": ["Product Discovery"]}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.required_skills == ["Product Discovery"]
    assert resultat.skill_importance == {}


def test_un_niveau_ne_sauve_pas_une_competence_absente(monkeypatch):
    """
    Le garde-fou anti-invention passe avant : une compétence qui ne
    figure pas dans l'annonce est écartée, quel que soit le niveau
    que l'IA lui attribue.
    """

    monkeypatch.setattr(job_analysis, "is_configured", lambda: True)

    monkeypatch.setattr(
        job_analysis,
        "generate_text",
        lambda *a, **k: (
            '{"contract_type": "", "remote_policy": "", '
            '"remote_details": "", "required_skills": ['
            '{"skill": "Kubernetes", "importance": "essentielle"}]}'
        ),
    )

    resultat = job_analysis.analyze_job_offer_with_ai(JOB_TEXT)

    assert resultat.required_skills == []
    assert resultat.skill_importance == {}

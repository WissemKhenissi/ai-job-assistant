"""
Lecture d'un CV (services.ai.profile_extraction).

Aucun test n'appelle la vraie API. Ce qui est vérifié n'est pas la
qualité de la lecture — elle dépend du modèle — mais les garde-fous :
ce que le code refuse d'accepter d'une IA qui interprète au lieu de
transcrire.

L'enjeu est plus lourd qu'ailleurs : ce que cette étape écrit devient
le Master CV, c'est-à-dire la source de vérité de tout le reste. Une
compétence inventée ici serait tenue pour vraie partout ensuite.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

import services.ai.profile_extraction as extraction


CV = """Camille Durand
camille.durand@example.com — 06 12 34 56 78 — Lyon
linkedin.com/in/camilledurand

Infirmière diplômée d'État, 8 ans en service de réanimation.

EXPÉRIENCE

Infirmière — CHU de Lyon — Lyon
2019-2025
Prise en charge de patients en réanimation polyvalente.
Encadrement de 4 étudiants infirmiers par semestre.

Infirmière — Clinique du Parc — Lyon
2017-2019
Surveillance post-opératoire en chirurgie ambulatoire.

COMPÉTENCES
Réanimation, Soins critiques, Encadrement, Dossier patient informatisé

FORMATION
Diplôme d'État d'infirmier — IFSI de Lyon — 2014-2017
"""


def _repondre(monkeypatch, charge):
    texte = (
        charge if isinstance(charge, str)
        else json.dumps(charge, ensure_ascii=False)
    )

    monkeypatch.setattr(extraction, "is_configured", lambda: True)
    monkeypatch.setattr(
        extraction, "generate_text", lambda *a, **k: texte
    )


def _profil_valide() -> dict:
    return {
        "first_name": "Camille",
        "last_name": "Durand",
        "email": "camille.durand@example.com",
        "location": "Lyon",
        "summary": "Infirmière diplômée d'État, 8 ans en service de réanimation.",
        "skills": ["Réanimation", "Soins critiques", "Encadrement"],
        "experiences": [
            {
                "company": "CHU de Lyon",
                "job_title": "Infirmière",
                "location": "Lyon",
                "start_date": "2019",
                "end_date": "2025",
                "lines": [
                    {
                        "text": "Prise en charge de patients en réanimation polyvalente.",
                        "skill": "Réanimation",
                    },
                    {
                        "text": "Encadrement de 4 étudiants infirmiers par semestre.",
                        "skill": "Encadrement",
                    },
                ],
            }
        ],
        "educations": [
            {
                "institution": "IFSI de Lyon",
                "degree": "Diplôme d'État d'infirmier",
                "start_year": 2014,
                "end_year": 2017,
            }
        ],
    }


# ============================================================
# LECTURE FIDELE
# ============================================================

def test_un_cv_est_transcrit(monkeypatch):
    """
    Le métier n'a rien à voir avec celui de l'auteur du référentiel :
    c'est le but.
    """

    _repondre(monkeypatch, _profil_valide())

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.first_name == "Camille"
    assert profil.email == "camille.durand@example.com"
    assert len(profil.experiences) == 1
    assert len(profil.experiences[0].lines) == 2
    assert "Réanimation" in profil.skills
    assert profil.educations[0].institution == "IFSI de Lyon"
    assert profil.warnings == ()


def test_les_dates_partielles_sont_completees(monkeypatch):
    _repondre(monkeypatch, _profil_valide())

    experience = extraction.extract_profile_from_cv(CV).experiences[0]

    assert experience.start_date == date(2019, 1, 1)
    assert experience.end_date == date(2025, 1, 1)


def test_un_poste_en_cours_n_a_pas_de_date_de_fin(monkeypatch):
    donnees = _profil_valide()
    donnees["experiences"][0]["end_date"] = ""

    _repondre(monkeypatch, donnees)

    assert (
        extraction.extract_profile_from_cv(CV)
        .experiences[0]
        .end_date
        is None
    )


# ============================================================
# GARDE-FOU : LA PUCE DOIT ETRE MOT POUR MOT
# ============================================================

def test_une_puce_reformulee_est_ecartee(monkeypatch):
    """
    Le CV est la source de vérité : une puce réécrite par l'IA n'y
    figure plus, et ce qu'elle affirme n'est plus vérifiable.
    """

    donnees = _profil_valide()
    donnees["experiences"][0]["lines"] = [
        {
            "text": "Pilotage de la prise en charge de patients critiques.",
            "skill": "Réanimation",
        }
    ]

    _repondre(monkeypatch, donnees)

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.experiences[0].lines == ()
    assert any("reformulées" in item for item in profil.warnings)


def test_une_puce_avec_un_chiffre_invente_est_ecartee(monkeypatch):
    donnees = _profil_valide()
    donnees["experiences"][0]["lines"] = [
        {"text": "Encadrement de 12 étudiants infirmiers par semestre."}
    ]

    _repondre(monkeypatch, donnees)

    assert extraction.extract_profile_from_cv(CV).experiences[0].lines == ()


def test_les_espaces_ne_font_pas_echouer_la_comparaison(monkeypatch):
    """
    L'extraction d'un PDF coupe les lignes n'importe où : comparer au
    caractère près rejetterait tout.
    """

    donnees = _profil_valide()
    donnees["experiences"][0]["lines"] = [
        {
            "text": "Prise en charge   de patients\nen réanimation polyvalente.",
            "skill": "Réanimation",
        }
    ]

    _repondre(monkeypatch, donnees)

    assert len(
        extraction.extract_profile_from_cv(CV).experiences[0].lines
    ) == 1


# ============================================================
# GARDE-FOU : COMPETENCES ET IDENTITE
# ============================================================

def test_une_competence_absente_du_cv_est_ecartee(monkeypatch):
    """
    Une compétence déduite du contexte n'est pas une déclaration du
    candidat.
    """

    donnees = _profil_valide()
    donnees["skills"] = ["Réanimation", "Gestion du stress"]

    _repondre(monkeypatch, donnees)

    profil = extraction.extract_profile_from_cv(CV)

    assert "Réanimation" in profil.skills
    assert "Gestion du stress" not in profil.skills
    assert any("écartées" in item for item in profil.warnings)


def test_un_email_invente_est_refuse(monkeypatch):
    """
    La pire erreur possible : un recruteur qui ne peut pas rappeler.
    """

    donnees = _profil_valide()
    donnees["email"] = "camille.durand@hopital-lyon.fr"

    _repondre(monkeypatch, donnees)

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.email == ""
    assert any("ne figure pas dans le CV" in i for i in profil.warnings)


def test_un_resume_avec_un_chiffre_invente_est_vide(monkeypatch):
    donnees = _profil_valide()
    donnees["summary"] = "Infirmière avec 15 ans d'expérience."

    _repondre(monkeypatch, donnees)

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.summary == ""
    assert any("Chiffre absent du CV" in i for i in profil.warnings)


def test_une_competence_de_puce_inconnue_est_deliee(monkeypatch):
    donnees = _profil_valide()
    donnees["experiences"][0]["lines"][0]["skill"] = "Télépathie"

    _repondre(monkeypatch, donnees)

    ligne = extraction.extract_profile_from_cv(CV).experiences[0].lines[0]

    assert ligne.skill == ""
    assert ligne.text


# ============================================================
# DATES INCOHERENTES
# ============================================================

def test_une_date_de_debut_future_est_signalee(monkeypatch):
    donnees = _profil_valide()
    donnees["experiences"][0]["start_date"] = "2099"

    _repondre(monkeypatch, donnees)

    profil = extraction.extract_profile_from_cv(
        CV, today=date(2026, 9, 4)
    )

    assert profil.experiences[0].start_date is None
    assert any("futur" in item for item in profil.warnings)


def test_une_fin_avant_le_debut_est_ignoree(monkeypatch):
    donnees = _profil_valide()
    donnees["experiences"][0]["end_date"] = "2015"

    _repondre(monkeypatch, donnees)

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.experiences[0].end_date is None
    assert any("précède le début" in item for item in profil.warnings)


# ============================================================
# ECHECS
# ============================================================

def test_un_texte_vide_n_appelle_pas_l_api(monkeypatch):
    appele = False

    def _generate_text(*args, **kwargs):
        nonlocal appele
        appele = True
        return "{}"

    monkeypatch.setattr(extraction, "is_configured", lambda: True)
    monkeypatch.setattr(extraction, "generate_text", _generate_text)

    profil = extraction.extract_profile_from_cv("   ")

    assert profil.is_empty
    assert not appele


def test_sans_cle_la_lecture_est_indisponible(monkeypatch):
    monkeypatch.setattr(extraction, "is_configured", lambda: False)

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.is_empty
    assert "GEMINI_API_KEY" in profil.warnings[0]


@pytest.mark.parametrize(
    "reponse",
    ["pas du JSON", "```json\n{invalide}\n```", "[]"],
)
def test_une_reponse_illisible_ne_casse_rien(monkeypatch, reponse):
    _repondre(monkeypatch, reponse)

    profil = extraction.extract_profile_from_cv(CV)

    assert profil.is_empty
    assert profil.warnings


def test_un_json_entoure_de_texte_reste_lisible(monkeypatch):
    _repondre(
        monkeypatch,
        "Voici le résultat :\n"
        + json.dumps(_profil_valide(), ensure_ascii=False),
    )

    assert extraction.extract_profile_from_cv(CV).first_name == "Camille"

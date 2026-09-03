"""
Contrainte d'une page (services.cv.fitting).

Les tests rendent de vrais PDF et comptent leurs pages : c'est tout
l'intérêt de la méthode, mesurer plutôt qu'estimer. Ils vérifient
aussi que l'élagage ne fait que **retirer** — un CV raccourci doit
rester exactement aussi vrai que le CV complet.
"""

from __future__ import annotations

from datetime import date

from services.cv.export import export_pdf
from services.cv.fitting import count_pdf_pages, fit_to_one_page
from services.cv.results import (
    CVEducation,
    CVEvidenceLine,
    CVExperience,
    CVSkillGroup,
    TargetedCV,
)


def _experience(indice: int, nb_lignes: int) -> CVExperience:
    return CVExperience(
        experience_id=f"experience-{indice}",
        job_title=f"Chef de projet {indice}",
        company=f"Entreprise {indice}",
        location="Paris",
        start_date=date(2000 + indice, 1, 1),
        end_date=date(2001 + indice, 1, 1),
        business_context="Contexte e-commerce et adtech." * 3,
        lines=[
            CVEvidenceLine(
                text=(
                    f"Réalisation {numero} de l'expérience {indice}, "
                    "décrite avec suffisamment de détail pour occuper "
                    "de la place sur la page."
                ),
                skill="Gestion de projet",
                evidence_id=f"evidence-{indice}-{numero}",
            )
            for numero in range(nb_lignes)
        ],
    )


def _cv(nb_experiences: int = 1, nb_lignes: int = 2) -> TargetedCV:
    return TargetedCV(
        candidate_id="candidate-test",
        full_name="Test Candidat",
        email="test@example.com",
        phone="0600000000",
        location="Paris",
        linkedin_url="",
        summary=(
            "Professionnel du digital avec une solide culture produit. "
            "Deuxième phrase du résumé, qui pourra être retirée. "
            "Troisième phrase, également superflue."
        ),
        headline="Chef de projet digital",
        languages="Français : natif | Anglais : B2",
        interests="Entrepreneuriat • IA",
        job_offer_id="job-test",
        job_offer_title="Product Owner",
        skills=["Gestion de projet"],
        skill_groups=[
            CVSkillGroup(category="Product", skills=("Gestion de projet",))
        ],
        experiences=[
            _experience(indice, nb_lignes) for indice in range(nb_experiences)
        ],
        educations=[
            CVEducation(
                institution="Lyon 2",
                degree="Master AEI",
                field_of_study="E-commerce",
                start_year=2015,
                end_year=2017,
            )
        ],
    )


# ============================================================
# MESURE
# ============================================================

def test_un_pdf_court_fait_une_page(tmp_path):
    chemin = tmp_path / "cv.pdf"
    export_pdf(_cv(), chemin)

    assert count_pdf_pages(chemin) == 1


def test_un_fichier_illisible_ne_fait_pas_planter_le_comptage(tmp_path):
    chemin = tmp_path / "pas-un.pdf"
    chemin.write_bytes(b"ceci n'est pas un pdf")

    assert count_pdf_pages(chemin) == 0


# ============================================================
# ELAGAGE
# ============================================================

def test_un_cv_qui_tient_deja_n_est_pas_touche():
    cv = _cv()

    ajuste, _sections, retraits, tient = fit_to_one_page(cv)

    assert tient
    assert retraits == []
    assert len(ajuste.experiences[0].lines) == len(cv.experiences[0].lines)


def test_un_cv_trop_long_est_ramene_a_une_page(tmp_path):
    """Le cœur de la fonctionnalité : mesurer, élaguer, re-mesurer."""

    cv = _cv(nb_experiences=6, nb_lignes=6)

    chemin_avant = tmp_path / "avant.pdf"
    export_pdf(cv, chemin_avant)
    assert count_pdf_pages(chemin_avant) > 1, "le cas de test doit déborder"

    ajuste, sections, retraits, tient = fit_to_one_page(cv)

    assert tient
    assert retraits

    chemin_apres = tmp_path / "apres.pdf"
    export_pdf(ajuste, chemin_apres, included_sections=sections)

    assert count_pdf_pages(chemin_apres) == 1


def test_l_elagage_ne_fait_que_retirer():
    """
    Aucune ligne conservée ne doit avoir été réécrite : un CV
    raccourci reste aussi vrai que le CV complet.
    """

    cv = _cv(nb_experiences=6, nb_lignes=6)

    textes_origine = {
        ligne.text
        for experience in cv.experiences
        for ligne in experience.lines
    }

    ajuste, _sections, _retraits, _tient = fit_to_one_page(cv)

    textes_restants = {
        ligne.text
        for experience in ajuste.experiences
        for ligne in experience.lines
    }

    assert textes_restants <= textes_origine


def test_aucune_experience_n_est_supprimee_entierement():
    """
    Un trou dans la chronologie appelle une question gênante en
    entretien : on réduit une expérience, on ne la fait pas
    disparaître.
    """

    cv = _cv(nb_experiences=6, nb_lignes=6)

    ajuste, _sections, _retraits, _tient = fit_to_one_page(cv)

    assert len(ajuste.experiences) == len(cv.experiences)
    assert all(
        len(experience.lines) >= 1 for experience in ajuste.experiences
    )


def test_le_cv_d_origine_n_est_jamais_modifie():
    cv = _cv(nb_experiences=6, nb_lignes=6)

    lignes_avant = len(cv.experiences[0].lines)
    resume_avant = cv.summary

    fit_to_one_page(cv)

    assert len(cv.experiences[0].lines) == lignes_avant
    assert cv.summary == resume_avant


def test_les_retraits_sont_annonces():
    cv = _cv(nb_experiences=6, nb_lignes=6)

    _ajuste, _sections, retraits, _tient = fit_to_one_page(cv)

    # Le premier sacrifice est le moins coûteux.
    assert retraits[0] == "centres d'intérêt"


def test_l_ordre_de_sacrifice_epargne_les_experiences_recentes():
    """
    Les lignes retirées viennent des expériences les plus anciennes :
    cv.experiences est trié du plus récent au plus ancien.
    """

    cv = _cv(nb_experiences=3, nb_lignes=6)

    ajuste, _sections, _retraits, _tient = fit_to_one_page(cv)

    lignes_recente = len(ajuste.experiences[0].lines)
    lignes_ancienne = len(ajuste.experiences[-1].lines)

    assert lignes_recente >= lignes_ancienne

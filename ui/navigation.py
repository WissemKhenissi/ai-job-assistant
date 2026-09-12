"""
Navigation de l'application.

Remplace un sélecteur de page en barre latérale doublé d'onglets
imbriqués : neuf destinations réparties sur deux niveaux, dont la
hiérarchie ne disait rien de leur importance. « Référentiel », une
tâche d'entretien qu'on ouvre de loin en loin, occupait le même rang
que « Nouvelle annonce », qui est l'action quotidienne ; et rien ne
reliait l'analyse d'une annonce à la génération qui la suit, alors que
c'est le même geste.

Les pages sont désormais à plat, groupées par intention :

    Mon profil   ce qu'on construit une fois, et qu'on enrichit
    Candidater   ce qu'on refait à chaque annonce, dans cet ordre
    Outils       ce qu'on entretient de temps en temps

Chaque page reçoit son candidat explicitement, par functools.partial.
Aucune ne le devine : c'est la règle posée avec le cloisonnement des
profils, et elle survit au changement de navigation.
"""

from __future__ import annotations

from functools import partial

import streamlit as st

from services.profile_service import get_skills
from ui.job_matching.analysis import render_analysis_tab
from ui.job_matching.generation import render_generation_tab
from ui.job_matching.market_memory import render_market_memory_tab
from ui.job_matching.referentiel import render_referentiel_tab
from ui.job_matching.tracking import render_tracking_tab
from ui.master_cv.experiences_section import render_experiences_section
from ui.master_cv.import_section import render_import_section
from ui.master_cv.interview_section import render_interview_section
from ui.master_cv.skills_section import render_skills_section
from ui.profile_page import render_profile_page


# ============================================================
# MON PROFIL
# ============================================================

def _page_profil(candidate, experiences) -> None:

    st.header("Profil", divider="blue")

    # En tête du profil : c'est la première chose dont un nouvel
    # utilisateur a besoin, et le repli s'ouvre de lui-même tant que
    # le parcours est vide.
    render_import_section(candidate.id, profil_vide=not experiences)

    render_profile_page(
        candidate,
        experiences_count=len(experiences),
        skills_count=len(get_skills(candidate.id)),
        experiences=experiences,
    )


def _page_experiences(experiences) -> None:

    st.header("Expériences", divider="blue")

    render_experiences_section(experiences)


def _page_competences(candidate_id: str) -> None:

    st.header("Compétences", divider="blue")

    render_skills_section(candidate_id)


def _page_entretien(candidate_id: str) -> None:

    st.header("Entretien IA", divider="blue")

    render_interview_section(candidate_id)


# ============================================================
# CANDIDATER
# ============================================================

def _page_analyse(candidate_id: str) -> None:

    st.header("Analyser une annonce", divider="blue")

    render_analysis_tab(candidate_id)


def _page_documents(candidate_id: str) -> None:

    st.header("CV & lettre", divider="blue")

    resultat = st.session_state.get("job_matching_result")

    if resultat is None:

        st.info(
            "Analysez d'abord une annonce dans « Analyser une "
            "annonce » pour générer un CV et une lettre."
        )

        return

    render_generation_tab(
        candidate_id=candidate_id,
        job_offer_id=resultat["job_offer_id"],
    )


def _page_suivi(candidate_id: str) -> None:

    st.header("Suivi des candidatures", divider="blue")

    render_tracking_tab(candidate_id)


# ============================================================
# OUTILS
# ============================================================

def _page_referentiel() -> None:

    st.header("Référentiel de compétences", divider="blue")

    render_referentiel_tab()


def _page_marche(candidate_id: str) -> None:

    st.header("Mémoire de marché", divider="blue")

    render_market_memory_tab(candidate_id)


# ============================================================
# ASSEMBLAGE
# ============================================================

def construire_navigation(candidate, experiences):
    """
    Les pages de l'application, groupées par intention.

    Retourne l'objet de navigation ; c'est à l'appelant de lancer la
    page choisie, une fois la barre latérale complétée.
    """

    pages = {
        "Mon profil": [
            st.Page(
                partial(_page_profil, candidate, experiences),
                title="Profil",
                icon="👤",
                url_path="profil",
                default=True,
            ),
            st.Page(
                partial(_page_experiences, experiences),
                title="Expériences",
                icon="💼",
                url_path="experiences",
            ),
            st.Page(
                partial(_page_competences, candidate.id),
                title="Compétences",
                icon="🧠",
                url_path="competences",
            ),
            st.Page(
                partial(_page_entretien, candidate.id),
                title="Entretien IA",
                icon="🎙️",
                url_path="entretien",
            ),
        ],
        "Candidater": [
            st.Page(
                partial(_page_analyse, candidate.id),
                title="Analyser une annonce",
                icon="📋",
                url_path="analyser",
            ),
            st.Page(
                partial(_page_documents, candidate.id),
                title="CV & lettre",
                icon="✨",
                url_path="documents",
            ),
            st.Page(
                partial(_page_suivi, candidate.id),
                title="Suivi",
                icon="📌",
                url_path="suivi",
            ),
        ],
        "Outils": [
            st.Page(
                _page_referentiel,
                title="Référentiel",
                icon="🧩",
                url_path="referentiel",
            ),
            st.Page(
                partial(_page_marche, candidate.id),
                title="Mémoire de marché",
                icon="📊",
                url_path="marche",
            ),
        ],
    }

    return st.navigation(pages)


__all__ = ["construire_navigation"]

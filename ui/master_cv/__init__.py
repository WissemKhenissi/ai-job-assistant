"""
Page "Mon Master CV" : profil, expériences, compétences et entretien
IA d'enrichissement.

Éclatée en onglets — même motif que `ui/job_matching/`. Le tout tenait
auparavant sur un seul défilement interminable, au point que le bouton
d'envoi de l'entretien passait inaperçu en bas de page. L'entretien
(la *reconstruction* du Master CV) vit désormais à part de son
*résultat* (profil, expériences, compétences).
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import get_skills
from ui.master_cv.experiences_section import render_experiences_section
from ui.master_cv.import_section import render_import_section
from ui.master_cv.interview_section import render_interview_section
from ui.master_cv.skills_section import render_skills_section
from ui.profile_page import render_profile_page


def render_master_cv_page(candidate, experiences) -> None:

    st.header("Mon Master CV", divider="blue")

    onglet_profil, onglet_experiences, onglet_competences, onglet_entretien = (
        st.tabs(
            [
                "👤 Profil",
                "💼 Expériences",
                "🧠 Compétences",
                "🎙️ Entretien IA",
            ]
        )
    )

    with onglet_profil:

        # Placé en tête du profil : c'est la première chose dont un
        # nouvel utilisateur a besoin, et le repli s'ouvre de
        # lui-même tant que le parcours est vide.
        render_import_section(
            candidate.id, profil_vide=not experiences
        )

        render_profile_page(
            candidate,
            experiences_count=len(experiences),
            skills_count=len(get_skills(candidate.id)),
            experiences=experiences,
        )

    with onglet_experiences:
        render_experiences_section(experiences)

    with onglet_competences:
        render_skills_section(candidate.id)

    with onglet_entretien:
        render_interview_section(candidate.id)


__all__ = ["render_master_cv_page"]

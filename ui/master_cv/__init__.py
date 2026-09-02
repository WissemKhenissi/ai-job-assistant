"""
Page "Mon Master CV" : profil, expériences, compétences et entretien
IA d'enrichissement, réunis en une seule page.

Remplace les trois anciennes pages séparées de app.py ("Mon profil",
"Mes expériences", "Mes compétences") — la logique de chaque section
n'a pas changé, seul le regroupement est nouveau. Package sur le
modèle de `ui/job_matching/`.
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import get_skills
from ui.master_cv.experiences_section import render_experiences_section
from ui.master_cv.interview_section import render_interview_section
from ui.master_cv.skills_section import render_skills_section
from ui.profile_page import render_profile_page


def render_master_cv_page(candidate, experiences) -> None:

    st.header("Mon Master CV", divider="blue")

    render_profile_page(
        candidate,
        experiences_count=len(experiences),
        skills_count=len(get_skills(candidate.id)),
    )

    st.divider()

    render_experiences_section(experiences)

    st.divider()

    render_skills_section(candidate.id)

    st.divider()

    render_interview_section(candidate.id)


__all__ = ["render_master_cv_page"]

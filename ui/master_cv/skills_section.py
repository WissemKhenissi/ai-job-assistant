"""
Section "Compétences" de la page Master CV.

Logique reprise telle quelle de l'ancienne page "Mes compétences" de
app.py — seule sa place dans la page a changé.
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import get_skills


def render_skills_section(candidate_id: str) -> None:

    st.subheader("Compétences")

    skills = get_skills(candidate_id)

    if not skills:
        st.caption("Aucune compétence déclarée pour l'instant.")
        return

    for skill in skills:

        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(
                f"**{skill.name}**"
            )

        with col2:
            if skill.level:
                st.write(skill.level)

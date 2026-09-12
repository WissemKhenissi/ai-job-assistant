"""
Section "Expériences professionnelles" de la page Master CV.

Logique reprise telle quelle de l'ancienne page "Mes expériences" de
app.py — seule sa place dans la page a changé.
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import get_achievements
from utils.profile_editor import edit_experience


def render_experiences_section(experiences) -> None:

    for experience in experiences:

        with st.container(border=True):
            st.markdown(
                f"**{experience.job_title} — {experience.company}**"
            )

            fin = (
                experience.end_date.strftime('%B %Y')
                if experience.end_date
                else "aujourd'hui"
            )

            lieu = (
                f" · {experience.location}"
                if experience.location
                else ""
            )

            st.caption(
                f"{experience.start_date.strftime('%B %Y')} → "
                f"{fin}{lieu}"
            )

            if experience.business_context:
                st.markdown("**Contexte**")
                st.write(experience.business_context)

        achievements = get_achievements(experience.id)

        if achievements:

            st.markdown("Réalisations")

            for achievement in achievements:
                with st.container(border=True):
                    st.markdown(f"### {achievement.title}")
                    st.write(achievement.description)

                    if achievement.situation:
                        st.markdown("**Situation**")
                        st.write(achievement.situation)

                    if achievement.action:
                        st.markdown("**Actions menées**")
                        st.write(achievement.action)

                    if achievement.result:
                        st.markdown("**Résultat**")
                        st.write(achievement.result)

                    if achievement.metrics:
                        st.markdown("**Indicateurs**")
                        for metric in achievement.metrics.split("\n"):
                            if metric.strip():
                                st.markdown(f"- {metric}")

        mode = st.segmented_control(
            "Mode",
            ["Consulter", "Modifier"],
            default="Consulter",
            key=f"mode_{experience.id}"
        )

        if mode == "Modifier":

            edit_experience(
                experience
            )

        st.divider()

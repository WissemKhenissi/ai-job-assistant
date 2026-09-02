import streamlit as st

from services.profile_service import (
    get_candidate,
    get_experiences,
    get_achievements,
    get_skills,
)

from utils.profile_editor import edit_experience
from ui.job_matching_page import render_job_matching_page


st.set_page_config(
    page_title="AI Job Assistant",
    page_icon="🤖",
    layout="wide"
)


# ============================================================
# DONNÉES
# ============================================================

candidate = get_candidate()
experiences = get_experiences()


# ============================================================
# HEADER
# ============================================================

st.title("🤖 AI Job Assistant")

st.write(
    "Ton assistant intelligent pour construire, adapter "
    "et suivre tes candidatures."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Aller vers",
    [
        "Mon profil",
        "Mes expériences",
        "Mes compétences",
        "Mes candidatures",
    ]
)


# ============================================================
# PAGE : MON PROFIL
# ============================================================

if page == "Mon profil":

    st.header("Mon profil professionnel", divider="blue")

    st.subheader("Positionnement")

    st.write(
        "Product Owner • Product Owner Digital • "
        "Chef de projet IT • PMO"
    )

    st.divider()

    st.subheader("Résumé de l'expérience")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Expérience principale",
            "7+ ans"
        )

    with col2:
        st.metric(
            "Expériences",
            len(experiences)
        )

    with col3:
        st.metric(
            "Compétences",
            len(get_skills(candidate.id))
        )

    st.divider()

    st.subheader("🎯 Positionnement")

    st.write(
        """
        Profil hybride Business / Digital / Produit,
        avec plus de 7 ans d'expérience dans des environnements
        e-commerce et adtech.
        """ 
    )


# ============================================================
# PAGE : MES EXPÉRIENCES
# ============================================================

elif page == "Mes expériences":

    st.header("Mes expériences professionnelles", divider="blue")

    for experience in experiences:

        with st.container(border=True):
            st.subheader(
                f"{experience.job_title} — {experience.company}"
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

        st.subheader("Réalisations")

        achievements = get_achievements(experience.id)

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


# ============================================================
# PAGE : MES COMPÉTENCES
# ============================================================

elif page == "Mes compétences":

    st.header("🧠 Mes compétences")

    skills = get_skills(candidate.id)

    st.subheader("Compétences")

    for skill in skills:

        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(
                f"**{skill.name}**"
            )

        with col2:
            if skill.level:
                st.write(skill.level)


# ============================================================
# PAGE : MES CANDIDATURES
# ============================================================

elif page == "Mes candidatures":
    render_job_matching_page(candidate.id)



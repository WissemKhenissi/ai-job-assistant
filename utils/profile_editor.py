import streamlit as st


def edit_experience(experience):

    st.subheader("✏️ Modifier l'expérience")

    company = st.text_input(
        "Entreprise",
        value=experience.company
    )

    job_title = st.text_input(
        "Poste",
        value=experience.job_title
    )

    description = st.text_area(
        "Description",
        value=experience.description,
        height=150
    )

    business_context = st.text_area(
        "Contexte business",
        value=experience.business_context,
        height=150
    )

    team_context = st.text_area(
        "Contexte de l'équipe",
        value=experience.team_context,
        height=150
    )

    st.divider()

    st.subheader("🎯 Responsabilités")

    responsibilities = []

    for i, responsibility in enumerate(
        experience.responsibilities
    ):

        value = st.text_input(
            f"Responsabilité {i + 1}",
            value=responsibility,
            key=f"responsibility_{i}"
        )

        responsibilities.append(value)

    st.divider()

    st.subheader("🧠 Compétences")

    skills = []

    for i, skill in enumerate(
        experience.skills
    ):

        value = st.text_input(
            f"Compétence {i + 1}",
            value=skill,
            key=f"skill_{i}"
        )

        skills.append(value)

    st.divider()

    save = st.button(
        "💾 Enregistrer les modifications",
        type="primary"
    )

    if save:

        experience.company = company
        experience.job_title = job_title
        experience.description = description
        experience.business_context = business_context
        experience.team_context = team_context

        experience.responsibilities = [
            r for r in responsibilities
            if r.strip()
        ]

        experience.skills = [
            s for s in skills
            if s.strip()
        ]

        st.success(
            "Les modifications ont été enregistrées."
        )

    return experience
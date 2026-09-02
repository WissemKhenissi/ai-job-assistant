"""
Section "Profil" de la page Master CV : consultation et édition des
champs de présentation du candidat (accroche, disponibilité, langues,
centres d'intérêt, motivations).

Avant ce module, ces champs existaient en base (voir
database/models.py::CandidateDB) mais n'avaient aucune interface pour
les renseigner — ils restaient vides. C'est le premier point d'entrée
qui les rend réellement éditables, et qui introduit le champ
"motivations" (projet professionnel, reconversion, intérêt pour un
secteur ou une entreprise) : la seule source pour ce que la lettre de
motivation rédigée par l'IA peut dire des motivations du candidat.
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import update_candidate


def render_profile_page(candidate, experiences_count: int, skills_count: int) -> None:

    st.subheader("Profil")

    # --------------------------------------------------------
    # RÉSUMÉ CHIFFRÉ
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Expériences", experiences_count)

    with col2:
        st.metric("Compétences", skills_count)

    with col3:
        st.metric(
            "Disponibilité",
            candidate.availability or "—",
        )

    st.divider()

    # --------------------------------------------------------
    # CONSULTATION
    # --------------------------------------------------------

    st.subheader("Positionnement")

    if candidate.headline:
        st.write(f"**{candidate.headline}**")
    else:
        st.caption("Aucune accroche renseignée pour l'instant.")

    if candidate.summary:
        st.write(candidate.summary)

    if candidate.motivations:
        st.subheader("Motivations et projet professionnel")
        st.write(candidate.motivations)

    st.divider()

    # --------------------------------------------------------
    # ÉDITION
    # --------------------------------------------------------

    st.subheader("✏️ Modifier mon profil")

    st.caption(
        "Ces informations ne sont jamais déduites : seul ce que vous "
        "écrivez ici peut apparaître dans un CV ou une lettre générés."
    )

    with st.form("edit_profile"):

        headline = st.text_input(
            "Accroche",
            value=candidate.headline,
            placeholder=(
                "Ex. Product Owner Digital — E-commerce & Tech"
            ),
            help="Affichée sous votre nom sur le CV.",
        )

        availability = st.text_input(
            "Disponibilité",
            value=candidate.availability,
            placeholder="Ex. Disponible immédiatement",
        )

        languages = st.text_area(
            "Langues",
            value=candidate.languages,
            height=80,
            placeholder="Ex. Français (natif), Anglais (courant)",
        )

        interests = st.text_area(
            "Centres d'intérêt",
            value=candidate.interests,
            height=80,
        )

        motivations = st.text_area(
            "Motivations et projet professionnel",
            value=candidate.motivations,
            height=160,
            placeholder=(
                "Ex. En reconversion vers le produit après 5 ans en "
                "gestion de projet ; intérêt marqué pour le secteur "
                "de la santé ; recherche un poste où..."
            ),
            help=(
                "Reconversion, intérêt pour un secteur ou une "
                "entreprise en particulier, ce qui donne envie d'y "
                "aller — tout ce que vous détaillez ici pourra "
                "nourrir la lettre de motivation rédigée par l'IA."
            ),
        )

        enregistrer = st.form_submit_button(
            "💾 Enregistrer",
            type="primary",
        )

        if enregistrer:

            try:
                update_candidate(
                    candidate.id,
                    headline=headline.strip(),
                    availability=availability.strip(),
                    languages=languages.strip(),
                    interests=interests.strip(),
                    motivations=motivations.strip(),
                )

            except Exception as error:
                st.error(f"Enregistrement impossible : {error}")
                return

            st.success("Profil mis à jour.")
            st.rerun()

"""
Édition du profil (Master CV) depuis l'interface.

Chaque formulaire écrit directement dans la base via
services.profile_service : contrairement à l'ancienne version de ce
module, "Enregistrer" persiste réellement les modifications.
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import update_experience


def edit_experience(experience) -> None:
    """
    Formulaire d'édition d'une expérience réelle (ExperienceDB).

    Les clés de widgets sont préfixées par l'identifiant de
    l'expérience : sans ça, éditer deux expériences en même temps
    (chacune a son propre bouton "Modifier") ferait entrer en
    collision les mêmes clés de champ d'un formulaire à l'autre.
    """

    prefixe = experience.id

    st.subheader("✏️ Modifier l'expérience")

    with st.form(f"edit_experience_{prefixe}"):

        company = st.text_input(
            "Entreprise",
            value=experience.company,
            key=f"company_{prefixe}",
        )

        job_title = st.text_input(
            "Poste",
            value=experience.job_title,
            key=f"job_title_{prefixe}",
        )

        location = st.text_input(
            "Lieu",
            value=experience.location,
            key=f"location_{prefixe}",
        )

        col_debut, col_fin = st.columns(2)

        with col_debut:
            start_date = st.date_input(
                "Date de début",
                value=experience.start_date,
                key=f"start_date_{prefixe}",
            )

        with col_fin:
            poste_actuel = st.checkbox(
                "Poste actuel (pas de date de fin)",
                value=experience.end_date is None,
                key=f"poste_actuel_{prefixe}",
            )

            end_date = None

            if not poste_actuel:
                end_date = st.date_input(
                    "Date de fin",
                    value=experience.end_date or experience.start_date,
                    key=f"end_date_{prefixe}",
                )

        description = st.text_area(
            "Description",
            value=experience.description,
            height=100,
            key=f"description_{prefixe}",
        )

        business_context = st.text_area(
            "Contexte business",
            value=experience.business_context,
            height=100,
            key=f"business_context_{prefixe}",
        )

        team_context = st.text_area(
            "Contexte de l'équipe",
            value=experience.team_context,
            height=100,
            key=f"team_context_{prefixe}",
        )

        enregistrer = st.form_submit_button(
            "💾 Enregistrer les modifications",
            type="primary",
        )

        if enregistrer:

            if not company.strip() or not job_title.strip():
                st.error(
                    "L'entreprise et le poste ne peuvent pas être "
                    "vides."
                )
                return

            if end_date is not None and end_date < start_date:
                st.error(
                    "La date de fin ne peut pas précéder la date "
                    "de début."
                )
                return

            try:
                update_experience(
                    experience.id,
                    company=company.strip(),
                    job_title=job_title.strip(),
                    location=location.strip(),
                    start_date=start_date,
                    end_date=end_date,
                    description=description.strip(),
                    business_context=business_context.strip(),
                    team_context=team_context.strip(),
                )

            except Exception as error:
                st.error(f"Enregistrement impossible : {error}")
                return

            st.success("Les modifications ont été enregistrées.")
            st.rerun()

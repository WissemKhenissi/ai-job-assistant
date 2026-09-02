"""
Onglet "Suivi" : liste des candidatures déjà générées, avec mise à
jour manuelle du statut.

Les statuts sont saisis à la main : la V1 ne lit aucune boîte mail,
ce qui demanderait un connecteur externe hors périmètre.
"""

from __future__ import annotations

import streamlit as st

from models.application import (
    APPLICATION_STATUS_LABELS,
    APPLICATION_STATUSES,
)
from services.application_service import (
    list_applications,
    update_application_status,
)


def render_tracking_tab(candidate_id: str) -> None:

    candidatures = list_applications(candidate_id)

    if not candidatures:

        st.info(
            "Aucune candidature enregistrée. Générer un CV et une "
            "lettre pour une annonce crée automatiquement son suivi."
        )

        return

    for candidature in candidatures:

        intitule = candidature.job_offer_title or "Annonce"

        if candidature.company:
            intitule += f" — {candidature.company}"

        with st.expander(
            f"{intitule}  ·  {candidature.status_label}"
        ):

            st.caption(
                "Documents générés le "
                + candidature.created_at.strftime("%d/%m/%Y à %H:%M")
            )

            fichiers = [
                chemin
                for chemin in (
                    candidature.cv_docx_path,
                    candidature.cv_pdf_path,
                    candidature.letter_docx_path,
                    candidature.letter_pdf_path,
                )
                if chemin
            ]

            if fichiers:
                st.caption("Fichiers : " + " · ".join(fichiers))

            with st.form(f"suivi_{candidature.id}"):

                statut = st.selectbox(
                    "Statut",
                    options=APPLICATION_STATUSES,
                    index=APPLICATION_STATUSES.index(
                        candidature.status
                    )
                    if candidature.status in APPLICATION_STATUSES
                    else 0,
                    format_func=lambda valeur: (
                        APPLICATION_STATUS_LABELS.get(valeur, valeur)
                    ),
                )

                notes = st.text_area(
                    "Notes",
                    value=candidature.notes,
                    placeholder=(
                        "Contact, canal d'envoi, retour reçu..."
                    ),
                )

                if st.form_submit_button("Enregistrer le suivi"):

                    try:

                        update_application_status(
                            application_id=candidature.id,
                            status=statut,
                            notes=notes,
                        )

                        st.success("Suivi mis à jour.")

                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"Mise à jour impossible : {error}"
                        )

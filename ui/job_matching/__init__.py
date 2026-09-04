"""
Page "Mes candidatures" : analyse d'annonce, génération de CV et de
lettre (avec ou sans IA), suivi des candidatures, mémoire de marché.

Éclaté en package (un module par onglet), à la place de l'ancien
fichier unique de 880 lignes qui empilait tout sur un seul long
défilement — même destinée à un seul utilisateur, la page avait
grandi au point que ce défilement devenait le principal obstacle à
sa lisibilité, pas la logique elle-même, restée inchangée module par
module.
"""

from __future__ import annotations

import streamlit as st

from ui.job_matching.analysis import render_analysis_tab
from ui.job_matching.generation import render_generation_tab
from ui.job_matching.market_memory import render_market_memory_tab
from ui.job_matching.referentiel import render_referentiel_tab
from ui.job_matching.tracking import render_tracking_tab


def render_job_matching_page(candidate_id: str) -> None:

    st.header("Mes candidatures", divider="blue")

    (
        tab_annonce,
        tab_generation,
        tab_suivi,
        tab_memoire,
        tab_referentiel,
    ) = st.tabs(
        [
            "📋 Nouvelle annonce",
            "✨ CV & lettre",
            "📌 Suivi",
            "📊 Mémoire de marché",
            "🧩 Référentiel",
        ]
    )

    with tab_annonce:
        render_analysis_tab(candidate_id)

    with tab_generation:

        stored_result = st.session_state.get("job_matching_result")

        if stored_result is None:

            st.info(
                "Analysez d'abord une annonce dans l'onglet "
                "« Nouvelle annonce » pour générer un CV et une "
                "lettre."
            )

        else:

            render_generation_tab(
                candidate_id=candidate_id,
                job_offer_id=stored_result["job_offer_id"],
            )

    with tab_suivi:
        render_tracking_tab(candidate_id)

    with tab_memoire:
        render_market_memory_tab(candidate_id)

    with tab_referentiel:
        render_referentiel_tab()


__all__ = ["render_job_matching_page"]

"""
Onglet "Mémoire de marché" : compétences les plus fréquemment
demandées parmi les annonces sélectionnées et déjà analysées.
"""

from __future__ import annotations

import streamlit as st

from services.market_memory_service import get_market_skill_memory


def render_market_memory_tab(candidate_id: str) -> None:

    memory = get_market_skill_memory(
        candidate_id=candidate_id,
        included_job_statuses={"selected"},
    )

    st.caption(
        f"{memory.analyzed_jobs_count} annonce(s) "
        "sélectionnée(s) et analysée(s)."
    )

    if memory.skills:

        memory_rows = []

        for item in memory.skills:

            memory_rows.append(
                {
                    "Priorité": item.priority,
                    "Compétence": item.skill,
                    "Fréquence": (
                        f"{item.frequency_percent:.0f} %"
                    ),
                    "Manquante": item.missing_count,
                    "À documenter": item.inferred_count,
                }
            )

        st.dataframe(
            memory_rows,
            hide_index=True,
            use_container_width=True,
        )

    else:

        st.info(
            "La mémoire se construira après l'analyse "
            "d'une annonce sélectionnée."
        )

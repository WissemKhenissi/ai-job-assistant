from __future__ import annotations

from uuid import uuid4

import streamlit as st

from services.job_service import save_job_offer
from services.market_memory_service import get_market_skill_memory
from services.matching import analyze_and_save_job_match
from services.job_requirements_service import extract_required_skills


def _new_draft() -> None:
    st.session_state["job_matching_draft_id"] = f"job-{uuid4()}"
    st.session_state.pop("job_matching_result", None)
    st.rerun()


def render_job_matching_page(candidate_id: str) -> None:

    st.header("Mes candidatures", divider="blue")

    st.write(
        "Collez une annonce, indiquez les compétences attendues, "
        "puis obtenez un score de matching explicable."
    )

    # ========================================================
    # INITIALISATION
    # ========================================================

    if "job_matching_draft_id" not in st.session_state:
        st.session_state["job_matching_draft_id"] = f"job-{uuid4()}"

    # ========================================================
    # FORMULAIRE
    # ========================================================

    with st.form("job_matching_form"):

        title = st.text_input(
            "Intitulé du poste *",
            placeholder="Product Owner E-commerce",
        )

        col1, col2 = st.columns(2)

        with col1:

            company = st.text_input(
                "Entreprise",
                placeholder="Nom de l'entreprise",
            )

            location = st.text_input(
                "Localisation",
                placeholder="Paris / Hybride",
            )

        with col2:

            contract_type = st.selectbox(
                "Type de contrat",
                ["", "CDI", "CDD", "Freelance", "Stage"],
            )

            remote_policy = st.selectbox(
                "Télétravail",
                ["", "Sur site", "Hybride", "Télétravail complet"],
            )

        description = st.text_area(
            "Texte de l'annonce *",
            height=220,
            placeholder="Collez ici l'annonce complète.",
        )

        submitted = st.form_submit_button(
            "Analyser l'annonce",
            type="primary",
            use_container_width=True,
        )

    # ========================================================
    # ANALYSE
    # ========================================================

    if submitted:

        if not title.strip():
            st.error("L'intitulé du poste est obligatoire.")
            return

        if not description.strip():
            st.error("Le texte de l'annonce est obligatoire.")
            return

        required_skills = extract_required_skills(description)

        if not required_skills:

            st.error(
                "Aucune compétence n'a été détectée dans l'annonce. "
                "Vous pouvez les ajouter manuellement si besoin."
            )

            return

        try:

            job_offer_id = save_job_offer(
                job_offer_id=st.session_state["job_matching_draft_id"],
                title=title.strip(),
                description=description.strip(),
                company=company.strip(),
                location=location.strip(),
                contract_type=contract_type,
                remote_policy=remote_policy,
                source="manual",
                status="selected",
            )

            result = analyze_and_save_job_match(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
                required_skills=required_skills,
            )

            st.session_state["job_matching_result"] = {
                "job_offer_id": job_offer_id,
                "title": title.strip(),
                "extraction_source": "automatique",
                "required_skills": required_skills,
                "result": result,
            }

            st.success(
                "Annonce analysée et enregistrée."
            )

        except Exception as error:

            st.error(
                f"Analyse impossible : {error}"
            )

            return

    # ========================================================
    # RÉCUPÉRATION DU DERNIER RÉSULTAT
    # ========================================================

    stored_result = st.session_state.get(
        "job_matching_result"
    )

    # Si aucune analyse n'a encore été effectuée,
    # on affiche simplement la mémoire du marché.
    if stored_result is None:

        st.info(
            "Collez une annonce puis cliquez sur "
            "« Analyser l'annonce » pour obtenir le matching."
        )

    else:

        result = stored_result["result"]

        # ====================================================
        # INFORMATIONS SUR L'ANNONCE
        # ====================================================

        st.caption(
            f"Compétences utilisées — "
            f"{stored_result['extraction_source']} : "
            f"{', '.join(stored_result['required_skills'])}"
        )

        st.divider()

        st.subheader(
            stored_result["title"]
        )

        # ====================================================
        # SCORE
        # ====================================================

        score_col, proven_col, inferred_col, missing_col = st.columns(4)

        score_col.metric(
            "Score global",
            f"{result.score_global:.0f} / 100",
        )

        proven_col.metric(
            "Compétences prouvées",
            len(result.matched_skills),
        )

        inferred_col.metric(
            "Compétences déduites",
            len(result.inferred_skills),
        )

        missing_col.metric(
            "Compétences manquantes",
            len(result.missing_skills),
        )

        # ====================================================
        # DÉTAIL DU MATCHING
        # ====================================================

        status_labels = {
            "proven": "🟢 Prouvée",
            "inferred": "🟡 Déduite",
            "missing": "🔴 Manquante",
        }

        details = []

        for item in result.matches:

            details.append(
                {
                    "Compétence": item.skill,
                    "Statut": status_labels.get(
                        item.status,
                        item.status,
                    ),
                    "Score": f"{item.score * 100:.0f} %",
                    "Justification": item.explanation,
                    "Éléments du Master CV": (
                        "\n".join(item.evidence)
                        if item.evidence
                        else "—"
                    ),
                }
            )

        st.subheader(
            "Détail du matching"
        )

        if details:

            st.dataframe(
                details,
                hide_index=True,
                use_container_width=True,
            )

        else:

            st.info(
                "Aucun détail de matching disponible."
            )

        # ====================================================
        # POINTS FORTS
        # ====================================================

        if result.strengths:

            st.subheader(
                "Points forts"
            )

            for strength in result.strengths:

                st.success(
                    strength
                )

        # ====================================================
        # POINTS DE VIGILANCE
        # ====================================================

        if result.weaknesses:

            st.subheader(
                "Points de vigilance"
            )

            for weakness in result.weaknesses:

                st.warning(
                    weakness
                )

    # ========================================================
    # MÉMOIRE DE MARCHÉ
    # ========================================================

    st.divider()

    st.subheader(
        "Mémoire de marché"
    )

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

    # ========================================================
    # NOUVELLE ANNONCE
    # ========================================================

    if st.button(
        "Analyser une nouvelle annonce"
    ):

        _new_draft()
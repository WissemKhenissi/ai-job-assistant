"""
Onglet "Nouvelle annonce" : formulaire d'analyse d'une offre, score de
matching, détail par compétence, points forts et points de vigilance.

Le résultat de l'analyse est conservé en session_state
("job_matching_result") : c'est ce que lit l'onglet "CV & lettre" pour
savoir sur quelle offre travailler, indépendamment de l'onglet
actuellement affiché — Streamlit réexécute tout le script à chaque
interaction, les deux onglets restent donc synchronisés.
"""

from __future__ import annotations

import unicodedata
from uuid import uuid4

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.job_analysis import (
    analyze_job_offer_with_ai,
    generate_fit_synthesis,
)
from services.job_offer_fetcher import fetch_job_offer_from_url
from services.job_service import save_job_offer
from services.matching import analyze_and_save_job_match
from services.job_requirements_service import extract_required_skills


# Clés session_state utilisées pour préremplir le formulaire après une
# récupération réussie depuis un lien — le formulaire ci-dessous les
# lit comme valeurs initiales.
_PREFILL_TITLE_KEY = "job_matching_prefill_title"
_PREFILL_TEXT_KEY = "job_matching_prefill_text"


def _normalize_loose(text: str) -> str:
    """Minuscules, sans accents — suffisant pour une déduplication d'affichage."""

    normalized = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).casefold()


def _new_draft() -> None:
    st.session_state["job_matching_draft_id"] = f"job-{uuid4()}"
    st.session_state.pop("job_matching_result", None)
    st.session_state.pop(_PREFILL_TITLE_KEY, None)
    st.session_state.pop(_PREFILL_TEXT_KEY, None)
    st.rerun()


def render_analysis_tab(candidate_id: str) -> None:

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
    # RECUPERATION DEPUIS UN LIEN (OPTIONNEL)
    # ========================================================
    #
    # Purement mécanique (pas d'IA) : un téléchargement de la page et
    # une extraction du texte principal. Ne fonctionne pas partout —
    # LinkedIn notamment bloque ce type de requête. Le copier-coller
    # ci-dessous reste toujours disponible, avant comme après un échec.

    with st.expander("🔗 Récupérer depuis un lien"):

        col_lien, col_bouton = st.columns([4, 1])

        with col_lien:

            lien_annonce = st.text_input(
                "Lien de l'annonce",
                placeholder="https://...",
                label_visibility="collapsed",
                key="job_offer_url_input",
            )

        with col_bouton:

            recuperer_clic = st.button(
                "Récupérer",
                use_container_width=True,
            )

        if recuperer_clic:

            with st.spinner("Récupération en cours..."):
                resultat_fetch = fetch_job_offer_from_url(lien_annonce)

            if resultat_fetch.success:

                st.session_state[_PREFILL_TITLE_KEY] = resultat_fetch.title
                st.session_state[_PREFILL_TEXT_KEY] = resultat_fetch.text

                st.success(
                    "Contenu récupéré ci-dessous — vérifiez-le avant "
                    "d'analyser : l'extraction automatique peut être "
                    "imparfaite selon le site."
                )

                st.rerun()

            else:

                st.error(
                    f"{resultat_fetch.error} Vous pouvez toujours "
                    "coller le texte manuellement ci-dessous."
                )

    # ========================================================
    # FORMULAIRE
    # ========================================================

    with st.form("job_matching_form"):

        title = st.text_input(
            "Intitulé du poste *",
            value=st.session_state.get(_PREFILL_TITLE_KEY, ""),
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
            value=st.session_state.get(_PREFILL_TEXT_KEY, ""),
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

        # --------------------------------------------------------
        # CATEGORISATION + EXTRACTION IA (GEMINI), OPTIONNELLE
        # --------------------------------------------------------
        #
        # Ne remplace jamais une sélection manuelle explicite : elle
        # ne comble que les champs laissés vides. Les compétences
        # détectées par le catalogue restent la base ; l'IA ne fait
        # qu'y ajouter celles qu'elle a repérées en plus. La
        # déduplication ici est insensible à la casse/aux accents —
        # simple affichage — le moteur de matching applique sa propre
        # normalisation, plus poussée, au moment du calcul du score.

        avertissement_ia = ""

        if ai_is_configured():

            analyse_ia = analyze_job_offer_with_ai(
                f"{title.strip()}\n{description.strip()}"
            )

            avertissement_ia = analyse_ia.warning

            contract_type = contract_type or analyse_ia.contract_type
            remote_policy = remote_policy or analyse_ia.remote_policy
            remote_details = analyse_ia.remote_details

            deja_presentes = {
                _normalize_loose(skill) for skill in required_skills
            }

            for skill in analyse_ia.required_skills:

                cle = _normalize_loose(skill)

                if cle in deja_presentes:
                    continue

                deja_presentes.add(cle)
                required_skills.append(skill)

        else:

            remote_details = ""

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
                remote_details=remote_details,
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
                "extraction_source": (
                    "catalogue + IA (Gemini)"
                    if ai_is_configured()
                    else "catalogue"
                ),
                "required_skills": required_skills,
                "result": result,
                "contract_type": contract_type,
                "remote_policy": remote_policy,
                "remote_details": remote_details,
            }

            st.success(
                "Annonce analysée et enregistrée. Passez à l'onglet "
                "« CV & lettre » pour générer vos documents."
            )

            if avertissement_ia:
                st.caption(avertissement_ia)

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
        # CATEGORISATION DE L'OFFRE
        # ====================================================

        categorisation = " · ".join(
            partie
            for partie in (
                stored_result.get("contract_type", ""),
                stored_result.get("remote_policy", ""),
                stored_result.get("remote_details", ""),
            )
            if partie
        )

        if categorisation:
            st.caption(f"📋 {categorisation}")

        # ====================================================
        # SCORE
        # ====================================================

        (
            score_col,
            proven_col,
            declared_col,
            inferred_col,
            missing_col,
        ) = st.columns(5)

        score_col.metric(
            "Score global",
            f"{result.score_global:.0f} / 100",
        )

        proven_col.metric(
            "Prouvées",
            len(result.proven_skills),
            help=(
                "Déclarées dans le Master CV et soutenues par "
                "au moins une preuve."
            ),
        )

        declared_col.metric(
            "Déclarées",
            len(result.declared_skills),
            help=(
                "Déclarées dans le Master CV, mais sans preuve "
                "rattachée : à documenter."
            ),
        )

        inferred_col.metric(
            "Déduites",
            len(result.inferred_skills),
            help=(
                "Non déclarées, déduites du parcours : une "
                "hypothèse, pas un fait affirmé."
            ),
        )

        missing_col.metric(
            "Manquantes",
            len(result.missing_skills),
        )

        # ====================================================
        # DÉTAIL DU MATCHING
        # ====================================================

        status_labels = {
            "proven": "🟢 Prouvée",
            "declared": "🔵 Déclarée",
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

        # ====================================================
        # AVIS IA SUR L'ADEQUATION (OPTIONNEL)
        # ====================================================
        #
        # Ne recalcule rien : met en mots le score et les statuts
        # déjà déterminés ci-dessus par le moteur honnête. Volontaire
        # -ment un avis à part, jamais confondu avec le score officiel.

        st.divider()

        job_offer_id = stored_result["job_offer_id"]
        synthese_key = f"fit_synthesis_{job_offer_id}"

        if not ai_is_configured():

            st.caption(
                "Avis IA sur l'adéquation indisponible — clé "
                "GEMINI_API_KEY absente de .env."
            )

        else:

            if st.button(
                "🔎 Générer un avis IA sur l'adéquation",
                key=f"generer_avis_{job_offer_id}",
            ):

                with st.spinner("Analyse en cours (Gemini)..."):
                    st.session_state[synthese_key] = (
                        generate_fit_synthesis(
                            candidate_id=candidate_id,
                            job_offer_id=job_offer_id,
                        )
                    )

            synthese = st.session_state.get(synthese_key)

            if synthese is not None:

                if synthese.text:

                    st.info(
                        "**Avis IA (indicatif — ne remplace pas "
                        "l'analyse ci-dessus)**\n\n" + synthese.text
                    )

                elif synthese.warning:

                    st.caption(synthese.warning)

    # ========================================================
    # NOUVELLE ANNONCE
    # ========================================================

    st.divider()

    if st.button(
        "Analyser une nouvelle annonce"
    ):

        _new_draft()

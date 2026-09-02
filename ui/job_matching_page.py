from __future__ import annotations

from uuid import uuid4

import streamlit as st

from models.application import (
    APPLICATION_STATUS_LABELS,
    APPLICATION_STATUSES,
)
from services.application_service import (
    list_applications,
    record_application,
    update_application_status,
)
from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.reformulation import (
    reformulate_cover_letter,
    reformulate_targeted_cv,
)
from services.cv import (
    build_targeted_cv,
    export_docx,
    export_pdf,
)
from services.letter import (
    build_cover_letter,
    export_letter_docx,
    export_letter_pdf,
)
from services.job_service import get_job_offer_text, save_job_offer
from services.market_memory_service import get_market_skill_memory
from services.matching import analyze_and_save_job_match
from services.job_requirements_service import extract_required_skills


def _new_draft() -> None:
    st.session_state["job_matching_draft_id"] = f"job-{uuid4()}"
    st.session_state.pop("job_matching_result", None)
    st.rerun()


def _render_cv_generation(
    candidate_id: str,
    job_offer_id: str,
) -> None:
    """
    Génération du CV ciblé et de la lettre à partir de l'analyse, et
    reformulation IA optionnelle.

    Les deux documents sont reconstruits à chaque clic depuis les
    données du Master CV : il n'existe aucun état intermédiaire
    modifiable entre l'analyse et les documents produits.

    Le texte affiché (déterministe ou reformulé) est conservé en
    session_state, sous la clé de l'offre : Streamlit réexécute tout
    le script à chaque interaction, il faut donc explicitement se
    souvenir de si on regarde la version brute ou reformulée.
    """

    st.divider()

    st.subheader("CV ciblé et lettre de motivation")

    st.caption(
        "Les documents ne reprennent que les compétences prouvées, "
        "c'est-à-dire déclarées dans le Master CV et soutenues par "
        "au moins une preuve. Les compétences déduites ou déclarées "
        "sans preuve en sont volontairement absentes."
    )

    etat_key = f"cv_letter_{job_offer_id}"

    if st.button("Générer le CV et la lettre"):

        try:

            cv = build_targeted_cv(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )

            letter = build_cover_letter(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )

        except Exception as error:

            st.error(f"Génération impossible : {error}")

            return

        # La reformulation part toujours de cette version : ne
        # jamais reformuler un texte déjà reformulé, pour ne pas
        # accumuler de dérive au fil des essais.
        st.session_state[etat_key] = {
            "cv_deterministe": cv,
            "letter_deterministe": letter,
            "cv_affiche": cv,
            "letter_affiche": letter,
            "reformule": False,
        }

    etat = st.session_state.get(etat_key)

    if etat is None:
        return

    cv = etat["cv_affiche"]
    letter = etat["letter_affiche"]

    if not cv.skills:

        st.warning(
            "Aucune compétence prouvée ne correspond à cette "
            "annonce. Le CV généré ne comportera pas de section "
            "Compétences : documenter des preuves dans le Master CV "
            "est le seul moyen honnête de l'étoffer."
        )

    else:

        st.success(
            f"{len(cv.skills)} compétence(s) prouvée(s) retenue(s) : "
            + ", ".join(cv.skills)
        )

    if cv.declared_skills or cv.inferred_skills:

        laissees = cv.declared_skills + cv.inferred_skills

        st.info(
            "Volontairement laissées de côté : "
            + ", ".join(laissees)
        )

    st.caption(
        f"{cv.total_lines} ligne(s) d'expérience retenue(s), "
        f"{len(cv.achievements)} réalisation(s)."
    )

    # --------------------------------------------------------
    # REFORMULATION IA (GEMINI) — OPTIONNELLE
    # --------------------------------------------------------
    #
    # Reformule toujours à partir de la version déterministe stockée
    # (jamais à partir d'une reformulation précédente) : l'IA ne peut
    # qu'ajuster le ton et le vocabulaire, jamais s'écarter davantage
    # du texte source à chaque nouvel essai.

    st.divider()

    if not ai_is_configured():

        st.caption(
            "Reformulation IA (Gemini) non configurée — clé "
            "GEMINI_API_KEY absente de .env. Les documents restent "
            "utilisables tels quels."
        )

    else:

        reformuler_col, revenir_col = st.columns(2)

        with reformuler_col:

            reformuler_clic = st.button(
                "✨ Reformuler avec l'IA (Gemini)",
                key=f"reformuler_{job_offer_id}",
            )

        with revenir_col:

            if etat["reformule"]:

                if st.button(
                    "↩️ Revenir au texte déterministe",
                    key=f"revenir_{job_offer_id}",
                ):

                    etat["cv_affiche"] = etat["cv_deterministe"]
                    etat["letter_affiche"] = etat["letter_deterministe"]
                    etat["reformule"] = False

                    st.rerun()

        if reformuler_clic:

            job_text = get_job_offer_text(job_offer_id)

            with st.spinner("Reformulation en cours..."):

                cv_reformule, avertissements_cv = reformulate_targeted_cv(
                    etat["cv_deterministe"],
                    job_text,
                )

                letter_reformulee, avertissements_lettre = (
                    reformulate_cover_letter(
                        etat["letter_deterministe"],
                        job_text,
                    )
                )

            etat["cv_affiche"] = cv_reformule
            etat["letter_affiche"] = letter_reformulee
            etat["reformule"] = True

            cv = cv_reformule
            letter = letter_reformulee

            for avertissement in (
                avertissements_cv + avertissements_lettre
            ):
                st.warning(avertissement)

            if not (avertissements_cv + avertissements_lettre):
                st.success("Texte reformulé avec Gemini.")

        elif etat["reformule"]:

            st.caption("Version actuellement affichée : reformulée par l'IA.")

    # --------------------------------------------------------
    # LETTRE — RELECTURE OBLIGATOIRE
    # --------------------------------------------------------

    st.markdown("**Lettre de motivation**")

    st.warning(
        "Cette lettre est un brouillon assemblé à partir de votre "
        "Master CV. Relisez-la et adaptez-la avant tout envoi : "
        "aucune lettre générée n'est finale."
    )

    st.text_area(
        "Texte de la lettre",
        value=letter.full_text,
        height=320,
        label_visibility="collapsed",
    )

    # --------------------------------------------------------
    # TÉLÉCHARGEMENTS
    # --------------------------------------------------------

    cv_docx = export_docx(cv)
    cv_pdf = export_pdf(cv)

    letter_docx = export_letter_docx(letter)
    letter_pdf = export_letter_pdf(letter)

    DOCX_MIME = (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    )

    cv_col, letter_col = st.columns(2)

    with cv_col:

        st.caption("CV ciblé")

        st.download_button(
            "CV — DOCX",
            data=cv_docx.read_bytes(),
            file_name=cv_docx.name,
            mime=DOCX_MIME,
        )

        st.download_button(
            "CV — PDF",
            data=cv_pdf.read_bytes(),
            file_name=cv_pdf.name,
            mime="application/pdf",
        )

    with letter_col:

        st.caption("Lettre de motivation")

        st.download_button(
            "Lettre — DOCX",
            data=letter_docx.read_bytes(),
            file_name=letter_docx.name,
            mime=DOCX_MIME,
        )

        st.download_button(
            "Lettre — PDF",
            data=letter_pdf.read_bytes(),
            file_name=letter_pdf.name,
            mime="application/pdf",
        )

    # --------------------------------------------------------
    # SUIVI DE CANDIDATURE
    # --------------------------------------------------------
    #
    # Le CV et la lettre existent : la candidature est tracée
    # automatiquement, conformément au principe « chaque candidature
    # laisse une trace ».

    record_application(
        candidate_id=candidate_id,
        job_offer_id=job_offer_id,
        cv_docx_path=cv_docx,
        cv_pdf_path=cv_pdf,
        letter_docx_path=letter_docx,
        letter_pdf_path=letter_pdf,
    )

    st.caption(
        "Cette candidature a été ajoutée à votre suivi, dans la "
        "section « Suivi des candidatures » ci-dessous."
    )


def _render_application_tracking(candidate_id: str) -> None:
    """
    Suivi des candidatures.

    Les statuts sont saisis à la main : la V1 ne lit aucune boîte
    mail, ce qui demanderait un connecteur externe hors périmètre.
    """

    st.divider()

    st.subheader("Suivi des candidatures")

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
        # GÉNÉRATION DU CV CIBLÉ
        # ====================================================

        _render_cv_generation(
            candidate_id=candidate_id,
            job_offer_id=stored_result["job_offer_id"],
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
    # SUIVI DES CANDIDATURES
    # ========================================================

    _render_application_tracking(candidate_id)

    # ========================================================
    # NOUVELLE ANNONCE
    # ========================================================

    if st.button(
        "Analyser une nouvelle annonce"
    ):

        _new_draft()
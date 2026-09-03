"""
Onglet "CV & lettre" : génération du CV ciblé et de la lettre de
motivation, avec ou sans IA, sections du CV activables, et panneau
des faits pour la relecture.

Deux chemins de génération, au choix :

- "Générer avec l'IA" : la lettre est rédigée par Gemini à partir
  d'une fiche de faits (services.ai.letter_authoring.build_ai_letter),
  et le CV reprend le résumé et les lignes de preuve reformulés
  (services.ai.reformulation.reformulate_targeted_cv). Repli
  automatique sur la version déterministe en cas d'échec ou de
  garde-fou déclenché — jamais d'erreur bloquante.
- "Générer sans IA" : assemblage déterministe pur, comme avant
  l'intégration de Gemini. Toujours disponible, même sans clé API.

Dans les deux cas, la relecture humaine reste obligatoire : le
panneau des faits affiche exactement ce que le Master CV met à
disposition, pour que chaque affirmation de la lettre puisse être
vérifiée avant tout envoi.
"""

from __future__ import annotations

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.letter_authoring import build_ai_letter
from services.ai.reformulation import reformulate_targeted_cv
from services.application_service import record_application
from services.ai.gemini_client import GEMINI_MODEL
from services.cv import build_targeted_cv, export_docx, export_pdf
from services.cv.validation import validate_targeted_cv
from services.generated_cv_service import record_generated_cv
from services.job_service import get_job_offer_text
from services.letter import (
    build_cover_letter,
    export_letter_docx,
    export_letter_pdf,
)
from services.profile_service import get_candidate


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document"
)

# Ordre d'affichage des sections activables du CV — ALL_CV_SECTIONS
# (services.cv) est un ensemble, donc non ordonné.
SECTION_ORDER = (
    "resume",
    "competences",
    "experiences",
    "formation_certifications",
    "langues",
    "interets",
)

SECTION_LABELS = {
    "resume": "Profil",
    "competences": "Compétences clés",
    "experiences": "Expériences",
    "formation_certifications": "Formation & certifications",
    "langues": "Langues",
    "interets": "Centres d'intérêt",
}


def _controler_et_tracer(
    candidate_id: str,
    job_offer_id: str,
    cv,
    mode: str,
) -> list[dict]:
    """
    Contrôle déterministe du CV produit, puis trace de la génération.

    Le contrôle est du code, pas une IA : tout ce qu'il vérifie est
    confrontable exactement au Master CV. La trace enregistre les
    décisions (retenu / écarté et pourquoi), afin de pouvoir répondre
    plus tard à « pourquoi cette expérience figure-t-elle ici ? ».

    Ne fait jamais échouer la génération : un défaut de trace ne doit
    pas priver l'utilisateur de son CV.
    """

    rapport = validate_targeted_cv(cv, candidate_id, job_offer_id)

    try:
        record_generated_cv(
            candidate_id=candidate_id,
            job_offer_id=job_offer_id,
            cv=cv,
            mode=mode,
            llm_model=GEMINI_MODEL if mode == "ia" else "",
            validation_status=rapport.status,
            validation_issues=rapport.as_dicts(),
        )

    except Exception:
        pass

    return rapport.as_dicts()


def _render_controle(signalements: list[dict]) -> None:

    if not signalements:
        st.success(
            "✅ Contrôle automatique : chaque ligne remonte à une "
            "preuve du Master CV, aucun chiffre ajouté, aucune "
            "compétence non prouvée."
        )
        return

    bloquants = [
        item for item in signalements if item["severity"] == "bloquant"
    ]

    entete = (
        f"⚠️ Contrôle automatique : {len(bloquants)} anomalie(s) "
        "sérieuse(s)"
        if bloquants
        else f"ℹ️ Contrôle automatique : {len(signalements)} remarque(s)"
    )

    with st.expander(entete, expanded=bool(bloquants)):

        for item in signalements:

            if item["severity"] == "bloquant":
                st.error(item["message"])
            else:
                st.warning(item["message"])


def _render_facts_panel(cv, candidate) -> None:
    """
    Ce que le Master CV met à disposition pour cette candidature —
    exactement la matière première envoyée à l'IA quand elle rédige.
    C'est le seul outil de relecture fiable contre une dérive que le
    garde-fou automatique (limité aux chiffres inventés) ne peut pas
    détecter : comparer chaque affirmation de la lettre à ce panneau.
    """

    with st.expander(
        "🔎 Ce que le Master CV met à disposition pour cette "
        "candidature"
    ):

        rien_a_montrer = True

        if candidate is not None and candidate.motivations:

            rien_a_montrer = False

            st.markdown("**Motivations**")
            st.write(candidate.motivations)

        if cv.skill_groups:

            rien_a_montrer = False

            st.markdown("**Compétences prouvées**")

            for groupe in cv.skill_groups:
                st.write(f"- {groupe.category} : " + ", ".join(groupe.skills))

        if cv.experiences:

            rien_a_montrer = False

            st.markdown("**Éléments retenus par expérience**")

            for experience in cv.experiences:

                st.write(
                    f"**{experience.job_title} — {experience.company}**"
                )

                for ligne in experience.lines:
                    st.write(f"· {ligne.text}")

        if cv.achievements:

            rien_a_montrer = False

            st.markdown("**Réalisations**")

            for achievement in cv.achievements:
                st.write(f"- {achievement.title}")

        if rien_a_montrer:
            st.caption("Rien à afficher pour l'instant.")


def render_generation_tab(
    candidate_id: str,
    job_offer_id: str,
) -> None:
    """
    Les deux documents sont reconstruits à chaque génération depuis
    les données du Master CV : il n'existe aucun état intermédiaire
    modifiable entre l'analyse et les documents produits.
    """

    st.subheader("CV ciblé et lettre de motivation")

    st.caption(
        "Les documents ne reprennent que les compétences prouvées, "
        "c'est-à-dire déclarées dans le Master CV et soutenues par "
        "au moins une preuve. Les compétences déduites ou déclarées "
        "sans preuve en sont volontairement absentes."
    )

    etat_key = f"cv_letter_{job_offer_id}"

    col_ia, col_det = st.columns(2)

    with col_ia:

        generer_ia = st.button(
            "✨ Générer avec l'IA (Gemini)",
            key=f"generer_ia_{job_offer_id}",
            type="primary",
            use_container_width=True,
            disabled=not ai_is_configured(),
        )

        if not ai_is_configured():
            st.caption(
                "Clé GEMINI_API_KEY absente de .env — indisponible."
            )

    with col_det:

        generer_det = st.button(
            "Générer sans IA",
            key=f"generer_det_{job_offer_id}",
            use_container_width=True,
        )

    if generer_ia:

        try:
            cv_deterministe = build_targeted_cv(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )
        except Exception as error:
            st.error(f"Génération impossible : {error}")
            return

        job_text = get_job_offer_text(job_offer_id)

        with st.spinner("Rédaction en cours (Gemini)..."):

            cv_ia, avertissements_cv = reformulate_targeted_cv(
                cv_deterministe,
                job_text,
            )

            letter_ia, avertissements_lettre = build_ai_letter(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )

        st.session_state[etat_key] = {
            "cv": cv_ia,
            "letter": letter_ia,
            "mode": "ia",
            "warnings": avertissements_cv + avertissements_lettre,
            "validation": _controler_et_tracer(
                candidate_id, job_offer_id, cv_ia, mode="ia"
            ),
        }

    elif generer_det:

        try:
            cv_deterministe = build_targeted_cv(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )

            letter_deterministe = build_cover_letter(
                candidate_id=candidate_id,
                job_offer_id=job_offer_id,
            )
        except Exception as error:
            st.error(f"Génération impossible : {error}")
            return

        st.session_state[etat_key] = {
            "cv": cv_deterministe,
            "letter": letter_deterministe,
            "mode": "deterministe",
            "warnings": [],
            "validation": _controler_et_tracer(
                candidate_id,
                job_offer_id,
                cv_deterministe,
                mode="deterministe",
            ),
        }

    etat = st.session_state.get(etat_key)

    if etat is None:
        return

    cv = etat["cv"]
    letter = etat["letter"]

    if etat["mode"] == "ia":
        st.caption("Version actuelle : rédigée avec l'aide de l'IA (Gemini).")
    else:
        st.caption("Version actuelle : assemblage déterministe, sans IA.")

    for avertissement in etat["warnings"]:
        st.warning(avertissement)

    _render_controle(etat.get("validation", []))

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

    if etat["mode"] == "ia":

        st.warning(
            "⚠️ L'IA compose l'argumentaire à partir du Master CV, "
            "mais peut encore glisser vers une affirmation plus "
            "confiante que le texte source, voire une activité "
            "plausible mais absente. Le panneau ci-dessous liste "
            "exactement ce qui lui a été transmis — comparez chaque "
            "affirmation avec ces éléments avant tout envoi."
        )

    candidate = get_candidate()
    _render_facts_panel(cv, candidate)

    st.divider()

    # --------------------------------------------------------
    # SECTIONS DU CV
    # --------------------------------------------------------

    st.markdown("**Sections du CV à inclure**")

    colonnes = st.columns(len(SECTION_ORDER))
    included_sections: set[str] = set()

    for colonne, section in zip(colonnes, SECTION_ORDER):

        with colonne:

            coche = st.checkbox(
                SECTION_LABELS[section],
                value=True,
                key=f"section_{section}_{job_offer_id}",
            )

            if coche:
                included_sections.add(section)

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

    cv_docx = export_docx(cv, included_sections=included_sections)
    cv_pdf = export_pdf(cv, included_sections=included_sections)

    letter_docx = export_letter_docx(letter)
    letter_pdf = export_letter_pdf(letter)

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
        "Cette candidature a été ajoutée à votre suivi, dans "
        "l'onglet « Suivi »."
    )

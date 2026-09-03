"""
Section "Compétences" de la page Master CV.

Les compétences sont affichées en pastilles compactes plutôt qu'en
liste verticale : à 18 compétences et plus, une ligne par compétence
rendait la page illisible.

Cliquer une pastille ouvre son panneau d'édition (renommer /
supprimer). Deux popovers permettent d'en ajouter : à la main ou
depuis le référentiel, et à partir des compétences qu'un poste visé
attend habituellement.

Point d'honnêteté : une compétence ajoutée ici est **déclarée**, pas
prouvée — elle n'a aucune preuve rattachée, et le moteur de matching
continuera de la distinguer partout d'une compétence "proven". C'est
le candidat qui atteste ce qu'il sait faire, jamais le système qui
l'affirme à sa place.
"""

from __future__ import annotations

import streamlit as st

from services.ai.gemini_client import is_configured as ai_is_configured
from services.ai.skill_suggestions import suggest_skills_for_role
from services.profile_service import (
    add_skill,
    delete_skill,
    get_evidence,
    get_skills,
    update_skill,
)
from services.skill_catalog_service import get_active_skills


_STATE_SUGGESTIONS = "master_cv_suggestions_competences"


def _ajouter_plusieurs(candidate_id: str, noms: list[str]) -> None:
    """
    Ajoute une liste de compétences.

    add_skill dédoublonne déjà par nom : réajouter une compétence
    existante retourne son identifiant sans rien créer.
    """

    for nom in noms:

        if nom.strip():
            add_skill(candidate_id=candidate_id, name=nom.strip())


def _render_ajout(candidate_id: str, noms_existants: set[str]) -> None:

    with st.popover("➕ Ajouter", use_container_width=True):

        nom_libre = st.text_input(
            "Nouvelle compétence",
            key="master_cv_nouvelle_competence",
            placeholder="Ex. Gestion de budget",
        )

        if st.button("Ajouter", key="master_cv_ajouter_libre"):

            if nom_libre.strip():
                add_skill(candidate_id=candidate_id, name=nom_libre.strip())
                st.rerun()

        st.divider()

        st.caption("Ou depuis le référentiel :")

        disponibles = [
            skill.canonical_name
            for skill in get_active_skills()
            if skill.canonical_name.casefold() not in noms_existants
        ]

        if not disponibles:
            st.caption(
                "Toutes les compétences du référentiel sont déjà là."
            )
            return

        choisies = st.multiselect(
            "Compétences du référentiel",
            options=disponibles,
            key="master_cv_competences_referentiel",
            label_visibility="collapsed",
        )

        if choisies and st.button(
            f"Ajouter {len(choisies)} compétence(s)",
            key="master_cv_ajouter_referentiel",
        ):
            _ajouter_plusieurs(candidate_id, choisies)
            st.rerun()


def _render_suggestions(candidate_id: str, noms_existants: set[str]) -> None:

    with st.popover(
        "✨ Suggestions pour un poste", use_container_width=True
    ):

        if not ai_is_configured():
            st.caption(
                "Suggestions indisponibles — clé GEMINI_API_KEY "
                "absente de .env."
            )
            return

        poste = st.text_input(
            "Poste visé",
            key="master_cv_poste_suggestions",
            placeholder="Ex. Product Owner Digital",
        )

        nombre = st.select_slider(
            "Nombre de compétences",
            options=[15, 20, 30],
            value=15,
            key="master_cv_nombre_suggestions",
        )

        if st.button("Proposer", key="master_cv_lancer_suggestions"):

            with st.spinner("Recherche des compétences attendues..."):
                suggestions, avertissement = suggest_skills_for_role(
                    poste,
                    count=nombre,
                    existing=sorted(noms_existants),
                )

            st.session_state[_STATE_SUGGESTIONS] = {
                "suggestions": suggestions,
                "warning": avertissement,
            }

        etat = st.session_state.get(_STATE_SUGGESTIONS)

        if etat is None:
            return

        if etat["warning"]:
            st.caption(etat["warning"])

        if not etat["suggestions"]:
            return

        st.caption(
            "Cochez uniquement ce que vous savez réellement faire — "
            "ces compétences seront déclarées, sans preuve."
        )

        retenues = st.multiselect(
            "Compétences proposées",
            options=etat["suggestions"],
            key="master_cv_suggestions_choisies",
            label_visibility="collapsed",
        )

        if retenues and st.button(
            f"Ajouter {len(retenues)} compétence(s)",
            key="master_cv_ajouter_suggestions",
        ):
            _ajouter_plusieurs(candidate_id, retenues)
            st.session_state.pop(_STATE_SUGGESTIONS, None)
            st.rerun()


def _render_edition(candidate_id: str, skill) -> None:

    nombre_preuves = len(
        [
            preuve
            for preuve in get_evidence(candidate_id)
            if preuve.skill_id == skill.id
        ]
    )

    with st.container(border=True):

        st.caption(
            f"{nombre_preuves} preuve(s) rattachée(s)"
            if nombre_preuves
            else "Aucune preuve rattachée — compétence déclarée."
        )

        nouveau_nom = st.text_input(
            "Nom de la compétence",
            value=skill.name,
            key=f"master_cv_nom_{skill.id}",
        )

        col_renommer, col_supprimer = st.columns(2)

        with col_renommer:

            if st.button(
                "💾 Renommer",
                key=f"master_cv_renommer_{skill.id}",
                use_container_width=True,
            ):
                if nouveau_nom.strip():
                    update_skill(skill.id, name=nouveau_nom.strip())
                    st.rerun()

        with col_supprimer:

            if st.button(
                "🗑️ Supprimer",
                key=f"master_cv_supprimer_{skill.id}",
                use_container_width=True,
                help=(
                    f"Supprime aussi les {nombre_preuves} preuve(s) "
                    "rattachée(s)."
                    if nombre_preuves
                    else "Supprime cette compétence."
                ),
            ):
                delete_skill(skill.id)
                st.rerun()


def render_skills_section(candidate_id: str) -> None:

    st.subheader("Compétences")

    skills = get_skills(candidate_id)

    noms_existants = {skill.name.casefold() for skill in skills}

    col_ajout, col_suggestions = st.columns(2)

    with col_ajout:
        _render_ajout(candidate_id, noms_existants)

    with col_suggestions:
        _render_suggestions(candidate_id, noms_existants)

    if not skills:
        st.caption("Aucune compétence déclarée pour l'instant.")
        return

    st.caption(
        f"{len(skills)} compétence(s) — cliquez sur l'une d'elles "
        "pour la renommer ou la supprimer."
    )

    selection = st.pills(
        "Compétences",
        options=[skill.name for skill in skills],
        selection_mode="single",
        key="master_cv_competence_selectionnee",
        label_visibility="collapsed",
    )

    if selection:

        skill_choisie = next(
            (skill for skill in skills if skill.name == selection),
            None,
        )

        if skill_choisie is not None:
            _render_edition(candidate_id, skill_choisie)

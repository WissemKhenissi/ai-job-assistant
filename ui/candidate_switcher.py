"""
Sélection du profil courant.

L'application n'a longtemps connu qu'un seul candidat : `get_candidate`
prenait le premier venu et `get_experiences` retournait le parcours de
tout le monde. Tant qu'une seule fiche existait, le défaut restait
invisible ; à la deuxième, les parcours se seraient mélangés.

Ce module fixe le profil courant pour toute la session et le passe
explicitement à chaque page. Il ne fait pas de l'application un
logiciel multi-utilisateur : il n'y a ni compte, ni mot de passe, ni
cloisonnement vis-à-vis de quelqu'un qui aurait accès au fichier de
base. C'est un sélecteur de profil, pas une authentification — et le
dire clairement vaut mieux que de le laisser croire.
"""

from __future__ import annotations

import streamlit as st

from services.profile_service import (
    count_candidate_data,
    create_candidate,
    delete_candidate,
    list_candidates,
)


CLE = "candidate_id"


def _basculer(candidate_id: str) -> None:
    """
    Change de profil et vide l'état de session.

    Sans ce nettoyage, l'analyse d'annonce, l'entretien et les
    documents générés du profil précédent resteraient affichés sous
    le nouveau — le mélange que ce module existe pour empêcher.
    """

    for cle in list(st.session_state.keys()):

        if cle != CLE:
            st.session_state.pop(cle, None)

    st.session_state[CLE] = candidate_id


def _rendre_creation() -> None:

    with st.sidebar.popover("➕ Nouveau profil", use_container_width=True):

        prenom = st.text_input("Prénom", key="nouveau_prenom")
        nom = st.text_input("Nom", key="nouveau_nom")

        if st.button(
            "Créer", type="primary", use_container_width=True
        ):
            _basculer(create_candidate(prenom, nom))
            st.rerun()


def _rendre_suppression(candidate_id: str, libelle: str) -> None:

    with st.sidebar.popover(
        "🗑️ Supprimer ce profil", use_container_width=True
    ):

        decompte = count_candidate_data(candidate_id)

        detail = ", ".join(
            f"{valeur} {nom.replace('_', ' ')}"
            for nom, valeur in decompte.items()
            if valeur
        )

        st.warning(
            f"**{libelle}** et tout ce qui lui est rattaché seront "
            "définitivement supprimés."
            + (f"\n\nContenu : {detail}." if detail else "")
        )

        st.caption(
            "Il n'y a ni corbeille ni restauration. Recopiez le nom "
            "du profil pour confirmer."
        )

        saisie = st.text_input(
            "Nom du profil",
            key=f"confirmation_suppression_{candidate_id}",
            placeholder=libelle,
        )

        if st.button(
            "Supprimer définitivement",
            type="primary",
            use_container_width=True,
            disabled=saisie.strip() != libelle,
        ):
            delete_candidate(candidate_id)
            st.session_state.pop(CLE, None)
            st.rerun()


def render_candidate_switcher() -> str | None:
    """
    Affiche le sélecteur et retourne l'identifiant du profil courant.

    Retourne None si la base ne contient aucun profil : l'appelant
    doit alors proposer d'en créer un plutôt que de planter.
    """

    profils = list_candidates()

    if not profils:

        st.sidebar.info("Aucun profil.")
        _rendre_creation()

        return None

    identifiants = [profil["id"] for profil in profils]

    libelles = {
        profil["id"]: profil["full_name"] for profil in profils
    }

    courant = st.session_state.get(CLE)

    if courant not in identifiants:
        courant = identifiants[0]
        st.session_state[CLE] = courant

    if len(profils) > 1:

        choisi = st.sidebar.selectbox(
            "Profil",
            options=identifiants,
            index=identifiants.index(courant),
            format_func=lambda cle: libelles.get(cle, cle),
        )

        if choisi != courant:
            _basculer(choisi)
            st.rerun()

        courant = choisi

    else:
        st.sidebar.caption(f"Profil : {libelles[courant]}")

    _rendre_creation()
    _rendre_suppression(courant, libelles[courant])

    return courant

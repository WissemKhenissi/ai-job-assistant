"""
Page d'accueil : où en est la recherche, et ce qui attend une action.

L'application s'ouvrait sur un formulaire — « Importer depuis un CV »
— c'est-à-dire sur la première chose qu'on fait une seule fois. Celui
qui revient n'avait aucune réponse à « où j'en étais ? ».

Ce que cette page montre et ce qu'elle refuse de montrer tiennent au
même principe que le reste du produit. On y trouve des comptes : des
candidatures par étape, des compétences sans preuve, des termes à
trier. On n'y trouve ni score moyen, ni taux de réponse, ni
pourcentage de complétion — des chiffres qu'on cherche à faire monter
plutôt qu'à corriger, et qui ne disent rien de ce qu'il y a à faire
aujourd'hui.

Chaque manque énoncé ici pointe vers l'écran qui le comble.
"""

from __future__ import annotations

import streamlit as st

from models.application import APPLICATION_COLUMNS
from services.application_service import list_applications
from services.profile_service import (
    count_candidate_data,
    get_undocumented_skills,
)
from services.skill_candidate_service import get_candidates


# Au-delà, la liste des exemples cités devient une liste tout court.
_EXEMPLES_CITES = 4


def _lien(url_path: str, label: str, icon: str | None = None) -> None:
    """
    Un lien interne, sans rechargement de l'application.

    L'import est tardif : ui.navigation construit cette page, et
    l'importer en tête créerait un cycle.
    """

    from ui.navigation import lien_vers

    lien_vers(url_path, label, icon)


def _rendre_candidatures(candidate_id: str) -> None:

    st.subheader("Mes candidatures")

    candidatures = list_applications(candidate_id)

    if not candidatures:

        st.caption(
            "Aucune candidature suivie pour l'instant."
        )

        _lien("analyser", "Analyser une annonce", "📋")

        return

    par_statut: dict[str, int] = {}

    for candidature in candidatures:
        par_statut[candidature.status] = (
            par_statut.get(candidature.status, 0) + 1
        )

    colonnes = st.columns(len(APPLICATION_COLUMNS))

    for colonne, (titre, statuts) in zip(
        colonnes, APPLICATION_COLUMNS
    ):

        colonne.metric(
            titre,
            sum(par_statut.get(statut, 0) for statut in statuts),
        )

    gauche, droite = st.columns(2)

    with gauche:
        _lien("suivi", "Voir le suivi", "📌")

    with droite:
        _lien("analyser", "Analyser une annonce", "📋")


def _rendre_en_attente(candidate_id: str) -> None:

    st.subheader("Ce qui attend une action")

    quelque_chose = False

    # --------------------------------------------------------
    # COMPETENCES DECLAREES SANS PREUVE
    # --------------------------------------------------------
    #
    # Ce n'est pas un défaut du candidat : il a fait ces choses, il ne
    # les a pas racontées. Le texte le dit, parce qu'un tableau de
    # bord qui aligne des manques sans les qualifier se lit comme un
    # reproche.

    sans_preuve = get_undocumented_skills(candidate_id)

    if sans_preuve:

        quelque_chose = True

        noms = [
            competence["name"] for competence in sans_preuve
        ]

        with st.container(border=True):

            st.markdown(
                f"**{len(noms)} compétence(s) déclarée(s) sans "
                "preuve**"
            )

            st.caption(
                "Elles ne peuvent pas figurer sur un CV généré, et "
                "elles pèsent moins face à une annonce qui les "
                "demande. Vous les avez faites — il reste à les "
                "raconter. "
                + ", ".join(noms[:_EXEMPLES_CITES])
                + ("…" if len(noms) > _EXEMPLES_CITES else "")
            )

            _lien("entretien", "Documenter une compétence", "🎙️")

    # --------------------------------------------------------
    # TERMES INCONNUS DU REFERENTIEL
    # --------------------------------------------------------
    #
    # Un terme inconnu est un trou du référentiel, pas une compétence
    # absente du candidat — mais il compte quand même comme exigence
    # manquante tant qu'il n'est pas trié. D'où sa place ici.

    a_trier = get_candidates(only_pending=True)

    if a_trier:

        quelque_chose = True

        termes = [terme["term"] for terme in a_trier]

        with st.container(border=True):

            st.markdown(
                f"**{len(termes)} terme(s) que le référentiel ne "
                "reconnaît pas**"
            )

            st.caption(
                "Rencontrés dans vos annonces. Tant qu'ils ne sont "
                "pas rattachés, ils comptent comme des exigences "
                "manquantes. "
                + ", ".join(termes[:_EXEMPLES_CITES])
                + ("…" if len(termes) > _EXEMPLES_CITES else "")
            )

            _lien("referentiel", "Trier les termes", "🧩")

    if not quelque_chose:
        st.caption("Rien en attente.")


def _rendre_master_cv(candidate_id: str, experiences) -> None:

    st.subheader("Mon Master CV")

    comptes = count_candidate_data(candidate_id)

    if not experiences:

        st.caption(
            "Aucune expérience enregistrée. Tout part de là : le "
            "matching, les preuves, le CV généré."
        )

        _lien("profil", "Importer mon CV", "👤")

        return

    # Des comptes, pas un taux de complétion : un pourcentage se
    # cherche à faire monter, un compte se lit pour ce qu'il est.
    colonnes = st.columns(4)

    for colonne, (titre, cle) in zip(
        colonnes,
        (
            ("Expériences", "experiences"),
            ("Compétences", "competences"),
            ("Preuves", "preuves"),
            ("Analyses", "analyses"),
        ),
    ):
        colonne.metric(titre, comptes.get(cle, 0))

    _lien("profil", "Voir mon profil", "👤")


def render_dashboard(candidate, experiences) -> None:

    st.header("Où j'en suis", divider="blue")

    _rendre_candidatures(candidate.id)

    st.divider()

    _rendre_en_attente(candidate.id)

    st.divider()

    _rendre_master_cv(candidate.id, experiences)


__all__ = ["render_dashboard"]

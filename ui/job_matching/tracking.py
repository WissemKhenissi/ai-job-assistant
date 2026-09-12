"""
Écran "Suivi" : où en est chaque candidature.

Le suivi ne commençait qu'après la génération des documents — une
annonce repérée, ou une candidature envoyée à la main, ne pouvait pas
être suivie du tout. L'écran s'ouvrait donc le plus souvent sur
« aucune candidature enregistrée », alors que c'est précisément là que
vit une recherche d'emploi au quotidien.

Les étapes viennent de models.application : un statut décrit un fait,
une étape décrit où en est la candidature.

Deux affichages, parce que les colonnes ont une contrainte de largeur
qu'on ne peut pas contourner. Cinq colonnes demandent environ onze
cents pixels ; en dessous, le titre d'une carte s'écrit lettre par
lettre. Streamlit n'a pas de requêtes de média : la mise en page ne
peut donc pas s'adapter toute seule, et c'est à l'utilisateur de
choisir. La liste dit la même chose, en hauteur plutôt qu'en largeur.

Streamlit ne permet pas non plus de déplacer une carte à la souris
sans composant tiers. Chaque carte ouvre son panneau, où le statut se
choisit dans une liste — un clic de plus qu'un glisser-déposer, et
aucune dépendance supplémentaire.

Les statuts restent saisis à la main : l'application ne lit aucune
boîte mail, ce qui demanderait un connecteur externe hors périmètre.
"""

from __future__ import annotations

import streamlit as st

from models.application import (
    APPLICATION_COLUMNS,
    APPLICATION_STATUS_LABELS,
    APPLICATION_STATUSES,
)
from services.application_service import (
    list_applications,
    update_application_status,
)


# Une colonne sur cinq mesure environ deux cents pixels sur un écran
# d'ordinateur portable : au-delà de cette longueur, le titre s'y
# étale sur cinq lignes.
_LONGUEUR_TITRE_CARTE = 34

_VUES = ("Colonnes", "Liste")

_CLE_VUE = "suivi_affichage"


def _titre_court(candidature) -> str:

    titre = candidature.job_offer_title or "Annonce"

    if len(titre) <= _LONGUEUR_TITRE_CARTE:
        return titre

    return titre[: _LONGUEUR_TITRE_CARTE - 1].rstrip() + "…"


def _intitule_complet(candidature) -> str:

    intitule = candidature.job_offer_title or "Annonce"

    if candidature.company:
        intitule += f" — {candidature.company}"

    return intitule


def _grouper(candidatures) -> list[tuple[str, list]]:
    """
    Les candidatures par étape, dans l'ordre du parcours.

    Partagé par les deux affichages : une candidature ne doit pas
    changer d'étape selon la façon dont on la regarde.
    """

    par_statut: dict[str, list] = {}

    for candidature in candidatures:
        par_statut.setdefault(candidature.status, []).append(
            candidature
        )

    return [
        (
            titre,
            [
                candidature
                for statut in statuts
                for candidature in par_statut.get(statut, [])
            ],
        )
        for titre, statuts in APPLICATION_COLUMNS
    ]


def _rendre_panneau(candidature) -> None:
    """Le détail d'une candidature, et la saisie de son statut."""

    st.caption(
        "Créée le "
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
    else:
        st.caption("Aucun document généré pour cette annonce.")

    with st.form(f"suivi_{candidature.id}"):

        statut = st.selectbox(
            "Statut",
            options=APPLICATION_STATUSES,
            index=(
                APPLICATION_STATUSES.index(candidature.status)
                if candidature.status in APPLICATION_STATUSES
                else 0
            ),
            format_func=lambda valeur: (
                APPLICATION_STATUS_LABELS.get(valeur, valeur)
            ),
        )

        notes = st.text_area(
            "Notes",
            value=candidature.notes,
            placeholder="Contact, canal d'envoi, retour reçu...",
        )

        if st.form_submit_button(
            "Enregistrer",
            use_container_width=True,
        ):

            try:

                update_application_status(
                    application_id=candidature.id,
                    status=statut,
                    notes=notes,
                )

                st.rerun()

            except Exception as error:

                st.error(f"Mise à jour impossible : {error}")


def _rendre_carte(candidature) -> None:

    with st.container(border=True):

        st.markdown(f"**{_titre_court(candidature)}**")

        if candidature.company:
            st.caption(candidature.company)

        with st.popover("Ouvrir", use_container_width=True):
            _rendre_panneau(candidature)


def _rendre_colonnes(groupes) -> None:

    colonnes = st.columns(len(groupes))

    for colonne, (titre, retenues) in zip(colonnes, groupes):

        with colonne:

            # Le compte sur la même ligne que l'intitulé : sur sa
            # propre ligne, il descendait d'un cran dès qu'un
            # intitulé passait à la ligne, et les colonnes ne
            # s'alignaient plus.
            st.markdown(f"**{titre}** · {len(retenues)}")

            for candidature in retenues:
                _rendre_carte(candidature)


def _rendre_liste(groupes) -> None:

    for titre, retenues in groupes:

        # Une étape vide ne mérite pas un titre : en hauteur, elle
        # n'apprend rien et éloigne la suivante. En colonnes, elle
        # garde sa place parce que c'est la place qui porte le sens.
        if not retenues:
            continue

        st.markdown(f"**{titre}** · {len(retenues)}")

        for candidature in retenues:

            with st.expander(
                f"{_intitule_complet(candidature)}  ·  "
                f"{candidature.status_label}"
            ):
                _rendre_panneau(candidature)


def _signaler_orphelines(candidatures) -> None:
    """
    Un statut absent des étapes n'apparaîtrait nulle part, et la
    candidature disparaîtrait de l'écran sans que rien ne le dise.
    """

    connus = {
        statut
        for _titre, statuts in APPLICATION_COLUMNS
        for statut in statuts
    }

    orphelines = [
        candidature
        for candidature in candidatures
        if candidature.status not in connus
    ]

    if not orphelines:
        return

    st.divider()

    st.warning(
        "Statut inconnu des étapes, à rattacher : "
        + ", ".join(
            f"{_titre_court(c)} ({c.status})" for c in orphelines
        )
    )


def render_tracking_tab(candidate_id: str) -> None:

    candidatures = list_applications(candidate_id)

    if not candidatures:

        st.info(
            "Aucune candidature suivie. Analysez une annonce, puis "
            "« Suivre cette annonce » — sans attendre d'avoir généré "
            "ses documents."
        )

        return

    vue = st.segmented_control(
        "Affichage",
        options=_VUES,
        default=_VUES[0],
        key=_CLE_VUE,
        label_visibility="collapsed",
        help=(
            "Les colonnes demandent de la largeur ; la liste tient "
            "sur un écran étroit."
        ),
    )

    groupes = _grouper(candidatures)

    # segmented_control rend None quand l'utilisateur désélectionne :
    # l'écran doit alors garder un affichage, pas disparaître.
    if vue == "Liste":
        _rendre_liste(groupes)
    else:
        _rendre_colonnes(groupes)

    _signaler_orphelines(candidatures)

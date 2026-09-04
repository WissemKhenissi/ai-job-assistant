"""
Onglet "Référentiel" : les termes d'annonce que le système ne connaît
pas encore, et ce que l'utilisateur décide d'en faire.

Le référentiel pilote le matching, le vocabulaire autorisé à la
rédaction et le tri des exigences. Livré figé, il ne couvre que les
métiers prévus par son auteur. Cet onglet est la boucle qui lui permet
de grandir : chaque analyse d'annonce y dépose les termes inconnus,
l'utilisateur tranche.

Trois décisions, jamais prises automatiquement :

- **Rattacher** : l'annonce nomme autrement une compétence déjà
  connue. C'est le cas le plus fréquent.
- **Créer** : le terme désigne une compétence que le référentiel
  ignore — le seul moyen d'ouvrir l'outil à un nouveau métier.
- **Ignorer** : ce n'est pas une compétence.

Créer une compétence, c'est affirmer qu'un terme en désigne une. Cette
affirmation revient à l'utilisateur, pas à la machine.
"""

from __future__ import annotations

import streamlit as st

from services.skill_candidate_service import (
    attach_as_alias,
    get_candidates,
    ignore_candidate,
    promote_to_catalog,
)
from services.skill_catalog_service import get_active_skills


CATEGORIES = [
    "",
    "Product",
    "Project Management",
    "Management",
    "Business",
    "Data",
    "Technology",
    "Tools",
    "Design",
    "AI",
]


def _rendre_un_terme(candidat: dict, competences) -> bool:
    """Affiche un terme et ses trois issues. Retourne True si traité."""

    identifiant = candidat["id"]

    entete = f"**{candidat['term']}**"

    if candidat["occurrences"] > 1:
        entete += f" — vu {candidat['occurrences']} fois"

    if not candidat["was_counted"]:
        entete += " — écarté du décompte"

    st.markdown(entete)

    col_rattacher, col_creer, col_ignorer = st.columns([3, 3, 1])

    traite = False

    # ----------------------------------------------------------
    # RATTACHER A UNE COMPETENCE EXISTANTE
    # ----------------------------------------------------------

    with col_rattacher:

        with st.popover("🔗 Rattacher", use_container_width=True):

            st.caption(
                "L'annonce nomme autrement une compétence que le "
                "référentiel connaît déjà."
            )

            choix = st.selectbox(
                "Compétence",
                options=[item.id for item in competences],
                format_func=lambda cle: _libelle(competences, cle),
                key=f"rattacher_choix_{identifiant}",
                label_visibility="collapsed",
            )

            if st.button(
                "Rattacher",
                key=f"rattacher_{identifiant}",
                type="primary",
                use_container_width=True,
            ):
                attach_as_alias(identifiant, choix)
                traite = True

    # ----------------------------------------------------------
    # CREER UNE COMPETENCE
    # ----------------------------------------------------------

    with col_creer:

        with st.popover("➕ Créer", use_container_width=True):

            st.caption(
                "Le terme désigne une compétence que le référentiel "
                "ignore. C'est ce qui ouvre l'outil à un métier qu'il "
                "ne couvrait pas."
            )

            nom = st.text_input(
                "Nom de la compétence",
                value=candidat["term"],
                key=f"creer_nom_{identifiant}",
            )

            categorie = st.selectbox(
                "Catégorie",
                options=CATEGORIES,
                key=f"creer_categorie_{identifiant}",
            )

            if st.button(
                "Créer",
                key=f"creer_{identifiant}",
                type="primary",
                use_container_width=True,
            ):
                try:
                    promote_to_catalog(
                        identifiant,
                        canonical_name=nom,
                        category=categorie,
                    )
                    traite = True

                except ValueError as erreur:
                    st.error(str(erreur))

    # ----------------------------------------------------------
    # IGNORER
    # ----------------------------------------------------------

    with col_ignorer:

        if st.button(
            "🗑️",
            key=f"ignorer_{identifiant}",
            help="Ce n'est pas une compétence",
            use_container_width=True,
        ):
            ignore_candidate(identifiant)
            traite = True

    return traite


def _libelle(competences, identifiant: str) -> str:

    for item in competences:
        if item.id == identifiant:
            return (
                f"{item.canonical_name}"
                + (f" ({item.category})" if item.category else "")
            )

    return identifiant


def render_referentiel_tab() -> None:

    st.write(
        "Les termes rencontrés dans vos annonces que le référentiel "
        "ne reconnaît pas encore."
    )

    st.caption(
        "Un terme inconnu n'est pas une compétence qui vous manque : "
        "c'est un trou du référentiel. Tant qu'il y reste, l'annonce "
        "qui l'emploie compte une exigence que rien ne peut couvrir, "
        "et la rédaction s'interdit ce mot."
    )

    candidats = get_candidates()

    if not candidats:

        st.success(
            "Rien à trier : toutes les exigences rencontrées sont "
            "reconnues par le référentiel."
        )

        traites = get_candidates(only_pending=False)

        if traites:
            st.caption(
                f"{len(traites)} terme(s) déjà traité(s)."
            )

        return

    competences = get_active_skills()

    st.info(
        f"{len(candidats)} terme(s) à trier. Après un ajout, "
        "relancez l'analyse des annonces concernées pour en voir "
        "l'effet sur votre score."
    )

    for candidat in candidats:

        with st.container(border=True):

            if _rendre_un_terme(candidat, competences):
                st.rerun()
